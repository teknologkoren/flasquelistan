function initStrequeButtons () {
  var strequeButtons = document.getElementsByClassName('streque-button');

  for (var i = 0; i < strequeButtons.length; i++) {
    strequeButton = strequeButtons[i];
    strequeButton.addEventListener('click', function(event) {
      event.preventDefault();

      data = {
        user_id: this.dataset.userid,
        article_id: this.dataset.articleid
      }

      csrftoken = this.dataset.csrftoken;

      var onsuccess = function(data) {
        displayEmma();
      }

      postData('/strequa', data, onsuccess, csrftoken);
    });
  }
}

initStrequeButtons();
