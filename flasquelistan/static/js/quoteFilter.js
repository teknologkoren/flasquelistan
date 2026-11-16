// Live filtering of the quote list. All quotes are already on the page, so
// this only shows and hides cards; what matches is decided in
// quoteFilterCore.js. The query is mirrored to ?q= so searches can be
// shared and survive reloads.

function quoteFilter() {
  var core = QuoteFilterCore;
  var box = document.getElementById("quote-filter-box");
  if (!box) {
    return;  // no quotes on the page
  }

  var input = document.getElementById("quote-filter");
  var clear = document.getElementById("clear-quote-filter");
  var status = document.getElementById("quote-filter-status");
  var empty = document.getElementById("quote-filter-empty");

  // Index each card once, not on every keystroke.
  var entries = Array.prototype.map.call(
    document.querySelectorAll(".quote.card"),
    function (card) {
      var fields = [".quote-text", ".quote-who", ".quote-when"].map(
        function (sel) {
          var el = card.querySelector(sel);
          return el ? el.textContent : "";
        });
      var entry = core.indexQuote(
        parseInt(card.id.replace(/^quote-/, ""), 10), fields);
      entry.card = card;
      return entry;
    }
  );

  function apply() {
    var query = core.parseQuery(input.value);
    var shown = 0;

    entries.forEach(function (entry) {
      var match = core.matches(entry, query);
      entry.card.hidden = !match;
      if (match) {
        shown++;
      }
    });

    if (query) {
      status.textContent = status.dataset.template
        .replace("{shown}", shown)
        .replace("{total}", entries.length);
    } else {
      status.textContent = "";
    }
    empty.hidden = shown > 0;
  }

  function updateUrl() {
    var url = new URL(window.location.href);
    if (input.value.trim()) {
      url.searchParams.set("q", input.value);
    } else {
      url.searchParams.delete("q");
    }
    // The filter now decides what's on screen, so drop any #quote-N anchor.
    url.hash = "";
    window.history.replaceState(null, "", url);
  }

  function reset() {
    input.value = "";
    apply();
    updateUrl();
  }

  // Make a permalink (/quotes/#quote-N) land on its quote: if the filter
  // hides that quote, show everything instead. With alwaysScroll, scroll even
  // when it was visible, since revealing the search box moves the page down.
  function revealHashTarget(alwaysScroll) {
    var target = window.location.hash && document.getElementById(
      decodeURIComponent(window.location.hash.slice(1)));
    if (!target) {
      return;
    }
    if (target.hidden) {
      reset();
    } else if (alwaysScroll !== true) {
      return;
    }
    target.scrollIntoView();
  }

  input.addEventListener("input", function () {
    apply();
    updateUrl();
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      e.preventDefault();
      reset();
    }
  });

  clear.addEventListener("click", function () {
    reset();
    input.focus();
  });

  window.addEventListener("hashchange", revealHashTarget);

  // ?q= is the source of truth on load, overriding whatever the browser
  // restored into the input.
  input.value = new URL(window.location.href).searchParams.get("q") || "";
  apply();
  box.hidden = false;
  revealHashTarget(true);
}

quoteFilter();
