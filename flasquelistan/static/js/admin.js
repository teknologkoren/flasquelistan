function initVoidTransactionButtons() {
  var voidForms = document.getElementsByClassName('transaction void-form');

  for (var i = 0; i < voidForms.length; i++) {
    voidForm = voidForms[i];
    voidForm.addEventListener('click', function(event) {
      event.preventDefault();

      data = {
        transaction_id: this.dataset.transactionid
      }

      onsuccess = function (data) {
        form = document.getElementById("void-transaction-" + data['transaction_id']);

        voidedSpan = document.createElement('span');
        voidedSpan.innerHTML = "Ångrad";

        form.parentNode.replaceChild(voidedSpan, form);
      }
      var request = postData('/admin/transaktioner/void', data, onsuccess);
    });
  }
}

initVoidTransactionButtons();
