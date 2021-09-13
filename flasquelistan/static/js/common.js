var timeout;

function displayEmma() {
  if (timeout !== undefined) {
    clearTimeout(timeout);
    document.getElementById('emma-img').remove();
  }

  var emma = document.createElement('img');
  emma.id = 'emma-img';
  emma.classList.add('hidden');

  emma.onload = function () {
    timeout = setTimeout(function () {
      emma.classList.remove('hidden');

      timeout = setTimeout(function () {
        emma.classList.add('hidden');
        setTimeout(function () {
          emma.remove();
          timeout = undefined;
        }, 100);
      }, 1100);
    }, 50);
  };
  emma.src = '/static/images/emma.gif';
  document.body.appendChild(emma);
}

function postData(uri, data, onsuccess, onfailure, csrftoken) {
  var request = new XMLHttpRequest();
  request.open('POST', uri, true);
  request.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
  request.setRequestHeader('X-CSRFToken', csrftoken);

  request.onload = function () {
    if (request.status >= 200 && request.status < 400) {
      // Success!
      var data = JSON.parse(request.responseText);
      onsuccess(data);
    } else {
      // Server returned error code
      var data = request.responseText;
      onfailure(data);
    }
  };

  request.onerror = function () {
    alert('Something went wrong, reload the page and try again.')
  };

  request.send(JSON.stringify(data));

  return request;
}

function hidenojs() {
  var nojs = document.getElementsByClassName("no-js");
  for (var i = 0; i < nojs.length; i++) {
    nojs[i].style.display = "none";
  }
}

function stupidCatButton() {
  var stupidButton = document.createElement('button');
  stupidButton.addEventListener('click', function () {
    var cuteCat = document.createElement('img');
    var stupidInt = Math.floor(Math.random() * 10) + 1;
    var stupidSrc = '/static/images/stupid/cats/cat-' + stupidInt + '.png';
    cuteCat.src = stupidSrc;
    cuteCat.style['z-index'] = '1000';
    cuteCat.style.position = 'fixed';
    cuteCat.style.top = Math.floor(Math.random() * 90) + -10 + '%';
    cuteCat.style.left = Math.floor(Math.random() * 90) + -10 + '%';
    cuteCat.style.transform = 'rotate(' + (-20 + Math.floor(Math.random() * 41)) + 'deg)';
    document.body.appendChild(cuteCat);
  });
  stupidButton.innerHTML = '🐱';
  return stupidButton;
}

function addStupidButtons() {
  var stupidButtons = [
    stupidCatButton()
  ];
  stupidDiv = document.getElementById('stupid-buttons');
  for (var i = 0; i < stupidButtons.length; i++) {
    stupidDiv.appendChild(stupidButtons[i]);
  }
}

hidenojs();
addStupidButtons();
