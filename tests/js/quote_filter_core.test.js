// Unit tests for the quote search's matching. Run with:
//   node --test 'tests/js/*.test.js'
// Uses only Node's built-in test runner; no dependencies.
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../../flasquelistan/static/js/quoteFilterCore.js');

// [id, text, who, when], like the fields of a card on the page.
const QUOTES = [
  [1, 'Kom igen, testa citaten, det blir kul!', 'Någon, om Strequelistan',
    '02 november 2016, 18:00'],
  [3, 'much quote, such fun', 'shibe', '07 oktober 2025, 06:00'],
  [33, 'Mer ÖL åt\nkören!', 'Kålle', '\n      14 maj 2023, 21:30\n    '],
  [339, 'Glögg är gott', null, 'före tidens början...'],
].map(([id, ...fields]) => core.indexQuote(id, fields));

function search(raw) {
  const query = core.parseQuery(raw);
  return QUOTES.filter((q) => core.matches(q, query)).map((q) => q.id);
}

test('normalize ignores case and accents, and collapses whitespace', () => {
  assert.equal(core.normalize('  Mer ÖL åt\n\tkören! '), 'mer ol at koren!');
  assert.equal(core.normalize('Ångström'), 'angstrom');
});

test('an empty or blank query matches everything', () => {
  assert.equal(core.parseQuery(''), null);
  assert.equal(core.parseQuery('   '), null);
  assert.deepEqual(search(''), [1, 3, 33, 339]);
});

test('matches part of a word, ignoring case and accents', () => {
  assert.deepEqual(search('GLÖ'), [339]);
  assert.deepEqual(search('glo'), [339]);
  assert.deepEqual(search('kören'), [33]);
  assert.deepEqual(search('koren'), [33]);
});

test('the query is one phrase: word order matters', () => {
  assert.deepEqual(search('much quote'), [3]);
  assert.deepEqual(search('quote much'), []);
  assert.deepEqual(search('such fun'), [3]);
  assert.deepEqual(search('much fun'), []);
});

test('whitespace in the query and the quote is collapsed, also across lines', () => {
  assert.deepEqual(search('åt kören'), [33]);
  assert.deepEqual(search('åt   kören'), [33]);
  assert.deepEqual(search('  much quote  '), [3]);
});

test('matches the author', () => {
  assert.deepEqual(search('shibe'), [3]);
  assert.deepEqual(search('kalle'), [33]);
});

test('a phrase does not run from one field into the next', () => {
  // End of the text followed by the start of the author.
  assert.deepEqual(search('fun shibe'), []);
  assert.deepEqual(search('kul! nagon'), []);
});

test('matches the date as it is shown', () => {
  assert.deepEqual(search('oktober 2025'), [3]);
  assert.deepEqual(search('14 maj'), [33]);
  assert.deepEqual(search('2016'), [1]);
  assert.deepEqual(search('tidens början'), [339]);
});

test('#N matches exactly that quote number', () => {
  assert.deepEqual(core.parseQuery('#3'), { id: 3 });
  assert.deepEqual(search('#3'), [3]);
  assert.deepEqual(search('#33'), [33]);
  assert.deepEqual(search(' #339 '), [339]);
  assert.deepEqual(search('#03'), [3]);
  assert.deepEqual(search('#4711'), []);
});

test('anything else with # is an ordinary phrase', () => {
  assert.deepEqual(core.parseQuery('#'), { phrase: '#' });
  assert.deepEqual(core.parseQuery('#3 fun'), { phrase: '#3 fun' });
  assert.deepEqual(search('#3 fun'), []);
});

test('quotes without an author are indexed fine', () => {
  assert.deepEqual(QUOTES.find((q) => q.id === 339).fields,
    ['glogg ar gott', 'fore tidens borjan...']);
});
