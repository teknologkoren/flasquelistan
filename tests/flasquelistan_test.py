import tempfile

import pytest
from flask import url_for
from flask_login import current_user

from flasquelistan import factory, forms, models


@pytest.fixture
def app():
    config = {
        # Use an in-memory database for faster test execution.
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
         # Disable CSRF in unit tests.
        'WTF_CSRF_ENABLED': False,
        'TESTING': True,
    }

    app = factory.create_app(config)
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email, password):
    return client.post('/login', data=dict(
         email=email, password=password
    ))


def logout(client):
    return client.get('/logout', follow_redirects=True)


def test_must_login_redirect(client):
    """Tests that users get redirected to the login page"""
    rv = client.get('/')

    assert rv.status_code == 302
    assert rv.headers['Location'] == 'http://localhost/login?next=%2F'

def test_successful_login(app):
    user = models.User(
            email='monty@python.tld',
            first_name='Monty',
            last_name='Python',
    )

    models.db.session.add(user)
    models.db.session.commit()

    user.password = 'solidsnake'
    models.db.session.commit()

    with app.test_client() as client:
        rv = login(client, 'monty@python.tld', 'solidsnake')
        assert rv.status_code == 302
        assert rv.headers['Location'] == 'http://localhost/'

def test_empty_quotes(app):
    """Test with blank database"""
    user = models.User(
            email='monty@python.tld',
            first_name='Monty',
            last_name='Python',
    )

    models.db.session.add(user)
    models.db.session.commit()

    user.password = 'solidsnake'
    models.db.session.commit()

    with app.test_client() as client:
        rv = login(client, 'monty@python.tld', 'solidsnake')
        assert rv.status_code == 302

        rv = client.get(url_for('quotes.index'))
        assert b'No quotes yet!' in rv.data


def test_user_model(app):
    user = models.User(
            email='monty@python.tld',
            first_name='Monty',
            last_name='Python',
            phone='0700011223',
    )

    models.db.session.add(user)
    models.db.session.commit()

    assert user.id > 0


def test_streque_model(app):
    streque = models.Streque(value=400)

    models.db.session.add(streque)
    models.db.session.commit()

    assert streque.id > 0
