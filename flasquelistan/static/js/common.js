function downloadEmma() {
  var video = document.createElement('video');
  video.id = 'emma';

  var webm = document.createElement('source');
  webm.src = '/static/images/emma.webm';
  webm.type = 'video/webm';

  var mp4 = document.createElement('source');
  mp4.src = '/static/images/emma.mp4';
  mp4.type = 'video/mp4';

  video.pause();

  video.appendChild(webm);
  video.appendChild(mp4);
  document.body.appendChild(video)
}

var timeout;

function displayEmma() {
  if (typeof timeout !== 'undefined') {
    clearTimeout(timeout);
  }

  var emma = document.getElementById('emma');
  emma.currentTime = 0;
  emma.style.display = 'block';
  emma.play();

  var timeout = setTimeout(function () {
    emma.style.display = 'none';
    emma.pause();
  }, 1200);
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
    // Error
  }

  request.send(JSON.stringify(data))

  return request
}

downloadEmma();
