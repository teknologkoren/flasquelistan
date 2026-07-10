#!/usr/bin/env python3


import pytest

from flask import url_for

from flasquelistan import factory, models

from tests.helpers import logged_in


GOOFS_CONFIG = {
    'monty_pictures': {
        'enabled': True,
        'type': 'random_picture',
        'route': '/monty-pictures',
        'user_id': 1,
        'title': 'Random Pictures',
    },
    'more-monty': {
        'enabled': True,
        'type': 'random_picture',
        'route': '/more-monty',
        'user_id': 1,
        'title': 'More Pictures',
    },
    'disabled_goof': {
        'enabled': False,
        'type': 'random_picture',
        'route': '/disabled-goof',
        'user_id': 1,
        'title': 'Disabled Pictures',
    },
}


@pytest.fixture
def app():
    config = {
        # Use an in-memory database for faster test execution.
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        # Disable CSRF in unit tests.
        'WTF_CSRF_ENABLED': False,
        'TESTING': True,
        'IMAGE_SECRET': 'not a secret',
        'IMAGE_EXPIRY': 3600,
        'GOOFS_CONFIG': GOOFS_CONFIG,
    }

    app = factory.create_app(config)
    with app.app_context():
        yield app


class TestGoofs:
    """Tests dynamically registered goof routes"""

    def test_goof_route_requires_login(self, client):
        rv = client.get('/monty-pictures')

        assert rv.status_code == 302
        assert rv.headers['Location'].startswith('/login')

    def test_goof_route_logged_in(self, client):
        with logged_in(client) as user:
            pic = models.ProfilePicture(
                filename='monty.jpg',
                user_id=user.id,
            )

            models.db.session.add(pic)
            models.db.session.commit()

            for route in ('/monty-pictures', '/more-monty'):
                rv = client.get(route)
                assert rv.status_code == 200

    def test_disabled_goof_not_registered(self, client):
        with logged_in(client):
            rv = client.get('/disabled-goof')
            assert rv.status_code == 404

    def test_goof_endpoint_names_are_stable(self, app):
        """Endpoint names must not change between app restarts.

        hash() of a string is randomized per process (PYTHONHASHSEED),
        so hash()-derived endpoint names would fail this test.
        """
        endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}

        assert 'goofs.monty_pictures' in endpoints
        assert 'goofs.more_monty' in endpoints

        with app.test_request_context():
            assert url_for('goofs.monty_pictures') == '/monty-pictures'
            assert url_for('goofs.more_monty') == '/more-monty'
