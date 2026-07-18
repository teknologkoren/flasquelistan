#!/usr/bin/env python3


from flask import url_for
from flask_login import current_user

import datetime

from flasquelistan import models

from tests.helpers import logged_in
from tests.helpers import logged_in_admin


class TestIndexPage():
    def test_name_on_index_page(self, client):
        """Test that users full name shows up on index page if no nickname is present"""
        with logged_in(client):
            response = client.get(url_for('strequelistan.index'))
            text = response.get_data(as_text=True)
            assert 'Monty Python' in text

    def test_nickname_replaces_real_name(self, client):
        """Test that nicknames replace 'real' name on index page"""
        with logged_in(client):
            current_user.nickname = "Black Knight"
            models.db.session.commit()
            response = client.get(url_for('strequelistan.index'))
            text = response.get_data(as_text=True)
            assert 'Monty Python' not in text
            assert 'Black Knight' in text

    class TestGroups():
        def test_group_show_up_on_index_page(self, client):
            """Tests that a group with members shows up on the index page"""
            group = models.Group(
                name="Knights who say Ni",
                weight=1000
            )

            models.db.session.add(group)
            models.db.session.commit()

            with logged_in(client):
                current_user.group = group
                models.db.session.commit()
                response = client.get(url_for('strequelistan.index'))
                text = response.get_data(as_text=True)
                assert group.name in text

        def test_empty_group_hidden_on_index_page(self, client):
            """Tests that a group without members is hidden on the index page"""
            group = models.Group(
                name="Knights who say Ni!",
                weight=1000
            )

            models.db.session.add(group)
            models.db.session.commit()

            with logged_in(client):
                response = client.get(url_for('strequelistan.index'))
                text = response.get_data(as_text=True)
                assert group.name not in text

    class TestArticleLinks:
        def test_article_links_on_index_page(self, client):
            article1 = models.Article(
                weight=1,
                name='Holy Grail',
                value=10000,
                description="Difficult to find. Watch out for the rabbit.",
                standardglas=2,
                is_active=True
            )

            models.db.session.add(article1)
            models.db.session.commit()

            with logged_in(client):
                response = client.get(url_for('strequelistan.index'))
                text = response.get_data(as_text=True)
                assert article1.name in text

        def test_hidden_article_links_on_index_page(self, client):
            article = models.Article(
                weight=1,
                name='Holy Grail',
                value=10000,
                description="Difficult to find. Watch out for the rabbit.",
                standardglas=2,
                is_active=False
            )

            models.db.session.add(article)
            models.db.session.commit()

            with logged_in(client):
                response = client.get(url_for('strequelistan.index'))
                text = response.get_data(as_text=True)
                assert article.name not in text

    class TestQuotes():

        def test_index_no_quotes(self, client):
            """Test that the index page works without quotes"""
            with logged_in(client):
                response = client.get(url_for('strequelistan.index'))
                text = response.get_data(as_text=True)

                assert 'permalänk' not in text

        def test_quote_on_index_page(self, client):
            """Test that a quote shows up on the index page"""
            quote = models.Quote(
                text="And now for something completely different.",
                who="Newsreader [John Cleese]"
            )
            models.db.session.add(quote)
            models.db.session.commit()

            with logged_in(client):
                response = client.get(url_for('strequelistan.index'))
                text = response.get_data(as_text=True)

                # Check if the quote text is present
                assert quote.text in text

                # Check if the person who said the quote is present
                assert quote.who in text


class TestStrequa():
    """Test views related to the strequa action"""

    def test_strequa_json(self, client):
        article = models.Article(
            weight=1,
            name='Holy Grail',
            value=10000,
            description="Difficult to find. Watch out for the rabbit.",
            standardglas=2,
            is_active=True
        )

        models.db.session.add(article)
        models.db.session.commit()

        with logged_in(client):
            response = client.post(
                url_for('strequelistan.add_streque'),
                json={
                    'user_id': current_user.id,
                    'article_id': article.id
                }
            )

            assert response.json.get('user_id') == current_user.id
            assert response.json.get('value') == -article.value
            assert current_user.balance == -article.value
            assert current_user.transactions[0].text == 'Holy Grail'

    def test_strequa_form(self, client):
        article = models.Article(
            weight=1,
            name='Holy Grail',
            value=10000,
            description="Difficult to find. Watch out for the rabbit.",
            standardglas=2,
            is_active=True
        )

        models.db.session.add(article)
        models.db.session.commit()

        with logged_in(client):
            response = client.post(
                url_for('strequelistan.add_streque'),
                json={
                    'user_id': current_user.id,
                    'article_id': article.id
                }
            )

            assert response.json.get('user_id') == current_user.id
            assert response.json.get('value') == -article.value
            assert current_user.balance == -article.value
            assert current_user.transactions[0].text == 'Holy Grail'


class TestVoidStreque:
    """Test voiding streques"""

    @staticmethod
    def _make_streque(user, minutes_old=0):
        streque = models.Streque(
            value=-1000,
            text='Holy Grail',
            user_id=user.id,
            created_by_id=user.id,
        )
        models.db.session.add(streque)
        models.db.session.commit()

        if minutes_old:
            streque.timestamp = (
                datetime.datetime.utcnow()
                - datetime.timedelta(minutes=minutes_old)
            )
            models.db.session.commit()

        return streque

    def test_void_own_recent_streque(self, client):
        with logged_in(client) as user:
            user.balance = -1000
            streque = self._make_streque(user)

            response = client.post(
                url_for('strequelistan.void_streque'),
                json={'streque_id': streque.id}
            )

            assert response.status_code == 200
            assert response.json.get('streque_id') == streque.id
            assert response.json.get('balance') == 0
            assert streque.voided
            assert user.balance == 0

    def test_void_too_old_streque_rejected(self, client):
        with logged_in(client) as user:
            user.balance = -1000
            streque = self._make_streque(user, minutes_old=16)

            response = client.post(
                url_for('strequelistan.void_streque'),
                json={'streque_id': streque.id}
            )

            assert response.status_code == 400
            assert not streque.voided
            assert user.balance == -1000

    def test_void_already_voided_streque_rejected(self, client):
        with logged_in(client) as user:
            user.balance = -1000
            streque = self._make_streque(user)
            streque.void_and_refund()
            assert user.balance == 0

            response = client.post(
                url_for('strequelistan.void_streque'),
                json={'streque_id': streque.id}
            )

            assert response.status_code == 400
            assert user.balance == 0  # no double refund

    def test_void_nonexistent_streque_rejected(self, client):
        with logged_in(client):
            response = client.post(
                url_for('strequelistan.void_streque'),
                json={'streque_id': 4711}
            )

            assert response.status_code == 400

    def test_void_other_users_streque_creates_notification(self, client):
        """Voiding someone else's already-notified streque notifies them."""
        with logged_in(client) as user:
            other = models.User(
                email='brian@pfoj.tld',
                first_name='Brian',
                last_name='Smith',
                balance=-1000,
            )
            models.db.session.add(other)
            models.db.session.commit()

            streque = self._make_streque(other)
            # Simulate that the streque notification was already sent.
            notification = models.Notification(
                text='streque',
                user_id=other.id,
                type='streque',
                reference=str(streque.id),
                is_sent=True,
            )
            models.db.session.add(notification)
            models.db.session.commit()

            response = client.post(
                url_for('strequelistan.void_streque'),
                json={'streque_id': streque.id}
            )

            assert response.status_code == 200
            assert other.balance == 0

            void_notification = models.Notification.query.filter_by(
                type='streque-void', user_id=other.id).one()
            assert user.displayname in void_notification.text


class TestHistoryPage:
    """Tests for the transaction history page"""
    def test_status(self, client):
        with logged_in(client):
            response = client.get(url_for('strequelistan.history'))
            assert response.status_code == 200

    def test_transaction_show_up(self, client):
        # create article
        article = models.Article(
            weight=1,
            name='Holy Grail',
            value=10000,
            description="Difficult to find. Watch out for the rabbit.",
            standardglas=2,
            is_active=True
        )

        models.db.session.add(article)
        models.db.session.commit()

        with logged_in(client):
            current_user.strequa(article, current_user)
            response = client.get(url_for('strequelistan.history'))
            text = response.get_data(as_text=True)
            print(text)
            assert current_user.full_name in text

    def test_old_transactions_hidden(self, client):
        # create article
        article = models.Article(
            weight=1,
            name='Holy Grail',
            value=10000,
            description="Difficult to find. Watch out for the rabbit.",
            standardglas=2,
            is_active=True
        )

        models.db.session.add(article)
        models.db.session.commit()

        with logged_in(client):
            streque = current_user.strequa(article, current_user)
            streque.timestamp = streque.timestamp - datetime.timedelta(minutes=16)
            response = client.get(url_for('strequelistan.history'))
            text = response.get_data(as_text=True)
            assert current_user.full_name not in text

    def test_returned_transactions_hidden(self, client):
        # create article
        article = models.Article(
            weight=1,
            name='Holy Grail',
            value=10000,
            description="Difficult to find. Watch out for the rabbit.",
            standardglas=2,
            is_active=True
        )

        models.db.session.add(article)
        models.db.session.commit()

        with logged_in(client):
            streque = current_user.strequa(article, current_user)
            streque.void_and_refund()
            response = client.get(url_for('strequelistan.history'))
            text = response.get_data(as_text=True)
            assert current_user.full_name not in text


class TestPaperListPage:
    """Test the generaton of paper lists"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequelistan.paperlist'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequelistan.paperlist'))
            assert response.status_code == 200
            # TODO: Should mayme be limitet to admins? on the other hand,
            # there's no sensitive information / edits preformed here

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/paperlist')
            assert response.status_code == 302
            assert response.headers['Location'] == '/login?next=%2Fpaperlist'
