function downloadEmma() {
  var video = document.createElement('video');
  video.id = 'emma';
  video.src = '/static/images/emma.webm';
  video.pause();
  document.body.appendChild(video)
}

var timeout;

function displayEmma() {
  if (typeof timeout !== 'undefined') {
    clearTimeout(timeout);
  }

  emma = document.getElementById('emma');
  emma.currentTime = 0;
  emma.style.display = 'block';
  emma.play();

  timeout = setTimeout(function () {
    emma.style.display = 'none';
    emma.pause();
  }, 1200);
}

function postData(uri, data, onsuccess) {
  request = new XMLHttpRequest();
  request.open('POST', uri, true);
  request.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');

  request.onload = function () {
    if (request.status >= 200 && request.status < 400) {
      // Success!
      var data = JSON.parse(request.responseText);
      console.log(data);
      onsuccess(data);
    } else {
      // Server returned error code
      alert('Error: ' + request.status);
    }
  };

  request.onerror = function () {
    // Error
  }

  request.send(JSON.stringify(data))

  return request
}

downloadEmma();
