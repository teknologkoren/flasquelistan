import datetime

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


def make_article(name='Holy Grail', value=10000, weight=1, is_active=True):
    article = models.Article(
        weight=weight,
        name=name,
        value=value,
        description="Difficult to find. Watch out for the rabbit.",
        standardglas=2,
        is_active=is_active,
    )
    models.db.session.add(article)
    models.db.session.commit()
    return article


def make_transactions(user, count):
    transactions = []
    for i in range(count):
        transaction = models.Transaction(
            text=f'transaction {i}',
            value=-100,
            user_id=user.id,
        )
        models.db.session.add(transaction)
        transactions.append(transaction)
    models.db.session.commit()
    return transactions


class TestAuthentication:
    def test_no_authorization_header(self, client):
        response = client.get('/api/v1/users/me')
        assert response.status_code == 401

    def test_garbage_token(self, client):
        make_api_user()
        response = client.get('/api/v1/users/me',
                              headers=auth_header('notavalidkey'))
        assert response.status_code == 401

    def test_disabled_key(self, client):
        _, api_key, key = make_api_user()
        api_key.is_enabled = False
        models.db.session.commit()

        response = client.get('/api/v1/users/me', headers=auth_header(key))
        assert response.status_code == 401


class TestAdminAuthorization:
    def test_admin_key_with_non_admin_owner_is_forbidden(self, client):
        """An admin-privileged key owned by a non-admin user must not grant
        admin access (privilege-escalation guard)."""
        _, _, key = make_api_user(admin=False, key_admin=True)

        response = client.get('/api/v1/transactions',
                              headers=auth_header(key))
        assert response.status_code == 403

    def test_admin_key_with_admin_owner_is_allowed(self, client):
        _, _, key = make_api_user(admin=True)

        response = client.get('/api/v1/transactions',
                              headers=auth_header(key))
        assert response.status_code == 200


class TestUserDataFiltering:
    def test_non_admin_key_gets_filtered_user_data(self, client):
        _, _, key = make_api_user()

        response = client.get('/api/v1/users/me', headers=auth_header(key))
        assert response.status_code == 200
        assert 'balance' not in response.json
        assert 'is_admin' not in response.json
        assert response.json['email'] == 'monty@python.tld'

    def test_admin_key_gets_full_user_data(self, client):
        _, _, key = make_api_user(admin=True)

        response = client.get('/api/v1/users/me', headers=auth_header(key))
        assert response.status_code == 200
        assert response.json['balance'] == 0
        assert response.json['is_admin'] is True


class TestUsers:
    def test_get_users_only_lists_active(self, client):
        _, _, key = make_api_user(email='monty@python.tld', active=True)
        inactive = models.User(email='brian@pfj.tld', first_name='Brian',
                               last_name='Cohen')
        models.db.session.add(inactive)
        models.db.session.commit()

        response = client.get('/api/v1/users', headers=auth_header(key))
        assert response.status_code == 200
        emails = [user['email'] for user in response.json]
        assert emails == ['monty@python.tld']

    def test_get_user_by_id(self, client):
        user, _, key = make_api_user()

        response = client.get(f'/api/v1/users/{user.id}',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert response.json['id'] == user.id

    def test_get_unknown_user(self, client):
        _, _, key = make_api_user()

        response = client.get('/api/v1/users/1337', headers=auth_header(key))
        assert response.status_code == 404


class TestUserLookups:
    def test_get_user_by_phone_national_format(self, client):
        user, _, key = make_api_user(phone='0701234567')
        assert user.phone == '+46701234567'  # Normalized by the model.

        response = client.get('/api/v1/users/by-phone/0701234567',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert response.json['id'] == user.id

    def test_get_user_by_unknown_phone(self, client):
        _, _, key = make_api_user(phone='0701234567')

        response = client.get('/api/v1/users/by-phone/0701111111',
                              headers=auth_header(key))
        assert response.status_code == 404

    def test_get_user_by_discord(self, client):
        user, _, key = make_api_user(discord_user_id='123456789')

        response = client.get('/api/v1/users/by-discord/123456789',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert response.json['id'] == user.id

    def test_get_user_by_unknown_discord(self, client):
        _, _, key = make_api_user()

        response = client.get('/api/v1/users/by-discord/987654321',
                              headers=auth_header(key))
        assert response.status_code == 404

    def test_get_users_by_birthday(self, client):
        user, _, key = make_api_user(birthday=datetime.date(1990, 5, 17))
        # A user without birthday must not crash the endpoint.
        no_birthday = models.User(email='brian@pfj.tld', first_name='Brian',
                                  last_name='Cohen')
        models.db.session.add(no_birthday)
        models.db.session.commit()

        response = client.get('/api/v1/users/by-birthday/5/17',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert [u['id'] for u in response.json] == [user.id]

    def test_get_users_by_birthday_no_match(self, client):
        _, _, key = make_api_user(birthday=datetime.date(1990, 5, 17))

        response = client.get('/api/v1/users/by-birthday/1/1',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert response.json == []


class TestStreque:
    def test_streque_me(self, client):
        user, api_key, key = make_api_user()
        article = make_article(value=1200)

        response = client.post(f'/api/v1/users/me/streque/{article.id}',
                               headers=auth_header(key))
        assert response.status_code == 200
        assert response.json['value'] == -1200
        assert response.json['user_id'] == user.id
        assert response.json['api_key_id'] == api_key.id
        assert user.balance == -1200

    def test_streque_other_user(self, client):
        user, api_key, key = make_api_user()
        other = models.User(email='brian@pfj.tld', first_name='Brian',
                            last_name='Cohen')
        models.db.session.add(other)
        models.db.session.commit()
        article = make_article(value=500)

        response = client.post(
            f'/api/v1/users/{other.id}/streque/{article.id}',
            headers=auth_header(key))
        assert response.status_code == 200
        assert response.json['user_id'] == other.id
        assert response.json['created_by_id'] == user.id
        assert response.json['api_key_id'] == api_key.id
        assert other.balance == -500
        assert user.balance == 0

    def test_streque_unknown_article(self, client):
        _, _, key = make_api_user()

        response = client.post('/api/v1/users/me/streque/1337',
                               headers=auth_header(key))
        assert response.status_code == 404

    def test_streque_unknown_user(self, client):
        _, _, key = make_api_user()
        article = make_article()

        response = client.post(f'/api/v1/users/1337/streque/{article.id}',
                               headers=auth_header(key))
        assert response.status_code == 404


class TestArticles:
    def test_only_active_articles_ordered_by_weight(self, client):
        _, _, key = make_api_user()
        make_article(name='Spam', weight=1)
        make_article(name='Egg', weight=3)
        make_article(name='Bacon', weight=2)
        make_article(name='Ni', weight=9000, is_active=False)

        response = client.get('/api/v1/articles', headers=auth_header(key))
        assert response.status_code == 200
        assert [article['name'] for article in response.json] == \
            ['Egg', 'Bacon', 'Spam']


class TestUserTransactions:
    def test_other_user_forbidden_for_non_admin(self, client):
        _, _, key = make_api_user()
        other = models.User(email='brian@pfj.tld', first_name='Brian',
                            last_name='Cohen')
        models.db.session.add(other)
        models.db.session.commit()

        response = client.get(f'/api/v1/users/{other.id}/transactions',
                              headers=auth_header(key))
        assert response.status_code == 403

    def test_own_transactions_allowed_for_non_admin(self, client):
        user, _, key = make_api_user()
        make_transactions(user, 2)

        response = client.get(f'/api/v1/users/{user.id}/transactions',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert len(response.json) == 2

    def test_other_user_allowed_for_admin(self, client):
        _, _, key = make_api_user(admin=True)
        other = models.User(email='brian@pfj.tld', first_name='Brian',
                            last_name='Cohen')
        models.db.session.add(other)
        models.db.session.commit()
        make_transactions(other, 1)

        response = client.get(f'/api/v1/users/{other.id}/transactions',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert len(response.json) == 1

    def test_min_id_filter(self, client):
        user, _, key = make_api_user()
        transactions = make_transactions(user, 3)

        response = client.get(
            f'/api/v1/users/{user.id}/transactions'
            f'?min_id={transactions[1].id}',
            headers=auth_header(key))
        assert response.status_code == 200
        assert [t['id'] for t in response.json] == \
            [transactions[1].id, transactions[2].id]

    def test_invalid_min_id(self, client):
        user, _, key = make_api_user()

        response = client.get(
            f'/api/v1/users/{user.id}/transactions?min_id=abc',
            headers=auth_header(key))
        assert response.status_code == 400


class TestTransactions:
    def test_get_all_transactions(self, client):
        user, _, key = make_api_user(admin=True)
        transactions = make_transactions(user, 3)

        response = client.get('/api/v1/transactions',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert [t['id'] for t in response.json] == \
            [t.id for t in transactions]

    def test_min_id_filter(self, client):
        user, _, key = make_api_user(admin=True)
        transactions = make_transactions(user, 3)

        response = client.get(
            f'/api/v1/transactions?min_id={transactions[2].id}',
            headers=auth_header(key))
        assert response.status_code == 200
        assert [t['id'] for t in response.json] == [transactions[2].id]

    def test_limit_and_order_desc(self, client):
        user, _, key = make_api_user(admin=True)
        transactions = make_transactions(user, 3)

        response = client.get('/api/v1/transactions?order=desc&limit=2',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert [t['id'] for t in response.json] == \
            [transactions[2].id, transactions[1].id]

    def test_invalid_min_id(self, client):
        _, _, key = make_api_user(admin=True)

        response = client.get('/api/v1/transactions?min_id=abc',
                              headers=auth_header(key))
        assert response.status_code == 400

    def test_unicode_digit_min_id(self, client):
        """Superscript digits pass str.isdigit() but crash int()."""
        _, _, key = make_api_user(admin=True)

        response = client.get('/api/v1/transactions?min_id=²',
                              headers=auth_header(key))
        assert response.status_code == 400

    def test_out_of_range_min_id(self, client):
        """Values beyond SQLite's 64-bit range crash at query execution."""
        _, _, key = make_api_user(admin=True)

        response = client.get(
            '/api/v1/transactions?min_id=99999999999999999999999999',
            headers=auth_header(key))
        assert response.status_code == 400

    def test_invalid_limit(self, client):
        _, _, key = make_api_user(admin=True)

        response = client.get('/api/v1/transactions?limit=abc',
                              headers=auth_header(key))
        assert response.status_code == 400

    def test_invalid_limit_on_user_transactions(self, client):
        user, _, key = make_api_user()

        response = client.get(
            f'/api/v1/users/{user.id}/transactions?limit=abc',
            headers=auth_header(key))
        assert response.status_code == 400


class TestNotifications:
    def make_notification(self, user):
        notification = models.Notification(text='Fetchez la vache!',
                                           user_id=user.id)
        models.db.session.add(notification)
        models.db.session.commit()
        return notification

    def test_mark_sent_forbidden_for_non_admin(self, client):
        user, _, key = make_api_user()
        notification = self.make_notification(user)

        response = client.post(
            f'/api/v1/notifications/{notification.id}/mark_sent',
            headers=auth_header(key))
        assert response.status_code == 403
        assert notification.is_sent is False

    def test_mark_sent(self, client):
        user, _, key = make_api_user(admin=True)
        notification = self.make_notification(user)
        assert notification.is_sent is False

        response = client.post(
            f'/api/v1/notifications/{notification.id}/mark_sent',
            headers=auth_header(key))
        assert response.status_code == 204
        assert notification.is_sent is True

    def test_mark_acknowledged_forbidden_for_non_admin(self, client):
        user, _, key = make_api_user()
        notification = self.make_notification(user)

        response = client.post(
            f'/api/v1/notifications/{notification.id}/mark_acknowledged',
            headers=auth_header(key))
        assert response.status_code == 403
        assert notification.is_acknowledged is False

    def test_mark_acknowledged(self, client):
        user, _, key = make_api_user(admin=True)
        notification = self.make_notification(user)
        assert notification.is_acknowledged is False

        response = client.post(
            f'/api/v1/notifications/{notification.id}/mark_acknowledged',
            headers=auth_header(key))
        assert response.status_code == 204
        assert notification.is_acknowledged is True

    def test_unknown_notification(self, client):
        _, _, key = make_api_user(admin=True)

        response = client.post('/api/v1/notifications/1337/mark_sent',
                               headers=auth_header(key))
        assert response.status_code == 404

        response = client.post('/api/v1/notifications/1337/mark_acknowledged',
                               headers=auth_header(key))
        assert response.status_code == 404


class TestQuotes:
    def make_quotes(self):
        quotes = []
        for text in ('Ni!', 'Ekke ekke!'):
            quote = models.Quote(text=text, who='riddare')
            models.db.session.add(quote)
            quotes.append(quote)
        models.db.session.commit()
        return quotes

    def test_get_quotes(self, client):
        _, _, key = make_api_user()
        quotes = self.make_quotes()

        response = client.get('/api/v1/quotes', headers=auth_header(key))
        assert response.status_code == 200
        assert [quote['text'] for quote in response.json] == \
            [quote.text for quote in quotes]

    def test_get_quote_by_id(self, client):
        _, _, key = make_api_user()
        quotes = self.make_quotes()

        response = client.get(f'/api/v1/quotes/{quotes[0].id}',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert response.json['text'] == quotes[0].text

    def test_get_unknown_quote(self, client):
        _, _, key = make_api_user()

        response = client.get('/api/v1/quotes/1337', headers=auth_header(key))
        assert response.status_code == 404

    def test_get_random_quote(self, client):
        _, _, key = make_api_user()
        quotes = self.make_quotes()

        response = client.get('/api/v1/quotes/random',
                              headers=auth_header(key))
        assert response.status_code == 200
        assert response.json['id'] in [quote.id for quote in quotes]


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

    def test_quotes_with_unicode_digit_min_id(self, client):
        """Superscript digits pass str.isdigit() but crash int()."""
        _, _, key = make_api_user()

        response = client.get('/api/v1/quotes?min_id=²',
                              headers=auth_header(key))
        assert response.status_code == 400

    def test_quotes_with_out_of_range_min_id(self, client):
        """Values beyond SQLite's 64-bit range crash at query execution."""
        _, _, key = make_api_user()

        response = client.get(
            '/api/v1/quotes?min_id=99999999999999999999999999',
            headers=auth_header(key))
        assert response.status_code == 400

    def test_quotes_with_invalid_limit(self, client):
        _, _, key = make_api_user()

        response = client.get('/api/v1/quotes?limit=abc',
                              headers=auth_header(key))
        assert response.status_code == 400
