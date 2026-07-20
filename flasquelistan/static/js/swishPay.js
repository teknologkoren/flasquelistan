// "Swisha istället"-links: open the Swish app with the payee's number
// prefilled, plus amount and message from the Streque Pay form when set.
// Amount and message are kept editable in the Swish app via the edit
// parameter. The links have a plain number-only href as fallback, so
// they work without javascript too.

function buildSwishUrl(number, amount, message) {
  var url = "https://app.swish.nu/1/p/sw/?sw=" + encodeURIComponent(number);

  var value = parseFloat((amount || "").replace(",", "."));
  if (!isNaN(value) && value >= 1) {
    url += "&amt=" + encodeURIComponent(value.toFixed(2)) + "&cur=SEK";
  }

  if (message && message.trim()) {
    url += "&msg=" + encodeURIComponent(message.trim());
  }

  return url + "&edit=amt,msg&src=url";
}

function addSwishPayListeners() {
  var buttons = document.querySelectorAll(".swish-pay-button[data-swish-number]");
  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function (e) {
      e.preventDefault();

      var form = this.closest("form");
      var valueInput = form ? form.querySelector('[name="value"]') : null;
      var messageInput = form ? form.querySelector('[name="message"]') : null;

      window.location.href = buildSwishUrl(
        this.dataset.swishNumber,
        valueInput ? valueInput.value : "",
        messageInput ? messageInput.value : ""
      );
    });
  }
}

addSwishPayListeners();
