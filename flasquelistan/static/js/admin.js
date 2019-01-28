function initVoidTransactionButtons() {
  var voidButtons = document.getElementsByClassName('transaction void-button');

  for (var i = 0; i < voidButtons.length; i++) {
    var voidButton = voidButtons[i];
    voidButton.addEventListener('click', function(event) {
      event.preventDefault();

      var data = {
        transaction_id: this.dataset.transactionid
      }

      var csrftoken = this.dataset.csrftoken;

      var onsuccess = function (data) {
        var form = document.getElementById("void-transaction-" + data['transaction_id']);

        var voidedSpan = document.createElement('span');
        voidedSpan.innerHTML = "Ångrad";

        form.parentNode.replaceChild(voidedSpan, form);
      }

      var onfailure = function (data) {
        console.log(data);
        alert('Something went wrong, reload the page and try again.')
      };

      var request = postData('/admin/transaktioner/void', data, onsuccess, onfailure, csrftoken);
    });
  }
}

initVoidTransactionButtons();
