class NormalizedRegExp extends RegExp {
  test(str) {                 // separate diacritics from "regular" chars, remove diacritics, and test again
    return super.test(str) || super.test(str.normalize('NFKD').replace(/[^A-Za-z]/g, ""));
  }
}

function doFilter() {
  var re = new NormalizedRegExp(this.value, "i");
  var groups = document.getElementsByClassName("group");

  for (var i = 0; i < groups.length; i++) {
    var cards = groups[i].getElementsByClassName("usercard");
    var matches = [];

    for (var j = 0; j < cards.length; j++) {
      var nameEl = cards[j].querySelector(".username");
      var fullName = nameEl.dataset.firstname + " " + nameEl.dataset.lastname;

      if (re.test(fullName) || re.test(nameEl.dataset.nickname)) {
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
    doFilter();
  })
}

userFilter();
clearFilter();

