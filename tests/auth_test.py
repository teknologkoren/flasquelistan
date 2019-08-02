#!/usr/bin/env python3
#
# This file is for authentication related tests
#

import pytest

from flask import url_for
from flask_login import current_user
from flask_login.mixins import AnonymousUserMixin
from flasquelistan import models

from tests.helpers import app
from tests.helpers import client
from tests.helpers import login
from tests.helpers import logout


def test_must_login_redirect(client):
    """Tests that users get redirected to the login page"""
    rv = client.get('/')

    assert rv.status_code == 302
    assert rv.headers['Location'] == 'http://localhost/login?next=%2F'


def test_login_logout(app):
    # Create 2 users
    user = models.User(
            email='monty@python1.tld',
            first_name='Monty',
            last_name='Python',
    )

    models.db.session.add(user)
    models.db.session.commit()

    user = models.User(
            email='monty@python2.tld',
            first_name='Monty',
            last_name='Python',
    )

    models.db.session.add(user)
    models.db.session.commit()

    user.password = 'solidsnake'
    models.db.session.commit()

    with app.test_client() as client:
        # Log in with wrong credentials
        rv = login(client, 'monty@python2.tld', 'liquidsnake')

        # Check that login failed
        assert not hasattr(current_user, 'id')

        # Check status code, no redirect should have been preformed
        assert rv.status_code == 200

        # Log in with correct credentials
        rv = login(client, 'monty@python2.tld', 'solidsnake')

        # Check if the correct user is logged in
        assert current_user.id == user.id

        # Check if redirect worked as expected
        assert rv.headers['Location'] == 'http://localhost/'
        assert rv.status_code == 302

        # Log out
        rv = client.get('/logout')

        # Check that logout redirect to login page
        assert rv.headers['Location'].endswith( url_for('auth.login'))

        # Check that current_user is unset
        assert not hasattr(current_user, 'id')
