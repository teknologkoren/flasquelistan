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

    @app.cli.command('populatetestdb')
    def populatetestdb_command():
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

        streque = models.Streque(value=400)

        quote1 = models.Quote(
            text="Kom igen, testa citaten, det blir kul!",
            who="Någon, om Strequelistan",
        )

        quote2 = models.Quote(text="Ett citat utan upphovsman, spännade!")

        models.db.session.add_all([monty, rick, streque, quote1, quote2])
        models.db.session.commit()


def init_db(app):
    from flasquelistan import models
    models.db.create_all(app=app)


def setup_flask_admin(app, db):
    import flask_admin
    from flasquelistan import models
    from flask_admin.contrib.sqla import ModelView

    admin = flask_admin.Admin(app, name='Flasquelistan')
    admin.add_view(ModelView(models.User, db.session, name='User'))
    admin.add_view(
            ModelView(models.Transaction, db.session, name='Transaction'))
    admin.add_view(ModelView(models.Streque, db.session, name='Streque'))
    admin.add_view(ModelView(models.Quote, db.session, name='Quote'))

    return admin


def setup_flask_assets(app):
    from flask_assets import Environment, Bundle

    assets = Environment(app)

    bundles = {
        'js_streque': Bundle(
            'js/streque.js',
            'js/addStreque.js',
            'js/voidTransaction.js',
            output='gen/streque.js'
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
