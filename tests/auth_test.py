import base64
import datetime
import hashlib

from itsdangerous import SignatureExpired, URLSafeTimedSerializer

from flasquelistan import models
from tests.helpers import logged_in


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


def make_legacy_hash(password, salt='saltysalt', rounds=1000):
    """Build a Django-style pbkdf2 hash like the ones imported from the
    old teknologkoren/Strequelistan database."""
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(),
                             rounds)
    return 'pbkdf2_sha256${}${}${}'.format(
        rounds, salt, base64.b64encode(dk).decode()
    )


def captcha_answer(app, n):
    s = (app.config['SECRET_KEY'] + str(n)).encode()
    return hashlib.sha256(s).hexdigest()


class TestLegacyPasswordUpgrade:
    def test_correct_password_upgrades_hash_to_bcrypt(self, app):
        user = make_user()
        user._password_hash = make_legacy_hash('correct horse')
        models.db.session.commit()

        assert models.User.authenticate('monty@python.tld',
                                        'correct horse') is user
        # The stored hash must have been upgraded to bcrypt.
        assert user._password_hash.startswith('$2')
        # The password still verifies against the new hash.
        assert user.verify_password('correct horse')

    def test_wrong_password_leaves_hash_unchanged(self, app):
        user = make_user()
        legacy_hash = make_legacy_hash('correct horse')
        user._password_hash = legacy_hash
        models.db.session.commit()

        assert models.User.authenticate('monty@python.tld',
                                        'wrong horse') is None
        assert user._password_hash == legacy_hash


class TestRegister:
    def register_data(self, app, **overrides):
        data = {
            'email': 'brian@pfoj.tld',
            'first_name': 'Brian',
            'last_name': 'Smith',
            'phone': '0701234567',
            'message': 'Romanes eunt domus',
            'are_you_a_robot-question': '7',
            'are_you_a_robot-answer': captcha_answer(app, 7),
        }
        data.update(overrides)
        return data

    def test_register_creates_request_and_notifies_admin(
            self, app, client, monkeypatch):
        sent = []
        monkeypatch.setattr('flasquelistan.util.send_email',
                            lambda *args: sent.append(args))

        response = client.post('/register', data=self.register_data(app))

        assert response.status_code == 302
        request = models.RegistrationRequest.query.filter_by(
            email='brian@pfoj.tld').first()
        assert request is not None
        assert request.first_name == 'Brian'
        assert len(sent) == 1
        assert sent[0][1] == app.config['ADMIN_EMAILADDR']

    def test_register_with_wrong_captcha_fails(self, app, client, monkeypatch):
        sent = []
        monkeypatch.setattr('flasquelistan.util.send_email',
                            lambda *args: sent.append(args))

        data = self.register_data(
            app, **{'are_you_a_robot-answer': 'not-the-right-hash'}
        )
        response = client.post('/register', data=data)

        assert response.status_code == 200
        assert models.RegistrationRequest.query.count() == 0
        assert sent == []


class TestPasswordReset:
    def test_no_user_enumeration(self, app, client, monkeypatch):
        sent = []
        monkeypatch.setattr('flasquelistan.util.send_email',
                            lambda *args: sent.append(args))
        make_user()

        known = client.post('/reset/', data={'email': 'monty@python.tld'})
        unknown = client.post('/reset/', data={'email': 'ghost@python.tld'})

        # Same response whether or not the address is registered.
        assert known.status_code == unknown.status_code == 302
        assert known.headers['Location'] == unknown.headers['Location']

        # But only the registered address got an email.
        assert len(sent) == 1
        assert sent[0][1] == 'monty@python.tld'

    def test_reset_token_flow(self, app, client):
        user = make_user()
        user.password = 'oldpassword'
        # itsdangerous truncates token timestamps to whole seconds, so a
        # token created in the same second as the last password change is
        # rejected as expired. Backdate the password change a bit, like it
        # would be in reality.
        user._password_timestamp -= datetime.timedelta(seconds=5)
        models.db.session.commit()

        ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        token = ts.dumps(user.id, salt='recover-key')

        response = client.get(f'/reset/{token}')
        assert response.status_code == 200

        response = client.post(f'/reset/{token}',
                               data={'new_password': 'brandnewpassword'})
        assert response.status_code == 302
        assert response.headers['Location'].startswith('/login')

        assert models.User.authenticate('monty@python.tld',
                                        'brandnewpassword') is user
        assert models.User.authenticate('monty@python.tld',
                                        'oldpassword') is None

    def test_token_invalid_after_password_change(self, app, client):
        user = make_user()
        user.password = 'oldpassword'
        models.db.session.commit()

        ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        token = ts.dumps(user.id, salt='recover-key')

        # Password is changed after the token was created...
        user.password = 'somethingelse'
        models.db.session.commit()

        # ...so the token must no longer grant a password reset.
        response = client.get(f'/reset/{token}')
        assert response.status_code == 302
        assert response.headers['Location'].startswith('/login')

        response = client.post(f'/reset/{token}',
                               data={'new_password': 'attackerpassword'})
        assert response.status_code == 302
        assert models.User.authenticate('monty@python.tld',
                                        'attackerpassword') is None

    def test_token_with_wrong_salt_rejected(self, app, client):
        user = make_user()
        user.password = 'oldpassword'
        models.db.session.commit()

        ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        token = ts.dumps(user.id, salt='some-other-salt')

        response = client.get(f'/reset/{token}')
        assert response.status_code == 302
        assert response.headers['Location'].startswith('/login')

    def test_expired_reset_token_redirects(self, app, client, monkeypatch):
        make_user()

        def raise_expired(self, *args, **kwargs):
            raise SignatureExpired('expired')

        monkeypatch.setattr(
            'flasquelistan.views.auth.URLSafeTimedSerializer.loads',
            raise_expired
        )

        response = client.get('/reset/some-token')
        assert response.status_code == 302
        assert response.headers['Location'].startswith('/login')


class TestVerifyTokenExpiry:
    def test_expired_verify_token_redirects(self, app, client, monkeypatch):
        user = make_user()

        def raise_expired(self, *args, **kwargs):
            raise SignatureExpired('expired')

        monkeypatch.setattr(
            'flasquelistan.views.auth.URLSafeTimedSerializer.loads',
            raise_expired
        )

        response = client.get('/verify/some-token')
        assert response.status_code == 302
        assert response.headers['Location'].startswith('/login')
        assert user.email == 'monty@python.tld'


class TestOpenRedirect:
    def make_user_with_password(self):
        user = make_user()
        user.password = 'solidsnake'
        models.db.session.commit()
        return user

    def test_login_next_offsite_not_followed(self, app, client):
        self.make_user_with_password()

        response = client.post('/login', data={
            'email': 'monty@python.tld',
            'password': 'solidsnake',
            'next': 'https://evil.tld/x',
        })

        assert response.status_code == 302
        assert 'evil.tld' not in response.headers['Location']

    def test_login_next_protocol_relative_not_followed(self, app, client):
        self.make_user_with_password()

        response = client.post('/login', data={
            'email': 'monty@python.tld',
            'password': 'solidsnake',
            'next': '//evil.tld/x',
        })

        assert response.status_code == 302
        assert not response.headers['Location'].startswith('//evil.tld')
        assert 'evil.tld' not in response.headers['Location']


class TestAdminRequired:
    def test_non_admin_browser_request_redirected(self, app, client):
        with logged_in(client):
            response = client.get('/admin/')

            assert response.status_code == 302
            assert response.headers['Location'] == '/'

    def test_non_admin_json_request_403(self, app, client):
        with logged_in(client):
            response = client.get('/admin/', json={'ping': 'pong'})

            assert response.status_code == 403

    def test_anonymous_redirected_to_login(self, app, client):
        response = client.get('/admin/')

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
