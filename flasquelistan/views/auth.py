import datetime
import functools

import flask
import flask_login
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_login import current_user
from itsdangerous import SignatureExpired, URLSafeTimedSerializer

from flasquelistan import forms, models, util

mod = flask.Blueprint('auth', __name__)

login_manager = flask_login.LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    """Tell flask-login how to get logged in user."""
    return models.User.query.get(user_id)


def admin_required(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.is_admin:
            return func(*args, **kwargs)

        if flask.request.get_json():
            # Request is AJAX
            return flask.abort(403)

        flask.flash(_l("Du måste vara admin för att komma åt den sidan."),
                    'error')
        return flask.redirect(
            flask.request.referrer or flask.url_for('strequelistan.index')
        )
    return wrapper


@mod.route('/robots.txt')
def robots():
    """Serve the robots.txt file
    """
    return flask.render_template('auth/robots.txt')


@mod.route('/login', methods=['GET', 'POST'])
def login():
    """Show login page and form.

    Not showing which field was wrong if any is intentional. Usernames
    and passwords only represent anything when used in combination
    (http://ux.stackexchange.com/a/13523).
    """
    form = forms.LoginForm()

    if current_user.is_authenticated:
        return form.redirect('strequelistan.index')

    if form.validate_on_submit():
        user = models.User.authenticate(form.email.data, form.password.data)
        flask_login.login_user(user, remember=form.remember.data)
        return form.redirect('strequelistan.index')
    elif form.is_submitted():
        flask.flash(
            _l("E-postadressen eller lösenordet du angav stämmer inte."),
            'error'
        )

    return flask.render_template('auth/login.html', form=form)


@mod.route('/logout')
def logout():
    """Logout user (if logged in) and redirect to main page."""
    if current_user.is_authenticated:
        flask_login.logout_user()
    return flask.redirect(flask.url_for('auth.login'))


@mod.route('/register', methods=['GET', 'POST'])
def register():
    """Request an account"""
    form = forms.RegistrationRequestForm()

    if form.validate_on_submit():
        request = models.RegistrationRequest(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data,
            message=form.message.data,
        )

        models.db.session.add(request)
        models.db.session.commit()

        util.send_email('qm@teknologkoren.se',
                        "Förfrågan om nytt konto på Strequelistan",
                        flask.render_template('auth/register_email.jinja2',
                                              request=request)
                        )

        flask.flash(_l("QM har uppmärksammats om din förfrågan."), 'info')

        return flask.redirect(flask.url_for('auth.login'))

    return flask.render_template('auth/register.html', form=form)


def verify_email(user, email):
    """Create an email verification email.

    The user id and the requested email address is hashed and included as a
    token in a link referring to the verification page. The link is sent to the
    requested email address.

    The token is timestamped, when verifying we can check the age.
    """
    ts = URLSafeTimedSerializer(flask.current_app.config["SECRET_KEY"])

    token = ts.dumps([user.id, email], 'verify-email')

    verify_link = flask.url_for('auth.verify_token', token=token,
                                _external=True)

    email_body = flask.render_template('auth/email_verification.jinja2',
                                       link=verify_link)

    subject = "Verifiera din e-postaddress på Strequelistan"

    util.send_email(email, subject, email_body)


@mod.route('/verify/<token>')
def verify_token(token):
    """Verify email reset token.

    Loads the user id and the requested email and simultaneously checks
    token age. If not too old, get user with id and set email.
    """
    ts = URLSafeTimedSerializer(flask.current_app.config["SECRET_KEY"])

    try:
        user_id, email = ts.loads(token, salt='verify-email', max_age=900)
    except SignatureExpired:
        flask.flash(_l("Länken har gått ut, var vänlig försök igen."), 'error')
        return flask.redirect(flask.url_for('auth.login'))
    except:  # noqa: E722 (ignore 'bare except' warning)
        flask.abort(404)

    user = models.User.query.get_or_404(user_id)
    user.email = email
    models.db.session.commit()

    flask.flash(_("%(e)s är nu verifierad!", e=email), 'success')
    return flask.redirect(flask.url_for('auth.login'))


@mod.route('/reset/', methods=['GET', 'POST'])
def reset():
    """View for requesting password reset.

    If a non-registred email address is entered, do nothing but tell
    user that an email has been sent. This way we do not expose what
    email addresses are registred.

    If a registred email address is entered, get the id of the user the
    email address is registred to and create a timestamped token with
    the id. The token is sent as a part of a link to the email of that
    user.

    The view which the link leads to checks that the token is intact and
    has not been tampered with, checks its age, and checks if the
    password has been changed after the token was created. This means:
    * Tokens are time limited.
    * Multiple tokens can be valid at the same time, which prevents
        confusion for the user.
    * If the password is changed, using a token or in some other way,
        all tokens generated before that change become invalid.
    * Tokens are therefore single use.
    * Tokens are not stored anywhere other than in the email sent to
        user.
    """
    reset_flash = (_l("Om {} är en registrerad adress så har vi skickat en "
                   "återställningslänk till den."))

    ts = URLSafeTimedSerializer(flask.current_app.config["SECRET_KEY"])

    form = forms.ExistingEmailForm()

    if form.validate_on_submit():
        user = models.User.query.filter_by(email=form.email.data).first()
        token = ts.dumps(user.id, salt='recover-key')

        recover_url = flask.url_for('.reset_token', token=token,
                                    _external=True)

        email_body = flask.render_template('auth/password_reset_email.jinja2',
                                           name=user.first_name,
                                           link=recover_url)

        subject = "Återställ ditt lösenord hos Strequelistan"

        util.send_email(user.email, subject, email_body)

        flask.flash(reset_flash.format(form.email.data), 'info')
        return flask.redirect(flask.url_for('.login'))

    elif form.email.data:
        flask.flash(reset_flash.format(form.email.data), 'info')
        return flask.redirect(flask.url_for('.login'))

    elif form.errors:
        flask.flash(_l("Vänligen skriv in din e-epostaddress"), 'error')

    return flask.render_template('auth/reset.html', form=form)


@mod.route('/reset/<token>', methods=['GET', 'POST'])
def reset_token(token):
    """Verify a password reset token.

    Checks if the token is intact and has not been tampered with,
    checks its age, and checks if the password has been changed after
    the token was created.

    If the token is valid, allow user to enter a new password.

    Note: itsdangerous saves the timestamp in tokens in UTC!
    """
    expired = _l("Länken har gått ut, var vänlig försök igen.")
    invalid = _l("Länken verkar vara trasig eller felaktig,\
               var vänlig försök igen.")

    ts = URLSafeTimedSerializer(flask.current_app.config["SECRET_KEY"])

    try:
        data, timestamp = ts.loads(token, salt='recover-key', max_age=3600,
                                   return_timestamp=True)
        user = models.User.query.get(data)
    except SignatureExpired:
        flask.flash(expired, 'error')
        return flask.redirect(flask.url_for('.login'))
    except:  # noqa: E722 (ignore 'bare except' warning)
        flask.flash(invalid, 'error')
        return flask.redirect(flask.url_for('.login'))

    pw_timestamp_tzaware = \
        user._password_timestamp.replace(tzinfo=datetime.timezone.utc)

    if timestamp < pw_timestamp_tzaware:
        flask.flash(expired, 'error')
        return flask.redirect(flask.url_for('.login'))

    form = forms.NewPasswordForm()

    if form.validate_on_submit():
        user.password = form.new_password.data
        models.db.session.commit()
        flask.flash(_l("Ditt lösenord har återställts!"), 'success')
        return flask.redirect(flask.url_for('.login'))

    return flask.render_template('auth/reset_token.html', form=form)
