import hashlib
from contextlib import contextmanager

from flasquelistan import models

# The app and client pytest fixtures live in tests/conftest.py, where pytest
# picks them up automatically without imports.


def make_user(email='monty@python.tld', first_name='Monty',
              last_name='Python', balance=0, **kwargs):
    """Create a user, commit it to the database and return it."""
    user = models.User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        balance=balance,
        **kwargs
    )
    models.db.session.add(user)
    models.db.session.commit()
    return user


def captcha_answer(app, n):
    """Compute the expected captcha answer for question `n`."""
    s = (app.config['SECRET_KEY'] + str(n)).encode()
    return hashlib.sha256(s).hexdigest()


@contextmanager
def logged_in(client):
    """Fixture for a signed in user"""
    user = make_user()

    user.password = 'solidsnake'
    models.db.session.commit()

    with client:
        rv = login(client, 'monty@python.tld', 'solidsnake')
        assert rv.status_code == 302
        yield user


@contextmanager
def logged_in_admin(client):
    """Fixture for a signed in user"""
    user = make_user(is_admin=True)

    user.password = 'solidsnake'
    models.db.session.commit()

    with client:
        rv = login(client, 'monty@python.tld', 'solidsnake')
        assert rv.status_code == 302
        yield user


def login(client, email, password):
    return client.post('/login', data={
        'email': email, 'password': password
    })


def logout(client):
    return client.get('/logout', follow_redirects=True)
