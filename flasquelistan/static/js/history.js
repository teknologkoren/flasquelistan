function initVoidStrequeButtons() {
  var voidButtons = document.getElementsByClassName('void-button');

  for (var i = 0; i < voidButtons.length; i++) {
    var voidButton = voidButtons[i];
    voidButton.addEventListener('click', function(event) {
      event.preventDefault();

      var data = {
        streque_id: this.dataset.strequeid
      }

      var csrftoken = document.getElementById('ajax-csrf_token').value;

      var onsuccess = function(data) {
        var card = document.getElementById(data['streque_id']);

        var voidedSpan = document.createElement('span');
        voidedSpan.innerHTML = "Ångrad!";

        var form = card.getElementsByClassName('void-button')[0];
        form.parentNode.replaceChild(voidedSpan, form);

        card.style.opacity = '0.5';
      }

      var onfailure = function(data) {
        alert('Something went wrong, reload the page and try again.');
      }

      var request = postData('/void', data, onsuccess, onfailure, csrftoken);
    });
  }
}

initVoidStrequeButtons();
