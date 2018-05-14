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
    setup_flask_assets(app)
    setup_flask_babel(app)

    return app


def register_blueprints(app):
    from flasquelistan.views import auth, quotes, strequelistan
    app.register_blueprint(auth.mod)
    app.register_blueprint(strequelistan.mod)
    app.register_blueprint(quotes.mod)


def register_cli(app):
    @app.cli.command('initdb')
    def initdb_command():
        init_db(app)

    @app.cli.command('dropdb')
    def dropdb_command():
        from flasquelistan import models
        if click.confirm(('You are about to DROP all tables, are you sure you '
                          'want to do this?'), abort=True):
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
        )

        models.db.session.add(user)
        models.db.session.commit()


def populate_testdb():
    from flasquelistan import models
    monty = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
        phone='0700011223',
        balance=10000,
    )

    rick = models.User(
        email='rick_astley@example.com',
        first_name='Rick',
        nickname='The Roll',
        last_name='Astley',
        phone='0703322110',
    )

    soprano = models.Group(
        name='Sopran',
        weight='10',
    )

    alto = models.Group(
        name='Alt',
        weight='20',
    )

    tenor = models.Group(
        name='Tenor',
        weight='30',
    )

    bass = models.Group(
        name='Bas',
        weight='40',
    )

    streque = models.Streque(value=400)

    quote1 = models.Quote(
        text="Kom igen, testa citaten, det blir kul!",
        who="Någon, om Strequelistan",
    )

    quote2 = models.Quote(text="Ett citat utan upphovsman, spännade!")

    models.db.session.add_all([monty, rick, soprano, alto, tenor, bass,
                               streque, quote1, quote2])
    models.db.session.commit()

    monty.group = tenor
    rick.group = bass

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

    admin = flask_admin.Admin(app, name='Flasquelistan',
                              index_view=LoginIndexView())
    admin.add_view(LoginModelView(models.User, db.session, name='User'))
    admin.add_view(LoginModelView(models.Group, db.session, name='Group'))
    admin.add_view(LoginModelView(models.Streque, db.session, name='Streque'))
    admin.add_view(LoginModelView(models.Quote, db.session, name='Quote'))
    admin.add_view(LoginModelView(models.Transaction, db.session,
                                  name='Transaction'))

    return admin


def setup_flask_assets(app):
    from flask_assets import Environment, Bundle

    assets = Environment(app)

    bundles = {
        'js_common': Bundle(
            'js/common.js',
            output='gen/common.js'
        ),
        'js_streque': Bundle(
            'js/addStreque.js',
            'js/userFilter.js',
            output='gen/streque.js'
        ),
        'js_history': Bundle(
            'js/history.js',
            output='gen/history.js'
        ),
        'css_all': Bundle(
            'css/lib/normalize.css',
            'css/style.css',
            'css/streque.css',
            'css/quotes.css',
            output='gen/style.css'
        )
    }

    assets.register(bundles)

    return assets


def setup_flask_babel(app):
    import flask_babel

    babel = flask_babel.Babel(app)

    app.jinja_env.globals['format_datetime'] = flask_babel.format_datetime
    app.jinja_env.globals['format_date'] = flask_babel.format_date

    return babel
