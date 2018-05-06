function initVoidTransactionButtons () {
  var voidButtons = document.getElementsByClassName('void-button');

  for (var i = 0; i < voidButtons.length; i++) {
    voidButton = voidButtons[i];
    voidButton.addEventListener('click', function () {
      data = {
        transaction_id: this.dataset.transactionid
      }

      onsuccess = function (data) {
        card = document.getElementById(data['transaction_id'])
        card.style.display = "none";
      }

      var request = postData('/void', data, onsuccess);
    });
  }
}

initVoidTransactionButtons();
