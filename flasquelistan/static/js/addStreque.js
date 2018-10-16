function initStrequeButtons () {
  var strequeButtons = document.getElementsByClassName('streque-button');

  for (var i = 0; i < strequeButtons.length; i++) {
    var strequeButton = strequeButtons[i];
    strequeButton.addEventListener('click', function(event) {
      event.preventDefault();

      var data = {
        user_id: this.dataset.userid,
        article_id: this.dataset.articleid
      }

      var csrftoken = document.getElementById('ajax-csrf_token').value;

      var onsuccess = function(data) {
        displayEmma();
        console.log(data);
      }

      var onfailure = function (data) {
        console.log(data);
        alert('Something went wrong, reload the page and try again.')
      };

      postData('/strequa', data, onsuccess, onfailure, csrftoken);
    });
  }
}

initStrequeButtons();
