function initVoidStrequeButtons() {
  var voidButtons = document.getElementsByClassName('void-button');

  for (var i = 0; i < voidButtons.length; i++) {
    voidButton = voidButtons[i];
    voidButton.addEventListener('click', function(event) {
      event.preventDefault();

      data = {
        streque_id: this.dataset.strequeid
      }

      csrftoken = this.dataset.csrftoken

      onsuccess = function (data) {
        card = document.getElementById(data['streque_id']);

        voidedSpan = document.createElement('span');
        voidedSpan.innerHTML = "Ångrad!";

        form = card.getElementsByClassName('void-button')[0];
        form.parentNode.replaceChild(voidedSpan, form);

        card.style.opacity = '0.5';
      }
      var request = postData('/void', data, onsuccess, csrftoken);
    });
  }
}

initVoidStrequeButtons();
