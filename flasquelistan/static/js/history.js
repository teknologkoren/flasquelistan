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
  var voidButtons = document.getElementsByClassName('void-button');

  for (var i = 0; i < voidButtons.length; i++) {
    voidButton = voidButtons[i];
    voidButton.addEventListener('click', function () {
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
