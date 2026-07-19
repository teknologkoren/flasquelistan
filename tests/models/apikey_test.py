from flasquelistan import models

from tests.helpers import make_user


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
