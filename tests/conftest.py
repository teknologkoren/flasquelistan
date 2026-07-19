from contextlib import contextmanager

import pytest

from flasquelistan import factory, models

# Base config shared by all test apps. Test modules that need extra
# settings compose with it: `{**BASE_TEST_CONFIG, ...overrides...}`.
BASE_TEST_CONFIG = {
    # Use an in-memory database for faster test execution.
    'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    # Disable CSRF in unit tests.
    'WTF_CSRF_ENABLED': False,
    'TESTING': True,
}


@contextmanager
def fresh_database(app):
    """Push an app context and give the test a clean database.

    Creating an app is slow (~0.2 s), so test apps are created once per
    session/module and each test instead gets a cheap drop_all/create_all
    reset on the in-memory database.
    """
    with app.app_context():
        models.db.drop_all()
        models.db.create_all()
        yield app
        models.db.session.remove()


@pytest.fixture(scope='session')
def _app():
    """The Flask app, created once per test session."""
    return factory.create_app(BASE_TEST_CONFIG)


@pytest.fixture
def app(_app):
    """The session app, with a fresh database for every test."""
    with fresh_database(_app) as app:
        yield app


@pytest.fixture
def client(app):
    return app.test_client()
