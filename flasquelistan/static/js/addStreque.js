function initStrequeButtons () {
  var strequeForms = document.getElementsByClassName('streque-form');

  for (var i = 0; i < strequeForms.length; i++) {
    strequeForm = strequeForms[i];
    strequeForm.addEventListener('submit', function(event) {
      event.preventDefault();

      data = {
        user_id: this.dataset.userid,
        article_id: this.dataset.articleid
      }

      var onsuccess = function(data) {
        displayEmma();
      }

      postData('/strequa', data, onsuccess);
    });
  }
}

initStrequeButtons();
