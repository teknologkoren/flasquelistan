import ssl
import smtplib
import threading
import email
from urllib.parse import urlparse, urljoin

import flask
import flask_bcrypt
import flask_uploads
from PIL import Image, ImageOps

# Note that if a module imports this as only "bcrypt", it will override
# the actual `bcrypt` library if imported. To avoid namespace issues,
# do instead: `from flasquelistan import util; util.bcrypt(...)`
bcrypt = flask_bcrypt.Bcrypt()

image_uploads = flask_uploads.UploadSet('images',
                                        flask_uploads.IMAGES)

profile_pictures = flask_uploads.UploadSet('profilepictures',
                                           flask_uploads.IMAGES)


def url_for_image(filename, imagetype, width=None):
    if not width or flask.current_app.debug:
        if imagetype == 'profilepicture':
            return profile_pictures.url(filename)

        if imagetype == 'image':
            return image_uploads.url(filename)

    if imagetype == 'profilepicture':
        base = profile_pictures.config.base_url

    elif imagetype == 'image':
        base = image_uploads.config.base_url

    return ''.join((base, 'img{}/'.format(width), filename))


def send_email(toaddr, subject, body):
    """Send an email with SMTP & STARTTLS.

    Uses the best security defaults according to the python documentation at
    the time of writing:
    https://docs.python.org/3/library/ssl.html#ssl-security

    "[ssl.create_default_context()] will load the system’s trusted CA
    certificates, enable certificate validation and hostname checking, and try
    to choose reasonably secure protocol and cipher settings."
    """

    msg = email.message.EmailMessage()
    msg.set_content(body)

    msg['Subject'] = subject
    msg['From'] = flask.current_app.config['SMTP_SENDADDR']
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

        with smtplib.SMTP(flask.current_app.config['SMTP_MAILSERVER'],
                          port=flask.current_app.config['SMTP_STARTTLS_PORT']
                          ) as smtp:

            context = ssl.create_default_context()
            smtp.starttls(context=context)

            smtp.login(flask.current_app.config['SMTP_USERNAME'],
                       flask.current_app.config['SMTP_PASSWORD'])

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
