function addVisibilityToggleListener() {
  var toggleFunc = function(event) {
    var x = document.getElementById("toggleable-element");
    x.classList.toggle("hidden")
    event.preventDefault();
  }

  var toggle = document.getElementById("visibility-toggle");
  toggle.addEventListener('click', toggleFunc, false);
}

addVisibilityToggleListener();