import pathlib
from contextlib import contextmanager

import pytest
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

from flasquelistan import factory, models


def _compile_translations():
    """Compile gettext catalogs so the locale tests see translated pages.

    The compiled .mo files are gitignored, so fresh checkouts (CI included)
    have none and Flask-Babel would silently fall back to the msgids.
    """
    root = pathlib.Path(__file__).parent.parent / 'flasquelistan' / 'translations'
    for po_path in root.glob('*/LC_MESSAGES/messages.po'):
        mo_path = po_path.with_suffix('.mo')
        if not mo_path.exists() or mo_path.stat().st_mtime < po_path.stat().st_mtime:
            with open(po_path, 'rb') as f:
                catalog = read_po(f)
            with open(mo_path, 'wb') as f:
                write_mo(f, catalog)


_compile_translations()

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
