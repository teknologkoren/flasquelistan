function downloadEmma() {
  var video = document.createElement('video');
  video.id = 'emma';
  video.classList.add('hide-emma');
  video.setAttribute('preload', 'auto');
  video.setAttribute('muted', '');
  video.setAttribute('playsinline', '');
  video.setAttribute('disableRemotePlayback', '');

  var webm = document.createElement('source');
  webm.src = '/static/images/emma.webm';
  webm.type = 'video/webm; codecs=vp9';
  video.appendChild(webm);

  var mp4 = document.createElement('source');
  mp4.src = '/static/images/emma.compat.mp4';
  mp4.type = 'video/mp4';
  video.appendChild(mp4);

  document.body.appendChild(video);
}

var timeout;
function displayEmma() {
  if (typeof timeout !== 'undefined') {
    clearTimeout(timeout);
  }
  var emma = document.getElementById('emma');
  emma.currentTime = 0;
  emma.classList.remove('hide-emma');
  setTimeout(function () { emma.play(); }, 50);
  timeout = setTimeout(function () {
    emma.classList.add('hide-emma');
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
