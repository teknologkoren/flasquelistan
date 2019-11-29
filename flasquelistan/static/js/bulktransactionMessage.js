function setMessage() {
  var message = document.getElementById("bulktransaction-message").value;

  var inputs = document.getElementsByTagName("input");

  for (i = 0; i < inputs.length; i++) {
    if (inputs[i].type == "text") {
      inputs[i].value = message
    }
  }
}

var button = document.getElementById("set-bulktransaction-message");
button.addEventListener('click', setMessage, false);
