import flask

from flasquelistan import models
from tests.helpers import logged_in


class TestLocaleSelection:
    """The ?lang= query parameter selects the UI language."""

    def test_default_language_is_swedish(self, client):
        response = client.get('/login')
        assert 'Håll mig inloggad' in response.get_data(as_text=True)

    def test_anonymous_lang_param_switches_language(self, client):
        response = client.get('/login?lang=en')
        assert 'Keep me logged in' in response.get_data(as_text=True)

    def test_anonymous_lang_param_is_remembered_in_session(self, client):
        with client:
            client.get('/login?lang=en')
            assert flask.session['lang'] == 'en'

            # The choice sticks on the next request without the parameter.
            response = client.get('/login')
            assert 'Keep me logged in' in response.get_data(as_text=True)

    def test_logged_in_lang_param_is_saved_on_user(self, client):
        with logged_in(client) as user:
            client.get(f'/profile/{user.id}/?lang=en')
            assert models.db.session.get(models.User, user.id).lang == 'en'

    def test_logged_in_user_gets_their_saved_language(self, client):
        with logged_in(client) as user:
            user.lang = 'en'
            models.db.session.commit()
            response = client.get(f'/profile/{user.id}/')
            assert "It's empty here, strequa more!" in response.get_data(as_text=True)
