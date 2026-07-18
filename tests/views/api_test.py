from flasquelistan import models


def make_api_user(email='monty@python.tld', admin=False, key_admin=None,
                  **user_kwargs):
    """Create a user with an API key, return (user, key, plaintext_key)."""
    user = models.User(
        email=email,
        first_name='Monty',
        last_name='Python',
        **user_kwargs,
    )
    user.is_admin = admin
    models.db.session.add(user)
    models.db.session.commit()

    plaintext = models.ApiKey.generate_key()
    key = models.ApiKey(user_id=user.id, name=f'test key {email}')
    key.api_key = plaintext
    key.has_admin_privileges = admin if key_admin is None else key_admin
    models.db.session.add(key)
    models.db.session.commit()

    return user, key, plaintext


def auth_header(plaintext_key):
    return {'Authorization': f'Bearer {plaintext_key}'}


class TestQuotesMinId:
    def test_quotes_with_min_id(self, client):
        """Regression test: ?min_id used to crash with a str/int TypeError."""
        _, _, key = make_api_user()
        for text in ('Ni!', 'Ekke ekke!'):
            models.db.session.add(models.Quote(text=text, who='riddare'))
        models.db.session.commit()

        response = client.get('/api/v1/quotes?min_id=2',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert [quote['id'] for quote in response.json] == [2]

    def test_quotes_with_invalid_min_id(self, client):
        _, _, key = make_api_user()

        response = client.get('/api/v1/quotes?min_id=bogus',
                              headers=auth_header(key))
        assert response.status_code == 400
