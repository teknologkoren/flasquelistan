function initVoidTransactionButtons() {
  var voidButtons = document.getElementsByClassName('transaction void-button');

  for (var i = 0; i < voidButtons.length; i++) {
    voidButton = voidButtons[i];
    voidButton.addEventListener('click', function(event) {
      event.preventDefault();

      data = {
        transaction_id: this.dataset.transactionid
      }

      csrftoken = this.dataset.csrftoken;

      onsuccess = function (data) {
        form = document.getElementById("void-transaction-" + data['transaction_id']);

        voidedSpan = document.createElement('span');
        voidedSpan.innerHTML = "Ångrad";

        form.parentNode.replaceChild(voidedSpan, form);
      }
      var request = postData('/admin/transaktioner/void', data, onsuccess, csrftoken);
    });
  }
}

initVoidTransactionButtons();
