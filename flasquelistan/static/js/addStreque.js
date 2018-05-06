function initStrequeButtons () {
  var strequeButtons = document.getElementsByClassName('streque-button');

  for (var i = 0; i < strequeButtons.length; i++) {
    strequeButton = strequeButtons[i];
    strequeButton.addEventListener('click', function () {
      data = {
        user_id: this.dataset.userid,
        amount: this.dataset.amount
      }

      var onsuccess = function (data) {
        displayEmma();
      }

      postData('/strequa', data, onsuccess);
    });
  }
}

initStrequeButtons();
