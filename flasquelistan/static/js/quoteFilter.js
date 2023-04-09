class QuoteRegExp extends RegExp {
  test(str) {
    return super.test(str);
  }

  matchAll(str) {
    const result = RegExp.prototype[Symbol.matchAll].call(this, str);

    if (result) {
      return Array.from(result);
    }
    return null;
  }
}

function escapeRegexp(s) {
  return s.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&");
}

function doFilter() {
  if (!this.value) {
    // for some reason, if you set filter.value = ""; outside this function,
    // it becomes undefined instead of empty string.
    this.value = "";
  }
  var re = new QuoteRegExp(escapeRegexp(this.value), "i");
  var cards = document.getElementsByClassName("quote");

  for (var j = 0; j < cards.length; j++) {
    var textEl = cards[j].querySelector(".quote-text").firstChild.nodeValue;
    var whoEl = cards[j].querySelector(".quote-meta").querySelector(".quote-who");
    if (whoEl) {
      whoEl = whoEl.firstChild.nodeValue;
    }
    var whenEl = cards[j].querySelector(".quote-meta").querySelector(".quote-when").firstChild.nodeValue;

    console.info(re.matchAll(textEl));
    if (re.test(textEl) || (whoEl && re.test(whoEl)) || re.test(whenEl)) {
      cards[j].style.display = "";
    } else {
      cards[j].style.display = "none";
    }
  }
}

function quoteFilter() {
  var filter = document.getElementById("quote-filter");
  filter.addEventListener("input", doFilter);
}

function clearFilter() {
  var filter = document.getElementById("quote-filter");
  var clear = document.getElementById("clear-filter");
  clear.addEventListener("click", function () {
    filter.value = "";
    filter.placeholder = "Sök citat";
    doFilter();
  })
}

quoteFilter();
clearFilter();

