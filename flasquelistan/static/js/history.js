function maybeDisplayNotice() {
  list = document.getElementsByClassName('transaction-list');
  notice = document.getElementsByClassName('no-transactions-notice');

  if (list[0].children.length > 0) {
    notice[0].style.display = 'none';
  } else {
    notice[0].style.display = 'block';
  }
}

function initVoidTransactionButtons() {
  var voidForms = document.getElementsByClassName('void-form');

  for (var i = 0; i < voidForms.length; i++) {
    voidForm = voidForms[i];
    voidForm.addEventListener('click', function(event) {
      event.preventDefault();

      data = {
        transaction_id: this.dataset.transactionid
      }

      onsuccess = function (data) {
        card = document.getElementById(data['transaction_id'])
        card.style.opacity = '0';
        setTimeout(function () {
          card.parentNode.removeChild(card);
          maybeDisplayNotice();
        }, 500);
      }
      var request = postData('/void', data, onsuccess);
    });
  }
}

maybeDisplayNotice();
initVoidTransactionButtons();
