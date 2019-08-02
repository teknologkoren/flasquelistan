#!/usr/bin/env python3

import pytest
from contextlib import contextmanager
from flasquelistan import factory, models


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


@contextmanager
def logged_in(client):
    """Fixture for a signed in user"""
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
    )

    models.db.session.add(user)
    models.db.session.commit()

    user.password = 'solidsnake'
    models.db.session.commit()

    with client:
        rv = login(client, 'monty@python.tld', 'solidsnake')
        assert rv.status_code == 302
        yield user


def login(client, email, password):
    return client.post('/login', data=dict(
        email=email, password=password
    ))


def logout(client):
    return client.get('/logout', follow_redirects=True)
