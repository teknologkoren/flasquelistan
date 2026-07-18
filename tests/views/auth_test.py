from flask import url_for
from flask_login import current_user
from itsdangerous import URLSafeTimedSerializer

from flasquelistan import models

from tests.helpers import login


def make_user():
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
    )
    models.db.session.add(user)
    models.db.session.commit()
    return user


class TestVerifyEmailToken:
    def test_valid_token_sets_email(self, app, client):
        user = make_user()
        ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        token = ts.dumps([user.id, 'new@python.tld'], salt='verify-email')

        response = client.get(f'/verify/{token}')

        assert response.status_code == 302
        assert user.email == 'new@python.tld'

    def test_garbage_token_404s(self, app, client):
        user = make_user()

        response = client.get('/verify/garbage-token')

        assert response.status_code == 404
        assert user.email == 'monty@python.tld'


class TestResetPasswordToken:
    def test_garbage_token_redirects_to_login(self, client):
        make_user()

        response = client.get('/reset/garbage-token')

        assert response.status_code == 302
        assert response.headers['Location'].startswith('/login')

    def test_token_for_deleted_user_redirects_to_login(self, app, client):
        # A valid token whose user has since been deleted must not crash.
        ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        token = ts.dumps(12345, salt='recover-key')

        response = client.get(f'/reset/{token}')

        assert response.status_code == 302
        assert response.headers['Location'].startswith('/login')


class TestAuth:
    """Tests authentication functions"""

    def test_must_login_redirect(self, client):
        """Tests that users get redirected to the login page"""
        rv = client.get('/')

        assert rv.status_code == 302
        assert rv.headers['Location'] == '/login?next=%2F'

    def test_login_logout(self, app):
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
            assert rv.headers['Location'] == '/'
            assert rv.status_code == 302

            # Log out
            rv = client.get('/logout')

            # Check that logout redirect to login page
            assert rv.headers['Location'].endswith(url_for('auth.login'))

            # Check that current_user is unset
            assert not hasattr(current_user, 'id')
