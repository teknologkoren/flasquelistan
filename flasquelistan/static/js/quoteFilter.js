// Live filtering of the quote list. All quotes are already on the page, so
// this only shows and hides cards; what matches is decided in
// quoteFilterCore.js. The query is mirrored to ?q= so searches can be
// shared and survive reloads.

// How long typing must pause before the URL is updated. Safari throws if
// history.replaceState is called too often (about 100 times in 30 s).
var URL_UPDATE_DELAY_MS = 300;

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
  var urlTimer = null;

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
    clearTimeout(urlTimer);
    urlTimer = null;
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

  // Set the input from ?q= and filter. On load this overrides whatever the
  // browser restored into the input; on Back/Forward the script doesn't run
  // again, so it has to be done here too.
  function readUrl() {
    clearTimeout(urlTimer);
    urlTimer = null;
    input.value = new URL(window.location.href).searchParams.get("q") || "";
    apply();
  }

  function reset() {
    input.value = "";
    apply();
    updateUrl();
  }

  input.addEventListener("input", function () {
    apply();
    clearTimeout(urlTimer);
    urlTimer = setTimeout(updateUrl, URL_UPDATE_DELAY_MS);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && input.value) {
      e.preventDefault();
      reset();
    }
  });

  clear.addEventListener("click", function () {
    reset();
    input.focus();
  });

  window.addEventListener("popstate", readUrl);

  // Leaving within the delay: write the URL now, or Back would bring the
  // page back from the browser's cache, filtered, under a URL without ?q=.
  window.addEventListener("pagehide", function () {
    if (urlTimer !== null) {
      updateUrl();
    }
  });

  readUrl();
  box.hidden = false;

  // Revealing the box moved the page down, so a permalink (/quotes/#quote-N)
  // the browser already scrolled to is now off by the box's height.
  var target = /^#quote-\d+$/.test(window.location.hash) &&
    document.getElementById(window.location.hash.slice(1));
  if (target && !target.hidden) {
    target.scrollIntoView();
  }
}

quoteFilter();
