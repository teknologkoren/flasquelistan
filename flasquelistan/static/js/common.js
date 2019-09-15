function downloadEmma() {
  var wrapper = document.createElement('div');
  wrapper.id = 'emma-wrapper';
  wrapper.classList.add('hidden');

  var video = document.createElement('video');
  video.id = 'emma';
  video.preload = 'auto';
  video.muted = '';
  video.playsinline = '';
  video.disableRemotePlayback = true;

  var webm = document.createElement('source');
  webm.src = '/static/images/emma.webm';
  webm.type = 'video/webm; codecs=vp9';
  video.appendChild(webm);

  var mp4 = document.createElement('source');
  mp4.src = '/static/images/emma.compat.mp4';
  mp4.type = 'video/mp4';
  video.appendChild(mp4);

  wrapper.appendChild(video);
  document.body.appendChild(wrapper);
}

var timeout;

function displayEmma() {
  if (typeof timeout !== 'undefined') {
    clearTimeout(timeout);
  }

  var wrapper = document.getElementById('emma-wrapper');
  var emma = document.getElementById('emma');

  emma.currentTime = 0;

  wrapper.classList.remove('hidden');
  wrapper.classList.add('visible');

  setTimeout(function () { emma.play(); }, 50);

  timeout = setTimeout(function () {
    wrapper.classList.remove('visible');
    wrapper.classList.add('hidden');
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

downloadEmma();
