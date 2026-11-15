// Editor for Discord roles: see flasquelistan/discord_roles.py.
//
// Edits stay in the browser (and in localStorage) as additions and removals
// per person until they are reviewed and applied. "base" is who has which
// role in Discord, "desired" is what the admin wants; the difference between
// them is the pending change.
(function () {
  'use strict';

  var root = document.getElementById('discord-roles');
  var config = JSON.parse(document.getElementById('discord-roles-config').textContent);
  var T = config.strings;
  var csrfToken = root.dataset.csrfToken;
  var storageKey = 'discord-roles-' + config.viewId;

  var roles = [];          // [{id, name, color, problem}]
  var roleById = new Map();
  var editable = new Set(); // ids of roles that can be edited
  var people = new Map();   // key -> person
  var base = new Map();     // key -> Set of role ids, as in Discord
  var desired = new Map();  // key -> Set of role ids, as wanted
  var missingRoles = 0;
  var loaded = false;
  var settings = { exclusive: false, source: 'active', poolOpen: null };
  var filterText = ''; // normalized
  var filterRaw = '';  // as typed

  // ---------------------------------------------------------------- helpers

  function fmt(s, vars) {
    return s.replace(/%\((\w+)\)s/g, function (m, k) { return vars[k]; });
  }

  // Build a DOM element. attrs: properties, or "on<event>" handlers.
  function h(tag, attrs) {
    var el = document.createElement(tag);
    for (var k in attrs || {}) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) continue;
      if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v);
      else if (k === 'class') el.className = v;
      else if (k === 'dataset') Object.assign(el.dataset, v);
      else if (k === 'style') el.style.cssText = v;
      else if (k in el && typeof v !== 'string') el[k] = v;
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (var i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  }

  function append(el, child) {
    if (child === null || child === undefined || child === false) return;
    if (Array.isArray(child)) { child.forEach(function (c) { append(el, c); }); return; }
    el.appendChild(typeof child === 'string' || typeof child === 'number'
      ? document.createTextNode(String(child)) : child);
  }

  function storageGet() {
    try { return JSON.parse(localStorage.getItem(storageKey)) || {}; } catch (e) { return {}; }
  }

  function storageSet(value) {
    try { localStorage.setItem(storageKey, JSON.stringify(value)); } catch (e) { /* private mode */ }
  }

  // "Mutually exclusive" is not remembered: it always starts from the view's
  // setting.
  function save() {
    storageSet({ changes: changes(), settings: { source: settings.source, poolOpen: settings.poolOpen } });
  }

  function request(method, url, body) {
    var opts = { method: method, headers: { 'X-CSRFToken': csrfToken }, credentials: 'same-origin' };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) throw new Error(data.error || (r.status + ' ' + r.statusText));
        return data;
      });
    });
  }

  function byName(a, b) { return a.name.localeCompare(b.name, 'sv'); }

  // ---------------------------------------------------------------- search
  //
  // Shared by the autocomplete and paste import. Case and accents are
  // ignored. Tiers: 1 = the whole query is the full name, the first name or
  // the nickname (what people are usually called), 2 = every word of the
  // query starts a different word of the first name, last name or nickname,
  // 3 = the query is part of the full name or nickname, 4 = all but one of
  // at least three words match as in tier 2, including the first word (an
  // extra middle name, a second surname, or a note after the name), 5 = the
  // same but the first word doesn't match ("Anna Karin Berg" for Karin
  // Berg). 0 = no match.

  function normalize(s) {
    return (s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
      .replace(/[^\p{L}\p{N}\s-]/gu, ' ').replace(/\s+/g, ' ').trim();
  }

  function indexPerson(p) {
    p._full = normalize(p.first_name + ' ' + p.last_name) || normalize(p.name);
    p._first = normalize(p.first_name);
    p._nick = normalize(p.nickname);
    p._words = (p._full + ' ' + p._nick).split(/[\s-]+/).filter(Boolean);
    p._firstWords = (p._first + ' ' + p._nick).split(/[\s-]+/).filter(Boolean);
  }

  function matchTier(p, q) {
    if (!q) return 0;
    if (q === p._full || q === p._first || q === p._nick) return 1;
    var words = q.split(/[\s-]+/).filter(Boolean);
    var tokens = words.slice().sort(function (a, b) { return b.length - a.length; });
    var used = new Array(p._words.length).fill(false);
    var matched = tokens.filter(function (t) {
      for (var i = 0; i < p._words.length; i++) {
        if (!used[i] && p._words[i].startsWith(t)) { used[i] = true; return true; }
      }
      return false;
    }).length;
    if (matched === tokens.length) return 2;
    if (p._full.includes(q) || (p._nick && p._nick.includes(q))) return 3;
    if (tokens.length >= 3 && matched >= tokens.length - 1) {
      var firstMatches = p._firstWords.some(function (w) { return w.startsWith(words[0]); });
      return firstMatches ? 4 : 5;
    }
    return 0;
  }

  function inSource(p) {
    return settings.source === 'all' || p.active;
  }

  // Streque users matching the query, best first; people in the chosen user
  // list (active or all) before the rest.
  function search(query) {
    var q = normalize(query);
    var results = [];
    people.forEach(function (p) {
      if (p.discord === 'external') return;
      var tier = matchTier(p, q);
      if (tier) results.push({ person: p, tier: tier, inSource: inSource(p) });
    });
    results.sort(function (a, b) {
      return (b.inSource - a.inSource) || (a.tier - b.tier) || byName(a.person, b.person);
    });
    return results;
  }

  // ---------------------------------------------------------------- state

  function canAssign(p) {
    return p.discord === 'linked' || p.discord === 'external';
  }

  function changes() {
    var list = [];
    desired.forEach(function (want, key) {
      var have = base.get(key);
      var add = [], remove = [];
      want.forEach(function (r) { if (!have.has(r)) add.push(r); });
      have.forEach(function (r) { if (!want.has(r)) remove.push(r); });
      if (add.length || remove.length) list.push({ key: key, add: add, remove: remove });
    });
    return list;
  }

  // Take fresh data from the server, keeping the pending changes on top of it.
  function setState(data, pending) {
    roles = data.roles;
    roleById = new Map(roles.map(function (r) { return [r.id, r]; }));
    editable = new Set(roles.filter(function (r) { return !r.problem; }).map(function (r) { return r.id; }));
    missingRoles = data.missing_roles;
    people = new Map();
    base = new Map();
    desired = new Map();
    data.people.forEach(function (p) {
      indexPerson(p);
      people.set(p.key, p);
      base.set(p.key, new Set(p.roles));
      desired.set(p.key, new Set(p.roles));
    });
    (pending || []).forEach(function (c) {
      var p = people.get(c.key);
      if (!p || !canAssign(p)) return;
      var want = desired.get(c.key);
      c.add.forEach(function (r) { if (editable.has(r)) want.add(r); });
      c.remove.forEach(function (r) { if (editable.has(r)) want.delete(r); });
    });
    loaded = true;
  }

  function commit() {
    save();
    render();
  }

  // Add to a role. In exclusive mode, also remove from the view's other
  // roles, except those listed in keep.
  function addTo(want, roleId, keep) {
    if (settings.exclusive) {
      editable.forEach(function (r) {
        if (r !== roleId && !(keep && keep.has(r))) want.delete(r);
      });
    }
    want.add(roleId);
  }

  function add(key, roleId) { addTo(desired.get(key), roleId); commit(); }
  function remove(key, roleId) { desired.get(key).delete(roleId); commit(); }

  function move(key, from, to, copy) {
    var want = desired.get(key);
    if (copy) want.add(to);
    else {
      if (from) want.delete(from);
      addTo(want, to);
    }
    commit();
  }

  function clearRole(roleId) {
    desired.forEach(function (want) { want.delete(roleId); });
  }

  // ---------------------------------------------------------------- popover menu

  var openMenu = null;

  function closeMenu() {
    if (openMenu) { openMenu.remove(); openMenu = null; }
  }

  function showMenu(anchor, items) {
    closeMenu();
    var menu = h('div', { class: 'dr-menu', role: 'menu' }, items.map(function (item) {
      return h('button', { type: 'button', role: 'menuitem', onclick: function () { closeMenu(); item.action(); } }, item.label);
    }));
    document.body.appendChild(menu);
    var rect = anchor.getBoundingClientRect();
    var left = Math.min(rect.left + window.scrollX, window.scrollX + document.documentElement.clientWidth - menu.offsetWidth - 8);
    menu.style.left = Math.max(8, left) + 'px';
    menu.style.top = (rect.bottom + window.scrollY + 2) + 'px';
    openMenu = menu;
    var first = menu.querySelector('button');
    if (first) first.focus();
  }

  document.addEventListener('click', function (e) {
    if (openMenu && !openMenu.contains(e.target) && !e.target.closest('.dr-menu-button')) closeMenu();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeMenu();
  });

  // ---------------------------------------------------------------- autocomplete

  // Attach an autocomplete dropdown to an input. candidates(query) returns
  // [{person, note, disabled}]; onPick(person) is called on selection.
  function autocomplete(input, candidates, onPick) {
    var list = null;
    var items = [];
    var active = -1;

    function close() {
      if (list) { list.remove(); list = null; }
      items = [];
      active = -1;
    }

    function highlight(i) {
      active = i;
      Array.prototype.forEach.call(list.children, function (li, j) {
        li.classList.toggle('active', j === i);
      });
    }

    function pick(item) {
      if (!item || item.disabled) return;
      input.value = '';
      close();
      onPick(item.person);
    }

    function update() {
      close();
      if (!input.value.trim()) return;
      items = candidates(input.value).slice(0, 8);
      list = h('ul', { class: 'dr-autocomplete', role: 'listbox' });
      if (!items.length) list.appendChild(h('li', { class: 'disabled' }, T.noMatches));
      items.forEach(function (item, i) {
        list.appendChild(h('li', {
          role: 'option',
          class: item.disabled ? 'disabled' : '',
          onmousedown: function (e) { e.preventDefault(); pick(item); },
          onmouseenter: function () { if (!item.disabled) highlight(i); },
        }, h('span', {}, item.person.name), item.note ? h('small', {}, item.note) : null));
      });
      input.parentNode.appendChild(list);
      var first = items.findIndex(function (item) { return !item.disabled; });
      if (first >= 0) highlight(first);
    }

    input.addEventListener('input', update);
    input.addEventListener('blur', function () { setTimeout(close, 100); });
    input.addEventListener('keydown', function (e) {
      if (!list) return;
      var step = e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0;
      if (step) {
        e.preventDefault();
        for (var i = active + step; i >= 0 && i < items.length; i += step) {
          if (!items[i].disabled) { highlight(i); break; }
        }
      } else if (e.key === 'Enter') {
        e.preventDefault();
        pick(items[active]);
      } else if (e.key === 'Escape') {
        // Only close the dropdown, not a dialog around it.
        e.preventDefault();
        close();
      }
    });
  }

  function statusNote(p) {
    if (p.discord === 'unlinked') return T.unlinked;
    if (p.discord === 'not_in_guild') return T.notInGuild;
    if (p.discord === 'external') return T.external;
    return null;
  }

  function roleNames(ids) {
    return ids.map(function (r) { return roleById.get(r).name; }).join(', ');
  }

  // Candidates for adding someone to a role.
  function roleCandidates(roleId) {
    return function (query) {
      return search(query).filter(function (res) {
        return !desired.get(res.person.key).has(roleId);
      }).map(function (res) {
        var p = res.person;
        var note = statusNote(p);
        var others = Array.from(desired.get(p.key)).filter(function (r) { return r !== roleId && editable.has(r); });
        if (!note && settings.exclusive && others.length) note = fmt(T.movesFrom, { roles: roleNames(others) });
        if (!note && !res.inSource) note = T.notActive;
        return { person: p, note: note, disabled: !canAssign(p) };
      });
    };
  }

  // ---------------------------------------------------------------- rendering

  function avatar(p) {
    if (p.picture) return h('img', { class: 'dr-avatar', src: p.picture, alt: '', loading: 'lazy' });
    return h('span', { class: 'dr-avatar' }, p.emoji || '?');
  }

  function dragData(e, key, from) {
    e.dataTransfer.setData('application/x-discord-role-person', JSON.stringify({ key: key, from: from }));
    e.dataTransfer.effectAllowed = 'copyMove';
  }

  function memberRow(p, roleId, state) {
    var locked = !editable.has(roleId);
    var want = desired.get(p.key);
    var others = Array.from(want).filter(function (r) { return r !== roleId; });
    var note = statusNote(p);
    var matches = filterText && matchTier(p, filterText);

    var actions = [];
    if (!locked && state === 'removed') {
      actions.push(h('button', { type: 'button', class: 'dr-icon', title: T.undo, 'aria-label': T.undo,
        // Just restore the role, even in exclusive mode: the person may
        // really be in several roles.
        onclick: function () { desired.get(p.key).add(roleId); commit(); } }, '↶'));
    } else if (!locked) {
      var targets = roles.filter(function (r) { return r.id !== roleId && editable.has(r.id) && !want.has(r.id); });
      if (targets.length) {
        actions.push(h('button', { type: 'button', class: 'dr-icon dr-menu-button', title: T.menu, 'aria-label': T.menu,
          onclick: function (e) {
            var items = [];
            targets.forEach(function (r) {
              items.push({ label: fmt(T.moveTo, { role: r.name }), action: function () { move(p.key, roleId, r.id, false); } });
              if (!settings.exclusive) {
                items.push({ label: fmt(T.alsoAdd, { role: r.name }), action: function () { move(p.key, roleId, r.id, true); } });
              }
            });
            items.push({ label: T.remove, action: function () { remove(p.key, roleId); } });
            showMenu(e.currentTarget, items);
          } }, '⋯'));
      }
      actions.push(h('button', { type: 'button', class: 'dr-icon', title: T.remove, 'aria-label': T.remove,
        onclick: function () { remove(p.key, roleId); } }, '×'));
    }

    var flags = [];
    // In an exclusive view, being in several roles is worth pointing out.
    if (settings.exclusive && state !== 'removed' && others.length) {
      flags.push(h('span', { class: 'dr-flag', title: roleNames(others) }, '+' + roleNames(others)));
    }
    if (p.discord === 'not_in_guild') flags.push(h('span', { class: 'dr-flag dr-flag-bad' }, T.notInGuild));

    return h('li', {
      class: 'dr-member' + (state ? ' dr-' + state : '') + (p.discord === 'external' ? ' dr-external' : '') + (matches ? ' dr-match' : ''),
      draggable: !locked && state !== 'removed' ? 'true' : null,
      title: note,
      ondragstart: !locked && state !== 'removed' ? function (e) { dragData(e, p.key, roleId); } : null,
    },
      avatar(p),
      // Badges go below the name, so that they never squeeze it.
      h('span', { class: 'dr-name-block' },
        h('span', { class: 'dr-name' }, p.name),
        flags.length ? h('span', { class: 'dr-flags' }, flags) : null),
      actions);
  }

  function dropZone(el, onDrop) {
    el.addEventListener('dragover', function (e) {
      if (!e.dataTransfer.types.includes('application/x-discord-role-person')) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = (e.ctrlKey || e.altKey) ? 'copy' : 'move';
      el.classList.add('dr-dragover');
    });
    el.addEventListener('dragleave', function (e) {
      if (!el.contains(e.relatedTarget)) el.classList.remove('dr-dragover');
    });
    el.addEventListener('drop', function (e) {
      el.classList.remove('dr-dragover');
      var raw = e.dataTransfer.getData('application/x-discord-role-person');
      if (!raw) return;
      e.preventDefault();
      onDrop(JSON.parse(raw), e.ctrlKey || e.altKey);
    });
  }

  function column(role) {
    var locked = !!role.problem;
    var members = [], removed = [];
    var before = 0;
    people.forEach(function (p) {
      var had = base.get(p.key).has(role.id);
      var has = desired.get(p.key).has(role.id);
      if (had) before++;
      if (has) members.push({ p: p, state: had ? null : 'added' });
      else if (had) removed.push({ p: p, state: 'removed' });
    });
    members.sort(function (a, b) { return byName(a.p, b.p); });
    removed.sort(function (a, b) { return byName(a.p, b.p); });

    var count = before === members.length && !removed.length
      ? String(before) : before + ' → ' + members.length;

    var header = h('h3', {},
      h('span', { class: 'dr-dot', style: role.color ? 'background:' + role.color : null }),
      h('span', { class: 'dr-role-name' }, role.name),
      h('span', { class: 'dr-count' }, count));

    var col = h('section', { class: 'dr-column' + (locked ? ' dr-locked' : '') }, header);

    if (locked) {
      col.appendChild(h('p', { class: 'dr-locked-note' }, fmt(T.locked, { reason: role.problem })));
    } else {
      header.appendChild(h('span', { class: 'dr-column-actions' },
        h('button', { type: 'button', class: 'dr-link', onclick: function () { openPaste(role.id); } }, T.pasteList),
        h('button', { type: 'button', class: 'dr-link dr-danger', disabled: !members.length, onclick: function () {
          if (confirm(fmt(T.confirmClear, { role: role.name }))) { clearRole(role.id); commit(); }
        } }, T.clear)));
      var input = h('input', { type: 'search', placeholder: T.addPlaceholder, 'aria-label': T.addPlaceholder, autocomplete: 'off' });
      autocomplete(input, roleCandidates(role.id), function (p) { add(p.key, role.id); refocus(role.id); });
      col.appendChild(h('div', { class: 'dr-add', dataset: { role: role.id } }, input));
      dropZone(col, function (d, copy) { if (d.from !== role.id) move(d.key, d.from, role.id, copy); });
    }

    col.appendChild(h('ul', { class: 'dr-members' }, members.map(function (m) { return memberRow(m.p, role.id, m.state); })));
    if (removed.length) {
      col.appendChild(h('div', { class: 'dr-removed-section' },
        h('div', { class: 'dr-removed-label' }, fmt(T.removed, { count: removed.length })),
        h('ul', { class: 'dr-members' }, removed.map(function (m) { return memberRow(m.p, role.id, 'removed'); }))));
    }
    return col;
  }

  // Put the focus back in a column's add box after re-rendering.
  function refocus(roleId) {
    var input = root.querySelector('.dr-add[data-role="' + CSS.escape(roleId) + '"] input');
    if (input) input.focus();
  }

  function pool() {
    var list = [];
    people.forEach(function (p) {
      if (p.discord === 'external' || !inSource(p)) return;
      var any = Array.from(desired.get(p.key)).some(function (r) { return roleById.has(r); });
      if (!any) list.push(p);
    });
    list.sort(byName);

    function poolOpen() { return settings.poolOpen === null ? settings.exclusive : settings.poolOpen; }
    var details = h('details', { class: 'dr-pool', open: poolOpen(),
      // Also fires for the initial state; only remember actual changes.
      ontoggle: function () { if (details.open !== poolOpen()) { settings.poolOpen = details.open; save(); } } },
      h('summary', {}, T.pool + ' ', h('span', { class: 'dr-count' }, '(' + list.length + ')')));
    if (!list.length) details.appendChild(h('p', { class: 'dr-muted' }, T.poolEmpty));
    details.appendChild(h('ul', { class: 'dr-chips' }, list.map(function (p) {
      var assignable = canAssign(p);
      var targets = roles.filter(function (r) { return editable.has(r.id); });
      return h('li', {
        class: 'dr-chip' + (assignable ? '' : ' dr-disabled') + (filterText && matchTier(p, filterText) ? ' dr-match' : ''),
        draggable: assignable ? 'true' : null,
        title: statusNote(p),
        ondragstart: assignable ? function (e) { dragData(e, p.key, null); } : null,
      }, avatar(p), h('span', {}, p.name), assignable ? null : h('small', {}, ' · ' + statusNote(p)),
      assignable && targets.length ? h('button', { type: 'button', class: 'dr-icon dr-menu-button', title: T.menu, 'aria-label': T.menu,
        onclick: function (e) {
          showMenu(e.currentTarget, targets.map(function (r) {
            return { label: fmt(T.addTo, { role: r.name }), action: function () { add(p.key, r.id); } };
          }));
        } }, '+') : null);
    })));
    dropZone(details, function (d) { if (d.from) remove(d.key, d.from); });
    return details;
  }

  function toolbar() {
    var filter = h('input', { type: 'search', class: 'dr-filter', placeholder: T.filter, 'aria-label': T.filter, value: filterText ? filterRaw : '',
      oninput: function () {
        filterRaw = filter.value;
        filterText = normalize(filter.value);
        render();
        var again = root.querySelector('.dr-filter');
        again.focus();
        again.setSelectionRange(again.value.length, again.value.length);
      } });
    return h('div', { class: 'dr-toolbar' },
      h('label', { class: 'dr-option', title: T.exclusiveHelp },
        h('input', { type: 'checkbox', checked: settings.exclusive, onchange: function (e) { settings.exclusive = e.target.checked; commit(); } }),
        ' ' + T.exclusive),
      h('label', { class: 'dr-option' }, T.users + ' ',
        h('select', { onchange: function (e) { settings.source = e.target.value; commit(); } },
          h('option', { value: 'active', selected: settings.source === 'active' }, T.onlyActive),
          h('option', { value: 'all', selected: settings.source === 'all' }, T.allUsers))),
      filter,
      h('button', { type: 'button', onclick: function () { openPaste('*'); } }, T.pasteList),
      h('button', { type: 'button', class: 'dr-danger', onclick: function () {
        if (confirm(T.confirmClearAll)) { editable.forEach(clearRole); commit(); }
      } }, T.clearAll));
  }

  function footer() {
    var list = changes();
    var count = list.reduce(function (n, c) { return n + c.add.length + c.remove.length; }, 0);
    return h('div', { class: 'dr-footer' + (count ? ' dr-dirty' : '') },
      h('span', { class: 'dr-summary' }, count
        ? [h('strong', {}, fmt(T.summary, { changes: count, people: list.length })), ' · ' + T.savedLocally]
        : T.noChanges),
      h('button', { type: 'button', disabled: !count, onclick: function () {
        if (confirm(T.confirmDiscard)) {
          desired.forEach(function (want, key) { desired.set(key, new Set(base.get(key))); });
          commit();
        }
      } }, T.discard),
      h('button', { type: 'button', class: 'dr-primary', disabled: !count, onclick: openReview }, T.review));
  }

  function render() {
    closeMenu();
    var scroll = window.scrollY;
    root.textContent = '';
    if (!loaded) return;
    var editableRoles = roles.filter(function (r) { return editable.has(r.id); });
    if (missingRoles) root.appendChild(h('p', { class: 'dr-notice' }, fmt(T.missingRoles, { count: missingRoles })));
    if (!roles.length) {
      root.appendChild(h('p', { class: 'dr-notice' }, T.noRoles));
      return;
    }
    root.appendChild(toolbar());
    if (editableRoles.length) {
      root.appendChild(h('p', { class: 'dr-muted dr-hint' }, T.dragHint));
      root.appendChild(pool());
    }
    root.appendChild(h('div', { class: 'dr-columns' }, roles.map(column)));
    root.appendChild(footer());
    window.scrollTo(0, scroll);
  }

  // ---------------------------------------------------------------- dialogs

  function dialog(className) {
    var d = h('dialog', { class: 'dr-dialog ' + className });
    d.addEventListener('close', function () { d.remove(); });
    document.body.appendChild(d);
    d.showModal();
    return d;
  }

  function roleChip(roleId, kind) {
    var role = roleById.get(roleId);
    return h('span', { class: 'dr-role-chip dr-' + kind }, role ? role.name : roleId);
  }

  function setsEqual(a, b) {
    if (a.size !== b.size) return false;
    for (var x of a) if (!b.has(x)) return false;
    return true;
  }

  function openReview() {
    var d = dialog('dr-review');
    d.appendChild(h('h3', {}, T.reviewTitle));
    var body = h('div', {}, h('p', { class: 'dr-muted' }, T.loading));
    d.appendChild(body);

    var oldBase = base;
    var pending = changes();
    request('POST', config.urls.preview, { changes: pending }).then(function (data) {
      // People whose roles changed in Discord since the page was loaded.
      var drift = data.state.people.filter(function (p) {
        var before = oldBase.get(p.key);
        return before && !setsEqual(before, new Set(p.roles));
      });
      setState(data.state, pending);
      render();
      showPlan(d, body, data.plan, drift);
    }).catch(function (err) {
      body.textContent = '';
      body.appendChild(h('p', { class: 'dr-error' }, fmt(T.error, { error: err.message })));
      body.appendChild(h('div', { class: 'dr-dialog-buttons' }, h('button', { type: 'button', onclick: function () { d.close(); } }, T.close)));
    });
  }

  function showPlan(d, body, plan, drift) {
    body.textContent = '';
    var todo = plan.filter(function (item) { return item.status === 'change'; });
    var time = new Date().toLocaleTimeString('sv');
    body.appendChild(h('p', { class: 'dr-muted' }, fmt(T.fetchedAt, { time: time })));

    if (drift.length) {
      body.appendChild(h('div', { class: 'dr-warning' }, T.drift + ' ',
        h('strong', {}, drift.map(function (p) { return p.name; }).join(', '))));
    }

    if (!todo.length) {
      body.appendChild(h('p', {}, T.nothingToDo));
    }

    var rows = plan.map(function (item) {
      var status = item.status === 'noop' ? T.alreadyDone : item.status === 'not_in_guild' ? T.notInGuild : '';
      return h('tr', { class: item.status === 'change' ? '' : 'dr-muted', dataset: { key: item.key } },
        h('td', {}, item.name),
        h('td', {}, item.remove.map(function (r) { return roleChip(r, 'minus'); }),
          item.remove.length && item.add.length ? ' → ' : '',
          item.add.map(function (r) { return roleChip(r, 'plus'); })),
        h('td', { class: 'dr-status' }, status));
    });
    body.appendChild(h('div', { class: 'dr-table-wrap' }, h('table', {},
      h('thead', {}, h('tr', {}, h('th', {}, T.member), h('th', {}, T.change), h('th', {}))),
      h('tbody', {}, rows))));

    var progress = h('div', { class: 'dr-progress', hidden: true }, h('div', { class: 'dr-progress-bar' }, h('i', {})), h('p', { class: 'dr-muted' }));
    body.appendChild(progress);

    var buttons = h('div', { class: 'dr-dialog-buttons' });
    var back = h('button', { type: 'button', onclick: function () { d.close(); } }, todo.length ? T.back : T.close);
    buttons.appendChild(back);
    if (todo.length) {
      var confirmButton = h('button', { type: 'button', class: 'dr-primary', onclick: function () {
        confirmButton.disabled = true;
        back.disabled = true;
        applyAll(d, body, todo, progress, buttons);
      } }, T.confirm);
      buttons.appendChild(confirmButton);
    }
    body.appendChild(buttons);
  }

  function applyAll(d, body, todo, progress, buttons) {
    var byKey = new Map(changes().map(function (c) { return [c.key, c]; }));
    var queue = todo.map(function (item) { return byKey.get(item.key); }).filter(Boolean);
    var total = queue.length;
    var done = 0;
    var failed = [];
    var bar = progress.querySelector('i');
    var text = progress.querySelector('p');
    progress.hidden = false;

    // Keep the dialog open while applying, so the view can't be edited
    // underneath. If it is closed anyway, stop after the current request.
    var applying = true;
    var stopped = false;
    d.addEventListener('cancel', function (e) { if (applying) e.preventDefault(); });
    d.addEventListener('close', function () { if (applying) stopped = true; });

    function show(waitSeconds) {
      bar.style.width = (total ? 100 * (done + failed.length) / total : 100) + '%';
      var msg = fmt(T.applying, { done: done, total: total });
      if (waitSeconds) msg += ' (' + fmt(T.waiting, { seconds: waitSeconds.toFixed(1) }) + ')';
      text.textContent = msg;
    }

    function step() {
      if (stopped) return finish();
      show(0);
      if (!queue.length) return finish();
      request('POST', config.urls.apply, { changes: queue }).then(function (data) {
        data.results.forEach(function (r) {
          if (r.status === 'error' || r.status === 'not_in_guild') {
            failed.push({ key: r.key, message: r.message || T.notInGuild });
          } else {
            done++;
            // Applied: no longer pending. Otherwise a later change in Discord
            // could make it show up as pending again after the final reload.
            var c = byKey.get(r.key);
            var had = base.get(r.key);
            c.add.forEach(function (role) { had.add(role); });
            c.remove.forEach(function (role) { had.delete(role); });
          }
        });
        save();
        var remaining = new Set(data.remaining);
        queue = queue.filter(function (c) { return remaining.has(c.key); });
        if (queue.length && data.retry_after) {
          show(data.retry_after);
          setTimeout(step, data.retry_after * 1000 + 100);
        } else {
          step();
        }
      }).catch(function (err) {
        queue.forEach(function (c) { failed.push({ key: c.key, message: err.message }); });
        queue = [];
        finish();
      });
    }

    function finish() {
      applying = false;
      if (stopped) {
        load();
        return;
      }
      bar.style.width = '100%';
      text.textContent = fmt(T.applied, { done: done, total: total });
      if (failed.length) {
        progress.appendChild(h('div', { class: 'dr-error' }, T.failed, h('ul', {}, failed.map(function (f) {
          var p = people.get(f.key);
          return h('li', {}, (p ? p.name : f.key) + ': ' + f.message);
        }))));
      }
      buttons.textContent = '';
      buttons.appendChild(h('button', { type: 'button', class: 'dr-primary', onclick: function () { d.close(); } }, T.close));
      // Reload so that what was applied becomes the new base; whatever failed
      // stays as a pending change.
      load();
    }

    step();
  }

  // ---------------------------------------------------------------- paste import

  var pastePicks = new Map(); // "role|normalized line" -> person key or 'skip'

  function parsePaste(text, target) {
    var entries = [];
    var section = target === '*' ? null : target;
    var headingSeen = target !== '*';
    // Lines, and cells within them: lists copied from a spreadsheet are
    // tab-separated, read row by row.
    var cells = [];
    text.split(/\r?\n/).forEach(function (line) { cells.push.apply(cells, line.split('\t')); });
    cells.forEach(function (cell) {
      var clean = cell.trim()
        .replace(/^(?:[-*•–—]|\d+[.)])\s*/, '')
        .replace(/\([^)]*\)|\[[^\]]*\]|\{[^}]*\}/g, '')
        .trim();
      if (!clean) return;
      if (target === '*') {
        var heading = clean.replace(/:\s*$/, '').trim();
        var role = roles.find(function (r) { return editable.has(r.id) && normalize(r.name) === normalize(heading); });
        if (role || /:\s*$/.test(clean)) {
          section = role ? role.id : null;
          headingSeen = true;
          entries.push({ type: 'heading', role: section, text: heading });
          return;
        }
      }
      clean.split(/[,;]/).forEach(function (part) {
        part = part.trim();
        if (part) entries.push({ type: 'name', role: section, text: part, orphan: !headingSeen });
      });
    });
    return entries;
  }

  // Find the person a pasted line means. Prefers people in the chosen user
  // list; picks automatically only when one person matches best, and not
  // when that match is only part of a name ("Alt" in "Walter") or misses the
  // first name: that is offered as an uncertain match instead.
  function resolveLine(entry) {
    var pickKey = entry.role + '|' + normalize(entry.text);
    var picked = pastePicks.get(pickKey);
    if (picked === 'skip') return { status: 'skip', pickKey: pickKey };
    if (picked && people.has(picked)) return { status: 'picked', person: people.get(picked), pickKey: pickKey };

    var results = search(entry.text);
    var pool = results.filter(function (r) { return r.inSource; });
    if (!pool.length) pool = results;
    if (!pool.length) return { status: 'none', pickKey: pickKey };
    var bestTier = Math.min.apply(null, pool.map(function (r) { return r.tier; }));
    var best = pool.filter(function (r) { return r.tier === bestTier; });
    if (bestTier === 3 || bestTier === 5) {
      return { status: 'uncertain', candidates: best.map(function (r) { return r.person; }), pickKey: pickKey };
    }
    if (best.length === 1) {
      var others = results.filter(function (r) { return r.tier <= bestTier && r.person !== best[0].person; });
      return { status: 'auto', person: best[0].person, pickKey: pickKey, note: others.length ? T.onlyActiveMatch : null };
    }
    return { status: 'ambiguous', candidates: best.map(function (r) { return r.person; }), pickKey: pickKey };
  }

  // Apply the paste to a copy of the desired state and return the copy.
  function simulatePaste(entries, target, replace) {
    var result = new Map();
    desired.forEach(function (want, key) { result.set(key, new Set(want)); });

    var targets = new Set(target === '*' ? [] : [target]);
    var listed = new Map(); // role -> Set of keys
    var listedRoles = new Map(); // key -> Set of roles they're listed in
    entries.forEach(function (e) {
      if (e.type === 'heading' && e.role) targets.add(e.role);
      if (e.type !== 'name' || !e.role || !e.person || e.status === 'duplicate' || !canAssign(e.person)) return;
      if (!listed.has(e.role)) listed.set(e.role, new Set());
      listed.get(e.role).add(e.person.key);
      if (!listedRoles.has(e.person.key)) listedRoles.set(e.person.key, new Set());
      listedRoles.get(e.person.key).add(e.role);
    });

    if (replace) {
      targets.forEach(function (roleId) {
        var keep = listed.get(roleId) || new Set();
        result.forEach(function (want, key) { if (!keep.has(key)) want.delete(roleId); });
      });
    }
    listed.forEach(function (keys, roleId) {
      keys.forEach(function (key) { addTo(result.get(key), roleId, listedRoles.get(key)); });
    });
    return result;
  }

  function openPaste(initialTarget) {
    var d = dialog('dr-paste');
    var target = initialTarget;
    var replace = target === '*';
    var editing = new Set(); // pickKeys whose row shows a search box

    var targetSelect = h('select', { onchange: function () { target = targetSelect.value; update(); } },
      h('option', { value: '*', selected: target === '*' }, T.wholeView),
      roles.filter(function (r) { return editable.has(r.id); }).map(function (r) {
        return h('option', { value: r.id, selected: target === r.id }, r.name);
      }));
    var modeName = 'dr-paste-mode-' + Date.now();
    var replaceRadio = h('input', { type: 'radio', name: modeName, checked: replace, onchange: function () { replace = true; update(); } });
    var addRadio = h('input', { type: 'radio', name: modeName, checked: !replace, onchange: function () { replace = false; update(); } });
    var textarea = h('textarea', { rows: 14, 'aria-label': T.pasteTitle, oninput: debounce(update, 150) });
    var table = h('tbody');
    var status = h('span', { class: 'dr-muted' });
    var applyButton = h('button', { type: 'button', class: 'dr-primary', onclick: doApply }, T.pasteApply);
    var skipAllButton = h('button', { type: 'button', class: 'dr-link', hidden: true, onclick: function () {
      current.forEach(function (e) { if (unsure(e)) pastePicks.set(e.pickKey, 'skip'); });
      update();
    } }, T.skipUnmatched);
    var current = [];

    d.appendChild(h('h3', {}, T.pasteTitle));
    d.appendChild(h('div', { class: 'dr-toolbar' },
      h('label', { class: 'dr-option' }, T.target + ' ', targetSelect),
      h('label', { class: 'dr-option' }, replaceRadio, ' ' + T.replace),
      h('label', { class: 'dr-option' }, addRadio, ' ' + T.addOnly)));
    d.appendChild(h('p', { class: 'dr-muted' }, T.pasteHelp));
    d.appendChild(h('div', { class: 'dr-paste-grid' }, textarea,
      h('div', { class: 'dr-table-wrap' }, h('table', {},
        h('thead', {}, h('tr', {}, h('th', {}), h('th', {}, T.line), h('th', {}, T.interpretation))),
        table))));
    d.appendChild(h('div', { class: 'dr-dialog-buttons' }, status,
      skipAllButton, h('button', { type: 'button', onclick: function () { d.close(); } }, T.cancel), applyButton));
    textarea.focus();

    function pick(pickKey, key) {
      pastePicks.set(pickKey, key);
      editing.delete(pickKey);
      update();
    }

    function update() {
      var entries = parsePaste(textarea.value, target);
      var seen = new Map(); // role -> Set of keys
      entries.forEach(function (e) {
        if (e.type !== 'name' || !e.role) return;
        Object.assign(e, resolveLine(e));
        if (e.person) {
          if (!seen.has(e.role)) seen.set(e.role, new Set());
          if (seen.get(e.role).has(e.person.key)) e.status = 'duplicate';
          seen.get(e.role).add(e.person.key);
        }
      });
      current = entries;
      var after = simulatePaste(entries, target, replace);

      // "SG1 · 2 added, 3 removed", and who would be removed: with "Replace
      // members", that includes everyone the list doesn't match.
      function summary(roleId) {
        var added = 0, removed = [];
        desired.forEach(function (want, key) {
          var has = after.get(key).has(roleId);
          if (has && !want.has(roleId)) added++;
          if (!has && want.has(roleId)) removed.push(people.get(key));
        });
        removed.sort(byName);
        return [roleById.get(roleId).name + ' · ' + fmt(T.sectionSummary, { added: added, removed: removed.length }),
          removed.length ? h('div', { class: 'dr-removes' }, fmt(T.removesNames, {
            names: removed.map(function (p) { return p.name; }).join(', ') })) : null];
      }

      table.textContent = '';
      if (target !== '*' && entries.length) {
        table.appendChild(h('tr', { class: 'dr-section' }, h('td', { colspan: 3 }, summary(target))));
      }
      var unresolved = 0;
      entries.forEach(function (e) {
        if (e.type === 'heading') {
          table.appendChild(h('tr', { class: 'dr-section' + (e.role ? '' : ' dr-bad') },
            h('td', { colspan: 3 }, e.role ? summary(e.role) : e.text + ': ' + T.unknownRole)));
          return;
        }
        if (!e.role) {
          if (e.orphan) unresolved++;
          table.appendChild(row('✗', 'dr-bad', e.text, e.orphan ? T.noSection : T.unknownRole));
          return;
        }
        if (editing.has(e.pickKey) || e.status === 'none') {
          if (e.status === 'none') unresolved++;
          var input = h('input', { type: 'search', placeholder: T.search, autocomplete: 'off' });
          autocomplete(input, function (q) {
            return search(q).map(function (res) {
              return { person: res.person, note: statusNote(res.person) || (res.inSource ? null : T.notActive), disabled: !canAssign(res.person) };
            });
          }, function (p) { pick(e.pickKey, p.key); });
          table.appendChild(row(e.status === 'none' ? '✗' : '?', e.status === 'none' ? 'dr-bad' : 'dr-unsure', e.text,
            [h('span', { class: 'dr-add' }, input), ' ', skipButton(e)]));
          return;
        }
        if (e.status === 'skip') {
          table.appendChild(row('–', 'dr-muted', e.text, [T.skipped + ' ',
            h('button', { type: 'button', class: 'dr-link', onclick: function () { pastePicks.delete(e.pickKey); update(); } }, T.undo)]));
          return;
        }
        if (e.status === 'ambiguous' || e.status === 'uncertain') {
          unresolved++;
          var select = h('select', { onchange: function () { pick(e.pickKey, select.value); } },
            h('option', { value: '' }, e.status === 'uncertain' ? T.uncertain : fmt(T.choose, { count: e.candidates.length })),
            e.candidates.map(function (p) {
              var note = statusNote(p);
              return h('option', { value: p.key, disabled: !canAssign(p) }, p.name + (p.nickname ? ' "' + p.nickname + '"' : '') + (note ? ' (' + note + ')' : ''));
            }),
            h('option', { value: 'skip' }, T.skip));
          table.appendChild(row('?', 'dr-unsure', e.text, select));
          return;
        }
        var p = e.person;
        if (e.status === 'duplicate') {
          table.appendChild(row('=', 'dr-muted', e.text, [fmt(T.duplicate, { name: p.name }) + ' ', changeButton(e)]));
          return;
        }
        if (!canAssign(p)) {
          table.appendChild(row('–', 'dr-muted', e.text, [p.name + ': ' + statusNote(p) + ' ', changeButton(e)]));
          return;
        }
        var notes = [];
        if (desired.get(p.key).has(e.role)) notes.push(T.alreadyIn);
        var from = Array.from(desired.get(p.key)).filter(function (r) { return r !== e.role && editable.has(r) && !after.get(p.key).has(r); });
        if (from.length) notes.push(fmt(T.movesFrom, { roles: roleNames(from) }));
        if (e.note) notes.push(e.note);
        table.appendChild(row('✓', 'dr-good', e.text, [p.name, notes.length ? h('span', { class: 'dr-muted' }, ' (' + notes.join(', ') + ')') : null, ' ', changeButton(e)]));
      });

      status.textContent = unresolved ? fmt(T.needsChoice, { count: unresolved }) : '';
      skipAllButton.hidden = !entries.some(unsure);
      applyButton.disabled = unresolved > 0 || !entries.some(function (e) { return e.type === 'name'; });
    }

    function row(symbol, cls, text, content) {
      return h('tr', {}, h('td', { class: 'dr-symbol ' + cls }, symbol), h('td', { class: 'dr-line' }, text), h('td', {}, content));
    }

    // Lines with no match, or only an uncertain one.
    function unsure(e) {
      return e.status === 'none' || e.status === 'uncertain';
    }

    function changeButton(e) {
      return h('button', { type: 'button', class: 'dr-link', onclick: function () { editing.add(e.pickKey); update(); } }, T.edit);
    }

    function skipButton(e) {
      return h('button', { type: 'button', class: 'dr-link', onclick: function () { pick(e.pickKey, 'skip'); } }, T.skip);
    }

    function doApply() {
      // The table updates shortly after typing; don't apply a stale version.
      update();
      if (applyButton.disabled) return;
      desired = simulatePaste(current, target, replace);
      d.close();
      commit();
    }
  }

  function debounce(fn, ms) {
    var t;
    return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }

  // ---------------------------------------------------------------- start

  function load() {
    return request('GET', config.urls.state).then(function (data) {
      var stored = storageGet();
      if (!loaded) {
        settings.exclusive = data.view.exclusive;
        if (stored.settings) {
          if (stored.settings.source) settings.source = stored.settings.source;
          if (stored.settings.poolOpen !== undefined) settings.poolOpen = stored.settings.poolOpen;
        }
      }
      var pending = loaded ? changes() : (stored.changes || []);
      setState(data, pending);
      save();
      render();
    }).catch(function (err) {
      root.textContent = '';
      root.appendChild(h('p', { class: 'dr-error' }, fmt(T.error, { error: err.message })));
    });
  }

  root.appendChild(h('p', { class: 'dr-muted' }, T.loading));
  load();
})();
