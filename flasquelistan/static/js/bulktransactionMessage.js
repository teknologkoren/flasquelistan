
function setMessage() {
  var message = document.getElementById("bulktransactionMessage").value;
  console.log(message);

  var inputs = document.getElementsByTagName("input");

  for (i = 0; i < inputs.length; i++){
    if (inputs[i].type=="text"){
      inputs[i].value = message
    }
  }
}

