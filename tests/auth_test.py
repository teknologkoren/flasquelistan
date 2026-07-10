from itsdangerous import URLSafeTimedSerializer

from flasquelistan import models


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


class TestApiKeyAuthenticate:
    def test_valid_key(self, app):
        user = make_user()
        key = models.ApiKey.generate_key()
        api_key = models.ApiKey(name='test', user_id=user.id, is_enabled=True)
        api_key.api_key = key
        models.db.session.add(api_key)
        models.db.session.commit()

        assert models.ApiKey.authenticate(key) == api_key

    def test_unknown_key_returns_none(self, app):
        assert models.ApiKey.authenticate('not-a-real-key') is None

    def test_disabled_key_returns_none(self, app):
        user = make_user()
        key = models.ApiKey.generate_key()
        api_key = models.ApiKey(name='test', user_id=user.id, is_enabled=False)
        api_key.api_key = key
        models.db.session.add(api_key)
        models.db.session.commit()

        assert models.ApiKey.authenticate(key) is None
