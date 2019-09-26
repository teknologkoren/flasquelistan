function downloadEmma() {
  var wrapper = document.createElement('div');
  wrapper.id = 'emma-wrapper';
  wrapper.classList.add('hidden');

  var emma = document.createElement('div');
  emma.id = 'emma';

  var emmasrc = document.createElement('img');
  emmasrc.id = 'emmasrc';

  emmasrc.src = '/static/images/emma.gif';
  emmasrc.style.display = 'none';

  wrapper.appendChild(emmasrc);
  wrapper.appendChild(emma);
  document.body.appendChild(wrapper);
}

function displayEmma() {
  var wrapper = document.getElementById('emma-wrapper');
  var emma = document.getElementById('emma');

  if (typeof timeout !== 'undefined') {
    emma.innerHTML = '';
    clearTimeout(timeout);
  }

  var img = document.createElement('img');
  img.src = '/static/images/emma.gif';
  emma.appendChild(img);

  setTimeout(function () {
    wrapper.classList.remove('hidden');
    wrapper.classList.add('visible');

    timeout = setTimeout(function () {
      wrapper.classList.remove('visible');
      wrapper.classList.add('hidden');
      setTimeout(function () {
        emma.removeChild(img);
      }, 200);
    }, 1200);
  }, 50) // Wait a bit if the browser does a request for the src
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

downloadEmma();
