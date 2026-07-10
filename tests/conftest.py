import pytest

from flasquelistan import factory


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
