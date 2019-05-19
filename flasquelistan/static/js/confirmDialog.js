function addConfirmListener() {
  var confirmFunc = function(e) {
    if (!confirm('Är du säker?')) e.preventDefault();
  };

  var confirms = document.getElementsByClassName('confirm');
  for (var i = 0; i < confirms.length; i++) {
    confirms[i].addEventListener('click', confirmFunc, false);
  }
}

addConfirmListener();
