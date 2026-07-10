from contextlib import contextmanager

from flasquelistan import models

# The app and client pytest fixtures live in tests/conftest.py, where pytest
# picks them up automatically without imports.


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


@contextmanager
def logged_in_admin(client):
    """Fixture for a signed in user"""
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
    )

    user.is_admin = True

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
