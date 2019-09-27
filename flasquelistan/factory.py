import click
import flask


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

    from flasquelistan import models, views, util

    models.db.init_app(app)
    init_db(app)

    util.bcrypt.init_app(app)

    views.auth.login_manager.init_app(app)

    setup_flask_admin(app, models.db)
    setup_flask_babel(app)
    setup_flask_uploads(app)
    setup_csrf_protection(app)

    return app


def register_blueprints(app):
    from flasquelistan.views import (auth, admin, more, quotes, serviceworker,
                                     strequelistan)
    app.register_blueprint(auth.mod)
    app.register_blueprint(admin.mod)
    app.register_blueprint(more.mod)
    app.register_blueprint(serviceworker.mod)
    app.register_blueprint(strequelistan.mod)
    app.register_blueprint(quotes.mod)


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
        populate_testdb()

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


def populate_testdb():
    from flasquelistan import models
    monty = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
        phone='0710001122',
        balance=10000,
        active=True,
    )

    rick = models.User(
        email='rick_astley@example.com',
        first_name='Rick',
        nickname='The Roll',
        last_name='Astley',
        phone='0713322110',
        balance=20050,
        active=True,
    )

    barack = models.User(
        email='no.44@hotmail.tld',
        first_name='Barack',
        last_name='Obama',
        nickname='Barry',
        phone='+1 (808) 555-2643',
        balance=100000,
        active=True,
    )

    kor = models.User(
        email='kor.ist@example.se',
        first_name='Kor',
        last_name='Ist',
        nickname="Party-'pranen",
        phone='074 876 54 32',
        balance=-1000,
        active=True,
    )

    malvina = models.User(
        email='maltek@kth.tld',
        first_name='Malvina',
        last_name='Teknolog',
        nickname='Osqulda',
        phone='074-345 32 10',
        balance=-10000,
        active=True,
    )

    soprano = models.Group(name='Sopran', weight='10')
    alto = models.Group(name='Alt', weight='20')
    tenor = models.Group(name='Tenor', weight='30')
    bass = models.Group(name='Bas', weight='40')

    beer = models.Article(name='Öl', value=1200, weight=10, standardglas=1)
    cider = models.Article(name='Cider', value=1200, weight=20, standardglas=1)
    wine = models.Article(name='Vin', value=1500, weight=30, standardglas=1)
    shot = models.Article(name='4 cl', value=1600, weight=40, standardglas=1)
    soft = models.Article(name='Alkfritt', value=1000, weight=50,
                          standardglas=0)

    quote1 = models.Quote(
        text="Kom igen, testa citaten, det blir kul!",
        who="Någon, om Strequelistan",
    )

    quote2 = models.Quote(text="Ett citat utan upphovsman, spännade!")

    quote3 = models.Quote(
        text=("Explicabo possimus dolorem voluptate. "
              "Aut perferendis mollitia dolor nulla. "
              "Perferendis at consequuntur ea aliquam "
              "aut inventore quis neque."),
        who="Godtycklig medietekniker",
    )

    quote4 = models.Quote(text="much quote, such fun", who="shibe")

    models.db.session.add_all([monty, rick, barack, kor, malvina,
                               soprano, alto, tenor, bass,
                               beer, cider, wine, shot, soft,
                               quote1, quote2, quote3, quote4])
    models.db.session.commit()

    kor.group = soprano
    malvina.group = alto
    monty.group = tenor
    rick.group = bass
    barack.group = bass

    models.db.session.commit()


def init_db(app):
    from flasquelistan import models
    models.db.create_all(app=app)


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
            else:
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
    admin.add_view(UserModelView(models.User, db.session, name='User'))
    admin.add_view(LoginModelView(models.Group, db.session, name='Group'))
    admin.add_view(LoginModelView(models.Quote, db.session, name='Quote'))
    admin.add_view(LoginModelView(models.Article, db.session, name='Article'))
    admin.add_view(LoginModelView(models.Transaction, db.session,
                                  name='Transaction'))
    admin.add_view(LoginModelView(models.Streque, db.session, name='Streque'))
    admin.add_view(LoginModelView(models.AdminTransaction, db.session,
                                  name='AdminTransaction'))
    admin.add_view(LoginModelView(models.ProfilePicture, db.session,
                                  name='ProfilePicture'))
    admin.add_view(LoginModelView(models.RegistrationRequest, db.session,
                                  name='RegistrationRequest'))

    return admin


def setup_flask_babel(app):
    import flask_babel
    from flask import request
    from flask import session
    from flask_login import current_user
    from flasquelistan import models

    babel = flask_babel.Babel(app)

    app.jinja_env.globals['format_datetime'] = flask_babel.format_datetime
    app.jinja_env.globals['format_date'] = flask_babel.format_date
    app.jinja_env.globals['format_currency'] = flask_babel.format_currency

    @babel.localeselector
    def get_locale():
        # Check if user is logged in, if so, use the users stored preferences
        if current_user.is_authenticated:
            if request.args.get('lang'):
                current_user.lang = request.args.get('lang')
                models.db.session.commit()
                flask_babel.refresh()
            return current_user.lang
        # Check the session cookie if the user isn't logged in
        else:
            if request.args.get('lang'):
                session['lang'] = request.args.get('lang')
                flask_babel.refresh()
            return session.get('lang', None)

    @babel.timezoneselector
    def get_timezone():
        # Used to change the time zone.
        # user = getattr(g, 'user', None)
        # if user is not None:
        #    return user.timezone
        return None
    return babel


def setup_flask_uploads(app):
    import flask_uploads
    from flasquelistan import util

    flask_uploads.configure_uploads(app, util.image_uploads)
    flask_uploads.configure_uploads(app, util.profile_pictures)

    app.jinja_env.globals['url_for_image'] = util.url_for_image


def setup_csrf_protection(app):
    from flask_wtf.csrf import CSRFProtect
    return CSRFProtect(app)
