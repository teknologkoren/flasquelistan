function initStrequeButtons () {
  var strequeButtons = document.getElementsByClassName('streque-button');

  for (var i = 0; i < strequeButtons.length; i++) {
    var strequeButton = strequeButtons[i];
    strequeButton.addEventListener('click', function(event) {
      event.preventDefault();

      var data = {
        user_id: this.dataset.userid,
        article_id: this.dataset.articleid
      }

      var csrftoken = document.getElementById('ajax-csrf_token').value;

      var onsuccess = function(data) {
        displayEmma();
        console.log(data);
      }

      var onfailure = function(data) {
        console.log(data);
        alert('Something went wrong, reload the page and try again.')
      };

      postData('/strequa', data, onsuccess, onfailure, csrftoken);
    });
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
    cuteCat.style.top = Math.floor(Math.random() * 90) + -15 + '%';
    cuteCat.style.left = Math.floor(Math.random() * 100) + -15 + '%';
    cuteCat.style.transform = 'rotate(' + (-20 + Math.floor(Math.random() * 41)) + 'deg)';
    document.body.appendChild(cuteCat);
  });
  stupidButton.innerHTML = '🐱';
  stupidButton.classList.add('stupid-button');
  return stupidButton;
}

function stupidConfettiButton() {
  var stupidButton = document.createElement('button');
  stupidButton.addEventListener('click', function () {
    confetti();
  });
  stupidButton.innerHTML = '🎉';
  stupidButton.classList.add('stupid-button');
  return stupidButton;
}

function addStupidButtons() {
  var stupidButtons = [
    stupidCatButton(),
    stupidConfettiButton()
  ];
  stupidDiv = document.getElementById('stupid-buttons');
  for (var i = 0; i < stupidButtons.length; i++) {
    stupidDiv.appendChild(stupidButtons[i]);
  }
}

initStrequeButtons();
addStupidButtons();
downloadEmma();
