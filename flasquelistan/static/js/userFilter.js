class NormalizedRegExp extends RegExp {
  test(str) {
    return super.test(str)
      // separate diacritics from "regular" chars, remove diacritics, and test again.
      // If there are symbols in the str, they will be removed too. Thus, inputing
      // a string with a symbol, as well as a regular char where there *should* be a
      // char with diacritic, will not match. This is considered a bug, but is
      // wontfix for now as that is a rare edgecase.
      || super.test(str.normalize("NFKD").replace(/[^A-Za-z]/g, ""));
  }
}

function escapeRegexp(s) {
  return s.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&");
}

function testPhone(input, phonenumber) {
  var e164input = input.replace(/\s/g, "").replace(/^0/, "+46");
  var re = new RegExp(escapeRegexp(e164input));
  return re.test(phonenumber);
}

function doFilter() {
  if (!this.value) {
    // for some reason, if you set filter.value = ""; outside this function,
    // it becomes undefined instead of empty string.
    this.value = "";
  }
  var re = new NormalizedRegExp(escapeRegexp(this.value), "i");
  var groups = document.getElementsByClassName("group");

  for (var i = 0; i < groups.length; i++) {
    var cards = groups[i].getElementsByClassName("usercard");
    var matches = [];

    for (var j = 0; j < cards.length; j++) {
      var nameEl = cards[j].querySelector(".username");
      var fullName = nameEl.dataset.firstname + " " + nameEl.dataset.lastname;

      if (re.test(fullName) || re.test(nameEl.dataset.nickname) || testPhone(this.value, nameEl.dataset.phonenumber)) {
        cards[j].style.display = "";
        matches.push(cards[j]);
      } else {
        cards[j].style.display = "none";
      }
    }

    if (matches.length > 0) {
      groups[i].style.display = "";
    } else {
      groups[i].style.display = "none";
    }
  }
}

function userFilter() {
  var filter = document.getElementById("user-filter");
  filter.addEventListener("input", doFilter);
}

function clearFilter() {
  var filter = document.getElementById("user-filter");
  var clear = document.getElementById("clear-filter");
  clear.addEventListener("click", function () {
    filter.value = "";
    filter.placeholder = "Namn";
    doFilter();
  })
}

userFilter();
clearFilter();

