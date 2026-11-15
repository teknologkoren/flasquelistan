// Unit tests for the Discord role editor's logic. Run with:
//   node --test tests/js/
// Uses only Node's built-in test runner; no dependencies.
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../../flasquelistan/static/js/discordRolesCore.js');

function person(key, first, last, extra = {}) {
  return core.indexPerson({
    key, first_name: first, last_name: last, name: `${first} ${last}`,
    nickname: '', active: true, discord: 'linked', ...extra,
  });
}

const PEOPLE = [
  person('anna', 'Anna', 'Andersson', { nickname: 'Majsan' }),
  person('annab', 'Anna', 'Berg'),
  person('kalle', 'Kalle', 'Karlsson'),
  person('karl', 'Karl', 'Berg', { nickname: 'Kalle' }),
  person('bligh', 'Bligh', 'Walter'),
  person('hilma', 'Hilma', 'Lampa'),
  person('lage', 'Lage', 'Linusson'),
  person('karin', 'Karin', 'Berg'),
  person('asa', 'Åsa', 'Öberg'),
  person('annak', 'Anna-Karin', 'Ek'),
  person('old', 'Olle', 'Gammal', { active: false }),
  person('unlinked', 'Ulla', 'Udd', { discord: 'unlinked' }),
  person('ext', '', '', { name: 'Old bass', discord: 'external' }),
];
const PEOPLE_MAP = new Map(PEOPLE.map((p) => [p.key, p]));
const byKey = (key) => PEOPLE_MAP.get(key);
const tier = (key, query) => core.matchTier(byKey(key), core.normalize(query));
const activeOnly = (p) => p.active;
const searchFn = (q) => core.search(PEOPLE_MAP, q, activeOnly);
const sets = (obj) => new Map(Object.entries(obj).map(([k, v]) => [k, new Set(v)]));
const plain = (map) => Object.fromEntries([...map].map(([k, v]) => [k, [...v].sort()]));

test('normalize ignores case, accents and punctuation', () => {
  assert.equal(core.normalize('  Åsa  ÖBERG!  '), 'asa oberg');
  assert.equal(core.normalize('Anna-Karin'), 'anna-karin');
  assert.equal(core.normalize(null), '');
});

test('tier 1: full name, first name or nickname', () => {
  assert.equal(tier('anna', 'Anna Andersson'), 1);
  assert.equal(tier('anna', 'anna'), 1);
  assert.equal(tier('anna', 'Majsan'), 1);
  assert.equal(tier('asa', 'asa oberg'), 1);
});

test('tier 2: every word starts a different word of the name', () => {
  assert.equal(tier('anna', 'Anna A'), 2);
  assert.equal(tier('anna', 'And Ann'), 2);
  assert.equal(tier('annak', 'Anna Karin Ek'), 2);
  // "Anna A" needs two different words: Anna Berg has no word starting with "a" left.
  assert.equal(tier('annab', 'Anna A'), 0);
});

test('tier 3: part of a name', () => {
  assert.equal(tier('bligh', 'Alt'), 3);
  assert.equal(tier('anna', 'ndersson'), 3);
});

test('tier 4 and 5: all but one of three words', () => {
  // Extra middle name, second surname, a note after the name.
  assert.equal(tier('hilma', 'Hilma Ådén Lampa'), 4);
  assert.equal(tier('lage', 'Lage Linusson-Hahn'), 4);
  assert.equal(tier('hilma', 'Hilma Lampa M'), 4);
  // The first word doesn't match.
  assert.equal(tier('karin', 'Anna Karin Berg'), 5);
  // Two words, one wrong: no match.
  assert.equal(tier('lage', 'Lage Hahn'), 0);
});

test('search: skips external members, chosen list first, then tier, then name', () => {
  const results = core.search(PEOPLE_MAP, 'berg', activeOnly);
  assert.deepEqual(results.map((r) => r.person.key), ['annab', 'karin', 'karl', 'asa']);
  assert.ok(!core.search(PEOPLE_MAP, 'old bass', activeOnly).length);
  const olle = core.search(PEOPLE_MAP, 'olle', activeOnly)[0];
  assert.equal(olle.person.key, 'old');
  assert.equal(olle.inSource, false);
});

test('resolveLine: automatic, ambiguous, uncertain, none', () => {
  const resolve = (text) => core.resolveLine({ role: 'sg1', text }, new Map(), PEOPLE_MAP, searchFn);

  assert.equal(resolve('Majsan').person.key, 'anna');
  assert.equal(resolve('Majsan').status, 'auto');
  // "Kalle" is Kalle Karlsson's first name and Karl Berg's nickname.
  const kalle = resolve('Kalle');
  assert.equal(kalle.status, 'ambiguous');
  assert.deepEqual(kalle.candidates.map((p) => p.key).sort(), ['kalle', 'karl']);
  // Only part of a name.
  assert.equal(resolve('Alt').status, 'uncertain');
  // The first word doesn't match: offered, not picked.
  const stina = resolve('Stina Karin Berg');
  assert.equal(stina.status, 'uncertain');
  assert.deepEqual(stina.candidates.map((p) => p.key), ['karin']);
  // People whose first name does match rank above Karin Berg.
  const anna = resolve('Anna Karin Berg');
  assert.equal(anna.status, 'ambiguous');
  assert.deepEqual(anna.candidates.map((p) => p.key).sort(), ['annab', 'annak']);
  assert.equal(resolve('Hilma Ådén Lampa').status, 'auto');
  assert.equal(resolve('Nobody Atall').status, 'none');
});

test('resolveLine: prefers the chosen user list, and remembers picks', () => {
  const extra = new Map(PEOPLE_MAP);
  extra.set('olle2', person('olle2', 'Olle', 'Ny'));
  const fn = (q) => core.search(extra, q, activeOnly);
  const result = core.resolveLine({ role: 'sg1', text: 'Olle' }, new Map(), extra, fn);
  assert.equal(result.person.key, 'olle2');
  assert.equal(result.onlyInSource, true);

  const picks = new Map([['sg1|kalle', 'karl'], ['sg1|alt', 'skip']]);
  assert.equal(core.resolveLine({ role: 'sg1', text: 'Kalle' }, picks, PEOPLE_MAP, searchFn).person.key, 'karl');
  assert.equal(core.resolveLine({ role: 'sg1', text: 'Alt' }, picks, PEOPLE_MAP, searchFn).status, 'skip');
  // Picks are per role.
  assert.equal(core.resolveLine({ role: 'sg2', text: 'Kalle' }, picks, PEOPLE_MAP, searchFn).status, 'ambiguous');
});

const ROLES = [{ id: 'sg1', name: 'SG1' }, { id: 'sg2', name: 'SG2' }, { id: 'web', name: 'Webbgruppen (IT)' }];
const names = (entries) => entries.map((e) => (e.type === 'heading' ? `#${e.role}` : `${e.role}:${e.text}`));

test('parsePaste: spreadsheet cells, bullets, numbering, brackets and commas', () => {
  const text = 'Anna Andersson\tKalle Karlsson [M]\n\t\tHilma (ordf.)\n- Bligh, Lage; Karin\n2) Åsa\n• Olle {x}\n\n';
  assert.deepEqual(names(core.parsePaste(text, 'sg1', ROLES)), [
    'sg1:Anna Andersson', 'sg1:Kalle Karlsson', 'sg1:Hilma',
    'sg1:Bligh', 'sg1:Lage', 'sg1:Karin', 'sg1:Åsa', 'sg1:Olle',
  ]);
});

test('parsePaste: headings in the whole view', () => {
  const entries = core.parsePaste('Anna\nSG1:\nKalle\nsg2\nKarin\nSopraner:\nOlle', '*', ROLES);
  assert.deepEqual(names(entries), ['null:Anna', '#sg1', 'sg1:Kalle', '#sg2', 'sg2:Karin', '#null', 'null:Olle']);
  assert.equal(entries[0].orphan, true);
  assert.equal(entries[6].orphan, false);
  // With a single role as target, a role name is just a name.
  assert.deepEqual(names(core.parsePaste('SG2\nKarin', 'sg1', ROLES)), ['sg1:SG2', 'sg1:Karin']);
});

test('changes and rebase', () => {
  const base = sets({ anna: ['sg1'], kalle: [], unlinked: [], ext: ['sg2'] });
  const desired = sets({ anna: ['sg2'], kalle: ['sg1'], unlinked: [], ext: [] });
  const pending = core.changes(base, desired);
  assert.deepEqual(pending, [
    { key: 'anna', add: ['sg2'], remove: ['sg1'] },
    { key: 'kalle', add: ['sg1'], remove: [] },
    { key: 'ext', add: [], remove: ['sg2'] },
  ]);

  const editable = new Set(['sg1', 'sg2']);
  assert.deepEqual(plain(core.rebase(PEOPLE_MAP, base, pending, editable)), plain(desired));
  // Dropped: roles that can't be edited, people who can't be assigned or are gone.
  const rebased = core.rebase(PEOPLE_MAP, base, [
    { key: 'anna', add: ['locked'], remove: [] },
    { key: 'unlinked', add: ['sg1'], remove: [] },
    { key: 'gone', add: ['sg1'], remove: [] },
  ], editable);
  assert.deepEqual(plain(rebased), plain(base));
});

test('addTo: exclusive mode removes the other editable roles, except keep', () => {
  const editable = new Set(['sg1', 'sg2', 'sg3']);
  let want = new Set(['sg1', 'sg2', 'locked']);
  core.addTo(want, 'sg3', editable, false);
  assert.deepEqual([...want].sort(), ['locked', 'sg1', 'sg2', 'sg3']);

  want = new Set(['sg1', 'sg2', 'locked']);
  core.addTo(want, 'sg3', editable, true);
  assert.deepEqual([...want].sort(), ['locked', 'sg3']);

  want = new Set(['sg1', 'sg2']);
  core.addTo(want, 'sg3', editable, true, new Set(['sg1']));
  assert.deepEqual([...want].sort(), ['sg1', 'sg3']);
});

function resolved(text, target) {
  return core.parsePaste(text, target, ROLES).map((e) => {
    if (e.type !== 'name' || !e.role) return e;
    return { ...e, ...core.resolveLine(e, new Map(), PEOPLE_MAP, searchFn) };
  });
}

test('simulatePaste: add only, or replace the listed roles', () => {
  const editable = new Set(['sg1', 'sg2']);
  const desired = sets({ anna: ['sg1'], kalle: ['sg1'], karin: [], ext: ['sg1'], unlinked: [] });
  const entries = resolved('Karin Berg\nAnna Andersson\nUlla Udd', 'sg1');

  const added = core.simulatePaste(entries, desired, 'sg1', false, editable, false);
  assert.deepEqual(plain(added), { anna: ['sg1'], kalle: ['sg1'], karin: ['sg1'], ext: ['sg1'], unlinked: [] });

  // Replace: everyone not listed is removed, including external members.
  // Ulla isn't linked to Discord, so she isn't added.
  const replaced = core.simulatePaste(entries, desired, 'sg1', true, editable, false);
  assert.deepEqual(plain(replaced), { anna: ['sg1'], kalle: [], karin: ['sg1'], ext: [], unlinked: [] });
  // The input isn't changed.
  assert.deepEqual(plain(desired), { anna: ['sg1'], kalle: ['sg1'], karin: [], ext: ['sg1'], unlinked: [] });
});

test('simulatePaste: whole view, exclusive, and someone listed in two roles', () => {
  const editable = new Set(['sg1', 'sg2']);
  const desired = sets({ anna: ['sg1'], kalle: ['sg2'], karin: ['sg2'] });
  // Kalle Karlsson moves to SG1; Anna is in both; SG2 only lists Anna.
  const entries = resolved('SG1\nKalle Karlsson\nAnna Andersson\nSG2\nAnna Andersson', '*');
  const after = core.simulatePaste(entries, desired, '*', true, editable, true);
  assert.deepEqual(plain(after), { anna: ['sg1', 'sg2'], kalle: ['sg1'], karin: [] });

  // Roles without a heading are left alone when replacing.
  const only1 = core.simulatePaste(resolved('SG1\nKarin Berg', '*'), desired, '*', true, editable, false);
  assert.deepEqual(plain(only1), { anna: [], kalle: ['sg2'], karin: ['sg1', 'sg2'] });
});

test('simulatePaste: unresolved, skipped and duplicate lines add no one', () => {
  const editable = new Set(['sg1']);
  const desired = sets({ kalle: [], karl: [], bligh: [] });
  const entries = resolved('Kalle\nAlt\nNobody', 'sg1');
  entries.push({ type: 'name', role: 'sg1', text: 'x', status: 'duplicate', person: byKey('bligh') });
  const after = core.simulatePaste(entries, desired, 'sg1', false, editable, false);
  assert.deepEqual(plain(after), plain(desired));
});
