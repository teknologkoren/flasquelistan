function initVoidTransactionButtons() {
  var voidForms = document.getElementsByClassName('void-form');

  for (var i = 0; i < voidForms.length; i++) {
    voidForm = voidForms[i];
    voidForm.addEventListener('click', function(event) {
      event.preventDefault();

      data = {
        streque_id: this.dataset.strequeid
      }

      onsuccess = function (data) {
        card = document.getElementById(data['streque_id']);

        voidedSpan = document.createElement('span');
        voidedSpan.innerHTML = "Ångrad!";

        form = card.getElementsByClassName('void-form')[0];
        form.parentNode.replaceChild(voidedSpan, form);

        card.style.opacity = '0.5';
      }
      var request = postData('/void', data, onsuccess);
    });
  }
}

initVoidTransactionButtons();
