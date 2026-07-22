import click
import flask
from flask_socketio import SocketIO
from werkzeug.middleware.proxy_fix import ProxyFix

from flasquelistan import cachebust

socketio = SocketIO()

def create_app(config=None, instance_config=None):
    app = flask.Flask(__name__, instance_relative_config=True)
    # Load default config
    app.config.from_object('config')

    if instance_config:
        # Load instance config
        app.config.from_pyfile(instance_config)

    # Load config dict
    app.config.update(config or {})

    register_blueprints(app)
    register_cli(app)

    from flasquelistan import models, views

    if app.testing:
        models.TESTING = True

    models.db.init_app(app)
    init_db(app)

    views.auth.login_manager.init_app(app)

    setup_logging()
    setup_error_emails(app)
    setup_jinja(app)
    setup_flask_admin(app, models.db)
    setup_flask_babel(app)
    setup_flask_uploads(app)
    setup_csrf_protection(app)
    cachebust.setup_cache_busting(app)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_host=1)

    socketio.init_app(app)
    return app


def setup_logging():
    from flask.logging import default_handler

    from flasquelistan import log

    default_handler.setFormatter(log.formatter)


def setup_error_emails(app):
    import logging
    from logging.handlers import SMTPHandler

    from flasquelistan import log

    if 'ERROR_EMAIL_TOADDRS' not in app.config:
        app.logger.warning(
            "ERROR_EMAIL_TOADDRS not in config, not setting up error emails."
        )
        return

    username = app.config.get('SMTP_USERNAME')
    password = app.config.get('SMTP_PASSWORD')

    if username and password:
        credentials = (username, password)
    else:
        credentials = None

    if app.config.get('SMTP_USE_STARTTLS'):
        secure = ()
    else:
        secure = None

    mail_handler = SMTPHandler(
        mailhost=(app.config['SMTP_MAILSERVER'], app.config['SMTP_PORT']),
        fromaddr=app.config['ERROR_EMAIL_FROMADDR'],
        toaddrs=app.config['ERROR_EMAIL_TOADDRS'],
        subject="Flasquelistan application error",
        credentials=credentials,
        secure=secure
    )
    mail_handler.setLevel(logging.ERROR)
    mail_handler.setFormatter(log.formatter)

    if not app.debug:
        app.logger.addHandler(mail_handler)


def register_blueprints(app):
    from flasquelistan import scripts
    from flasquelistan.views import (
        admin,
        api,
        auth,
        discord_oauth,
        gallery,
        goofs,
        notifications,
        profile,
        quotes,
        serviceworker,
        songbook,
        strequelistan,
        transfers,
    )
    app.register_blueprint(auth.mod)
    app.register_blueprint(admin.mod)
    app.register_blueprint(api.mod)
    app.register_blueprint(serviceworker.mod)
    app.register_blueprint(strequelistan.mod)
    app.register_blueprint(discord_oauth.mod)
    app.register_blueprint(notifications.mod)
    app.register_blueprint(transfers.mod)
    app.register_blueprint(gallery.mod)
    app.register_blueprint(profile.mod)
    app.register_blueprint(quotes.mod)
    app.register_blueprint(songbook.songbook)
    app.register_blueprint(scripts.mod)
    goofs.init_goof_routes(app)
    app.register_blueprint(goofs.mod)


def register_cli(app):
    @app.cli.command('initdb')
    def initdb_command():
        init_db(app)

    @app.cli.command('dropdb')
    def dropdb_command():
        from flasquelistan import models
        if click.confirm("You are about to DROP *ALL* tables, are you sure "
                         "you want to do this?", abort=True):
            models.db.drop_all()

    @app.cli.command('populatetestdb')
    def populatetestdb_command():
        from flasquelistan.scripts import testdata
        testdata.populate()

    @app.cli.command('createadmin')
    def createadmin_command():
        from flasquelistan import models
        print("Creating a new admin user...")
        first_name = click.prompt("First name")
        last_name = click.prompt("Last name")
        email = click.prompt("Email address")
        password = click.prompt("Password", hide_input=True)
        user = models.User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            is_admin=True,
            active=True,
        )

        models.db.session.add(user)
        models.db.session.commit()


def init_db(app):
    from flasquelistan import models
    with app.app_context():
        models.db.create_all()


def setup_jinja(app):
    app.jinja_env.globals['site_title'] = \
        lambda: app.config.get('SITE_TITLE', 'Strequelistan')


def setup_flask_admin(app, db):
    import flask_admin
    from flask_admin import AdminIndexView
    from flask_admin.contrib.sqla import ModelView
    from flask_login import current_user

    from flasquelistan import models
    from flasquelistan.views import auth

    class AdminLoginMixin:
        def is_accessible(self):
            if current_user.is_authenticated:
                return current_user.is_admin
            return False

        def inaccessible_callback(self, name, **kwargs):
            if current_user.is_authenticated:
                flask.flash("Du måste vara admin för att komma åt den sidan.",
                            'error')
                return flask.redirect(flask.url_for('strequelistan.index'))
            return auth.login_manager.unauthorized()

    class LoginIndexView(AdminLoginMixin, AdminIndexView):
        pass

    class LoginModelView(AdminLoginMixin, ModelView):
        pass

    class UserModelView(LoginModelView):
        form_excluded_columns = ['transactions']
        column_exclude_list = [
            '_password_hash', 'body_mass', 'profile_picture', 'y_chromosome',
            '_password_timestamp'
        ]

    admin = flask_admin.Admin(app, name='Flasquelistan',
                              index_view=LoginIndexView(url='/flask-admin'))
    admin.add_view(UserModelView(models.User, db, name='User'))
    admin.add_view(LoginModelView(models.Group, db, name='Group'))
    admin.add_view(LoginModelView(models.Quote, db, name='Quote'))
    admin.add_view(LoginModelView(models.Article, db, name='Article'))
    admin.add_view(LoginModelView(models.Transaction, db, name='Transaction'))
    admin.add_view(LoginModelView(models.Streque, db, name='Streque'))
    admin.add_view(LoginModelView(models.AdminTransaction, db, name='AdminTransaction'))
    admin.add_view(LoginModelView(models.ApiKey, db, name='ApiKey'))
    admin.add_view(LoginModelView(models.UserTransaction, db, name='UserTransaction'))
    admin.add_view(LoginModelView(models.CreditTransfer, db, name='CreditTransfer'))
    admin.add_view(LoginModelView(models.ProfilePicture, db, name='ProfilePicture'))
    admin.add_view(LoginModelView(models.RegistrationRequest, db, name='RegistrationRequest'))
    admin.add_view(LoginModelView(models.NicknameChange, db, name='NicknameChange'))
    admin.add_view(LoginModelView(models.Notification, db, name='Notification'))
    admin.add_view(LoginModelView(models.Poke, db, name="Poke"))

    return admin


def setup_flask_babel(app):
    import flask_babel
    from flask import request, session
    from flask_login import current_user

    from flasquelistan import models

    def get_locale():
        # Check if user is logged in, if so, use the users stored preferences
        if current_user.is_authenticated:
            if request.args.get('lang'):
                current_user.lang = request.args.get('lang')
                models.db.session.commit()
                flask_babel.refresh()
            return current_user.lang
        # Check the session cookie if the user isn't logged in
        if request.args.get('lang'):
            session['lang'] = request.args.get('lang')
            flask_babel.refresh()
        return session.get('lang', None)

    def get_timezone():
        # Used to change the time zone.
        # user = getattr(g, 'user', None)
        # if user is not None:
        #    return user.timezone
        return None

    babel = flask_babel.Babel(app, locale_selector=get_locale,
                              timezone_selector=get_timezone)

    # Flask-Babel caches the selected locale on flask.g for the lifetime of
    # the app context. When an app context outlives a single request (CLI
    # scripts making internal requests, tests with a long-lived context), a
    # stale locale would be reused, so re-select it at every request start.
    app.before_request(flask_babel.refresh)

    app.jinja_env.globals['format_datetime'] = flask_babel.format_datetime
    app.jinja_env.globals['format_date'] = flask_babel.format_date
    app.jinja_env.globals['format_currency'] = flask_babel.format_currency
    app.jinja_env.globals['locale'] = flask_babel.get_locale

    return babel


def setup_flask_uploads(app):
    import flask_uploads

    from flasquelistan import util
    from flasquelistan.views import gallery

    flask_uploads.configure_uploads(app, util.image_uploads)
    flask_uploads.configure_uploads(app, util.profile_pictures)

    app.jinja_env.globals['url_for_image'] = util.url_for_image
    app.jinja_env.globals['gallery_page_for_image'] = (
        gallery.gallery_page_for_image
    )


def setup_csrf_protection(app):
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect(app)

    # Exempt the API from CSRF protection. The API is not vulnerable to
    # cross-site request forgery, since it only allows authentication through
    # the HTTP Authorization header, and will not accept any preexisting
    # session.
    from flasquelistan.views import api
    csrf.exempt(api.mod)

    return csrf
