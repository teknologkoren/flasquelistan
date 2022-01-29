import base64
import datetime
import email
import hashlib
import smtplib
import ssl
import threading
from urllib.parse import urljoin, urlparse

import flask
import flask_uploads
import werkzeug
from PIL import Image, ImageOps

image_uploads = flask_uploads.UploadSet('images',
                                        flask_uploads.IMAGES)

profile_pictures = flask_uploads.UploadSet('profilepictures',
                                           flask_uploads.IMAGES)


def generate_secure_path_hash(expires, url, secret):
    data = f"{expires}{url}{flask.request.remote_addr} {secret}"
    binary_hash = hashlib.md5(data.encode()).digest()
    nginx_hash = base64.urlsafe_b64encode(binary_hash).decode().rstrip('=')
    return nginx_hash


def url_for_image(filename, imagetype, width=None):
    if imagetype == 'profilepicture':
        base = profile_pictures.config.base_url
    elif imagetype == 'image':
        base = image_uploads.config.base_url
    else:
        flask.abort(500)

    href = werkzeug.urls.Href(base)
    if width and not flask.current_app.debug:
        url = href('img{}'.format(width), filename)
    else:
        url = href(filename)

    secret = flask.current_app.config['IMAGE_SECRET']
    expiry = flask.current_app.config['IMAGE_EXPIRY']
    expires = int(datetime.datetime.now().timestamp() + expiry)
    md5 = generate_secure_path_hash(expires, url, secret)

    full_href = werkzeug.urls.Href(url)
    return full_href(md5=md5, expires=expires)


def send_email(toaddr, subject, body):
    """Send an email with SMTP & STARTTLS.

    Uses the best security defaults according to the python documentation at
    the time of writing:
    https://docs.python.org/3/library/ssl.html#ssl-security

    "[ssl.create_default_context()] will load the system’s trusted CA
    certificates, enable certificate validation and hostname checking, and try
    to choose reasonably secure protocol and cipher settings."
    """
    config = flask.current_app.config

    msg = email.message.EmailMessage()
    msg.set_content(body)

    msg['Subject'] = subject
    msg['From'] = config['SMTP_SENDADDR']
    msg['To'] = toaddr

    @flask.copy_current_request_context
    def thread_func():
        if flask.current_app.debug:
            print("\n===== DEBUG: Did not send the "
                  "following email message: =====\n")
            print(msg)
            print("===== DEBUG: Content is: =====\n")
            print(msg.get_content())
            print("===== END DEBUG =====\n")
            return

        with smtplib.SMTP(config['SMTP_MAILSERVER'],
                          port=config['SMTP_PORT']
                          ) as smtp:

            if config.get('SMTP_USE_STARTTLS'):
                context = ssl.create_default_context()
                smtp.starttls(context=context)

            username = config.get('SMTP_USERNAME')
            password = config.get('SMTP_PASSWORD')
            if username and password:
                smtp.login(username, password)

            smtp.send_message(msg)

    thread = threading.Thread(target=thread_func)

    with flask.current_app.app_context():
        thread.start()


def is_safe_url(target):
    """Tests if the url is a safe target for redirection.

    Does so by checking that the url is still using http or https and
    and that the url is still our site.
    """
    ref_url = urlparse(flask.request.host_url)
    test_url = urlparse(urljoin(flask.request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        test_url.netloc == ref_url.netloc


def get_redirect_target():
    """Get where we want to redirect to.

    Checks the 'next' argument in the request and if nothing there, use
    the http referrer. Also checks whether the target is safe to
    redirect to (no 'open redirects').
    """
    for target in (flask.request.values.get('next'), flask.request.referrer):
        if not target:
            continue
        if target == flask.request.url:
            continue
        if is_safe_url(target):
            return target


def rotate_jpeg(filename):
    img = Image.open(filename)
    if 'exif' in img.info:
        rotated = ImageOps.exif_transpose(img)
        rotated.save(filename, exif=rotated.info.get('exif'))
