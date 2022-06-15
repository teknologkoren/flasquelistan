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

hidenojs();
