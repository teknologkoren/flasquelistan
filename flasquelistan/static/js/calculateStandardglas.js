function standardglas(volumeMl, alcVolPercent) {
  var alcDensity = 0.7893;  // g/cm^3 at 20 degrees celsius
  var alcVolume = volumeMl*alcVolPercent;
  var alcWeight = alcVolume*alcDensity;
  var sg = alcWeight/12;  // 1 standardglas is 12g of alcohol
  return sg;
}

function createInputs(sgInput) {
  var volumeInput = document.createElement("input");
  volumeInput.setAttribute("type", "number");
  volumeInput.setAttribute("min", "0");

  var volumeText = document.createTextNode("cl");

  var volumeSpan = document.createElement("span");
  volumeSpan.appendChild(volumeInput);
  volumeSpan.appendChild(volumeText);
  volumeSpan.classList.add("calculate-sg-volume");

  var percentInput = document.createElement("input");
  percentInput.setAttribute("type", "number");
  percentInput.setAttribute("min", "0");
  percentInput.setAttribute("max", "100");
  percentInput.setAttribute("step", "0.1");

  var percentText = document.createTextNode("%");

  var percentSpan = document.createElement("span");
  percentSpan.appendChild(percentInput);
  percentSpan.appendChild(percentText);
  percentSpan.classList.add("calculate-sg-percent");

  var calculateButton = document.createElement("button");
  calculateButton.innerHTML = "Beräkna";
  calculateButton.classList.add("calculate-sg-button");

  var inputDiv = document.createElement("div");
  inputDiv.appendChild(volumeSpan);
  inputDiv.appendChild(percentSpan);
  inputDiv.appendChild(calculateButton);

  sgInput.parentNode.insertBefore(inputDiv, sgInput.nextSibling);
  calculateButton.addEventListener("click", function(event) {
    event.preventDefault();
    var vol = volumeInput.value*10;
    var perc = percentInput.value/100;
    var sg = standardglas(vol, perc);
    var rounded = Math.round((sg + Number.EPSILON) * 10) / 10;
    sgInput.value = rounded;
  });
}

function sgInit() {
  var standardglasInput = document.getElementById("standardglas");
  createInputs(standardglasInput);
}

sgInit();
