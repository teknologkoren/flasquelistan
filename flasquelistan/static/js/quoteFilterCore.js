// The parts of the quote search (quoteFilter.js) that don't touch the page:
// normalizing text and deciding whether a quote matches a query. Kept
// separate so they can be tested with Node: tests/js/quote_filter_core.test.js.
//
// Matching works like the browser's find (Ctrl+F): the query is one phrase,
// found anywhere in the quote's text, author or date, with case, accents
// and runs of whitespace ignored. A query like "#3" is a quote number
// instead, and matches quote 3 only.
var QuoteFilterCore = (function () {
  'use strict';

  // Lowercase, strip accents ("Öl" -> "ol") and collapse whitespace, the
  // same way for the query and the quotes so they compare like for like.
  function normalize(s) {
    return s.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
      .replace(/\s+/g, ' ').trim();
  }

  // The searchable form of a quote. Fields are kept apart so a phrase can't
  // match across them, e.g. the end of the text and the start of the author.
  function indexQuote(id, fields) {
    return {
      id: id,
      fields: fields.filter(Boolean).map(normalize),
    };
  }

  // null for an empty query (everything matches), {id} for "#N", otherwise
  // {phrase}.
  function parseQuery(raw) {
    var q = normalize(raw);
    if (!q) {
      return null;
    }
    var m = /^#(\d+)$/.exec(q);
    if (m) {
      return {id: parseInt(m[1], 10)};
    }
    return {phrase: q};
  }

  function matches(entry, query) {
    if (query === null) {
      return true;
    }
    if (query.id !== undefined) {
      return entry.id === query.id;
    }
    return entry.fields.some(function (f) {
      return f.indexOf(query.phrase) !== -1;
    });
  }

  return {
    normalize: normalize,
    indexQuote: indexQuote,
    parseQuery: parseQuery,
    matches: matches,
  };
})();

if (typeof module === 'object' && module.exports) module.exports = QuoteFilterCore;
