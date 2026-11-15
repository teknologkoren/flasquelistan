// The parts of the Discord role editor (discordRoles.js) that don't touch the
// page: name matching, paste parsing and the role bookkeeping. Kept separate
// so they can be tested with Node: tests/js/discord_roles_core.test.js.
//
// Role sets are Maps from a person's key to a Set of role ids. "base" is who
// has which role in Discord, "desired" is what the admin wants.
var DiscordRolesCore = (function () {
  'use strict';

  function byName(a, b) { return a.name.localeCompare(b.name, 'sv'); }

  // Who can be given a role: Discord members, with or without a Streque
  // account. Not people without a linked Discord account, or who have left
  // the server.
  function canAssign(p) {
    return p.discord === 'linked' || p.discord === 'external';
  }

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

  // Precompute the normalized names that matchTier compares with.
  function indexPerson(p) {
    p._full = normalize(p.first_name + ' ' + p.last_name) || normalize(p.name);
    p._first = normalize(p.first_name);
    p._nick = normalize(p.nickname);
    p._words = (p._full + ' ' + p._nick).split(/[\s-]+/).filter(Boolean);
    p._firstWords = (p._first + ' ' + p._nick).split(/[\s-]+/).filter(Boolean);
    return p;
  }

  // q must be normalized.
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

  // Streque users matching the query, best first; people in the chosen user
  // list (inSource(person) is true) before the rest.
  function search(people, query, inSource) {
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

  // ---------------------------------------------------------------- role sets

  // The pending changes: [{key, add: [role ids], remove: [role ids]}].
  function changes(base, desired) {
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

  // The desired state: base with the pending changes on top. Changes to
  // people who are gone or can't be assigned, or to roles that can't be
  // edited, are dropped.
  function rebase(people, base, pending, editable) {
    var desired = new Map();
    base.forEach(function (roles, key) { desired.set(key, new Set(roles)); });
    (pending || []).forEach(function (c) {
      var p = people.get(c.key);
      if (!p || !canAssign(p)) return;
      var want = desired.get(c.key);
      c.add.forEach(function (r) { if (editable.has(r)) want.add(r); });
      c.remove.forEach(function (r) { if (editable.has(r)) want.delete(r); });
    });
    return desired;
  }

  // Add a role to a person's set. In exclusive mode, also remove the view's
  // other editable roles, except those in keep.
  function addTo(want, roleId, editable, exclusive, keep) {
    if (exclusive) {
      editable.forEach(function (r) {
        if (r !== roleId && !(keep && keep.has(r))) want.delete(r);
      });
    }
    want.add(roleId);
  }

  // ---------------------------------------------------------------- paste import

  // Split a pasted list into headings and names. target is a role id, or '*'
  // for the whole view, where a line with a role's name is a heading for the
  // lines below it. roles are the editable roles ({id, name}).
  function parsePaste(text, target, roles) {
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
        var role = roles.find(function (r) { return normalize(r.name) === normalize(heading); });
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

  // Find the person a pasted line means. picks maps "role|normalized line"
  // to a person key or 'skip' (choices made by the admin); searchFn(text)
  // returns search() results. Prefers people in the chosen user list; picks
  // automatically only when one person matches best, and not when that match
  // is only part of a name ("Alt" in "Walter") or misses the first name: that
  // is offered as an uncertain match instead. onlyInSource means others
  // outside the chosen user list matched as well.
  function resolveLine(entry, picks, people, searchFn) {
    var pickKey = entry.role + '|' + normalize(entry.text);
    var picked = picks.get(pickKey);
    if (picked === 'skip') return { status: 'skip', pickKey: pickKey };
    if (picked && people.has(picked)) return { status: 'picked', person: people.get(picked), pickKey: pickKey };

    var results = searchFn(entry.text);
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
      return { status: 'auto', person: best[0].person, pickKey: pickKey, onlyInSource: others.length > 0 };
    }
    return { status: 'ambiguous', candidates: best.map(function (r) { return r.person; }), pickKey: pickKey };
  }

  // Apply resolved paste entries to a copy of desired and return the copy.
  // With replace, everyone not listed is removed from the pasted roles.
  function simulatePaste(entries, desired, target, replace, editable, exclusive) {
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
      keys.forEach(function (key) { addTo(result.get(key), roleId, editable, exclusive, listedRoles.get(key)); });
    });
    return result;
  }

  return {
    byName: byName,
    canAssign: canAssign,
    normalize: normalize,
    indexPerson: indexPerson,
    matchTier: matchTier,
    search: search,
    changes: changes,
    rebase: rebase,
    addTo: addTo,
    parsePaste: parsePaste,
    resolveLine: resolveLine,
    simulatePaste: simulatePaste,
  };
})();

if (typeof module === 'object' && module.exports) module.exports = DiscordRolesCore;
