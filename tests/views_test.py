#!/usr/bin/env python3


import pytest
from flask import url_for
from flask_login import current_user
from jinja2.exceptions import TemplateNotFound

import datetime

from flasquelistan import models

from tests.helpers import logged_in
from tests.helpers import logged_in_admin
from tests.helpers import login


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

        def test_status(self, client):
            with logged_in(client):
                response = client.get(url_for('quotes.index'))
                assert response.status_code == 200

        def test_empty_quotes(self, client):
            """Test with blank database"""
            with logged_in(client):
                response = client.get(url_for('quotes.index'))
                text = response.get_data(as_text=True)

                assert 'No quotes yet!' in text

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


class TestProfilePage:
    """Tests for the profile page"""
    def test_status(self, client):
        with logged_in(client):
            response = client.get(url_for('profile.show_profile', user_id=1))
            assert response.status_code == 200

    def test_edit_profile_link_correct_user(self, client):

        with logged_in(client):
            response = client.get(url_for('profile.show_profile', user_id=1))
            text = response.get_data(as_text=True)

            assert "Redigera profil" in text

    def test_edit_profile_link_admin(self, client):

        user = models.User(
                email='monty@python2.tld',
                first_name='Osquar',
                last_name='Teknolog'
        )

        models.db.session.add(user)
        models.db.session.commit()


        with logged_in_admin(client):

            response = client.get(url_for('profile.show_profile', user_id=user.id))
            text = response.get_data(as_text=True)

            assert "Redigera profil" in text

    def test_edit_profile_link_hidden(self, client):

        user = models.User(
                email='monty@python2.tld',
                first_name='Osquar',
                last_name='Teknolog'
        )

        models.db.session.add(user)
        models.db.session.commit()

        with logged_in(client):
            response = client.get(url_for('profile.show_profile', user_id=user.id))
            text = response.get_data(as_text=True)

            assert "Redigera profil" not in text

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


class TestAdminPage:
    """Tests for the 'Admin' page"""
    def test_status(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('admin.index'))
            assert response.status_code == 200


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


class TestCreateUserPage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.add_user'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.add_user'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/add-user/')
            assert response.status_code == 302

    def test_create_user(self, client):

        with logged_in_admin(client):
            data = {
                "first_name": "Monty",
                "last_name": "Python",
                "email": "monty@python.example.org",
                "phone": "+46761234567",
            }

            response = client.post(
                    url_for('strequeadmin.add_user'),
                    data=data,
                    follow_redirects = True
            )


            text = response.get_data(as_text=True)
            assert "Monty Python <monty@python.example.org> skapad!" in text


class TestCreateUserFromRequestPage:
    """description"""

    def test_status_admin(self, client):
        r = models.RegistrationRequest(
            email="monty@python.example.org",
            first_name="Monty",
            last_name="Python",
            phone="+46761234567",
            message="Hejsan!"
        )
        models.db.session.add(r)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.post(url_for('strequeadmin.add_user', request_id=1))
            text = response.get_data(as_text=True)

            assert "monty@python.example.org" in text
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        r = models.RegistrationRequest(
            email="monty@python.example.org",
            first_name="Monty",
            last_name="Python",
            phone="+46761234567",
            message="Hejsan!"
        )
        models.db.session.add(r)
        models.db.session.commit()

        with logged_in(client):
            response = client.get(url_for('strequeadmin.add_user', request_id=1))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        r = models.RegistrationRequest(
            email="monty@python.example.org",
            first_name="Monty",
            last_name="Python",
            phone="+46761234567",
            message="Hejsan!"
        )
        models.db.session.add(r)
        models.db.session.commit()

        with client:
            response = client.get('http://localhost/admin/add-user/request/1')
            assert response.status_code == 302


class TestAccountRequestPage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.requests'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.requests'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/requests/')
            assert response.status_code == 302


class TestRemoveAccountRequestPage:
    """description"""
    def test_status_admin(self, client):
        r = models.RegistrationRequest(
            email="monty@python.example.org",
            first_name="Monty",
            last_name="Python",
            phone="+46761234567",
            message="Hejsan!"
        )
        models.db.session.add(r)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.post(
                    url_for('strequeadmin.remove_request', request_id=1),
                    follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert "Förfrågan från Monty Python borttagen." in text
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.post(
                    url_for('strequeadmin.remove_request', request_id=1),
            )
            assert response.headers['Location'] == '/'
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.post('http://localhost/admin/requests/remove/1')
            assert response.status_code == 302


class TestListUserPage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.show_users'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.show_users'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/users')
            assert response.status_code == 302


class TestGroupsPage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.show_groups'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.show_groups'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/groups')
            assert response.status_code == 302

class TestRemoveGroupPage:
    """description"""
    def test_status_admin(self, client):
        group = models.Group(
            name="Knights of the round table",
        )
        models.db.session.add(group)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.post(
                    url_for('strequeadmin.remove_group', group_id=1),
                    follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert "Grupp \"Knights of the round table\" borttagen" in text
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.post(
                    url_for('strequeadmin.remove_group', group_id=1),
            )
            assert response.headers['Location'] == '/'
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.post('http://localhost/admin/groups/remove/1')
            assert response.status_code == 302



class TestBalanceReminderPage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.spam'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.spam'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/spam')
            assert response.status_code == 302

    def test_correct_users(self, client):
        user = models.User(
                email='monty@python2.tld',
                first_name='Malvina',
                last_name='Teknolog'
        )

        user.balance = -1000

        models.db.session.add(user)
        models.db.session.commit()

        user = models.User(
                email='monty@python3.tld',
                first_name='Osquar',
                last_name='Teknolog'
        )

        user.balance = 1000

        models.db.session.add(user)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.spam'))
            text = response.get_data(as_text=True)
            assert "Malvina Teknolog" in text
            assert "Osquar Teknolog" not in text


class TestAdminTransactionHistoryPage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.transactions'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.transactions'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/transactions/')
            assert response.status_code == 302

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

        with logged_in_admin(client):
            current_user.strequa(article, current_user)
            response = client.get(url_for('strequeadmin.transactions'))
            text = response.get_data(as_text=True)
            print(text)
            assert current_user.full_name in text


class TestBulkTransactionPage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.bulk_transactions'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.bulk_transactions'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/transactions/bulk')
            assert response.status_code == 302


class TestConfirmBulkTransactionPage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.post(url_for('strequeadmin.confirm_bulk_transactions'), follow_redirects=True)
            text = response.get_data(as_text=True)
            assert "Transaktionerna utfördes!" in text
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.post(url_for('strequeadmin.confirm_bulk_transactions'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.post('http://localhost/admin/transactions/bulk/confirm')
            assert response.status_code == 302



class TestadminQuotePage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.show_quotes'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.show_quotes'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/quotes/')
            assert response.status_code == 302

class TestEditQuotePage:
    """description"""
    def test_status_admin(self, client):
        quote = models.Quote(
            text="And now for something completely different.",
            who="Newsreader [John Cleese]"
        )
        models.db.session.add(quote)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.edit_quote', quote_id=1))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.edit_quote', quote_id=1))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/quotes/edit/1')
            assert response.status_code == 302


class TestRemoveQuotePage:
    """description"""
    def test_status_admin(self, client):
        quote = models.Quote(
            text="And now for something completely different.",
            who="Newsreader [John Cleese]"
        )
        models.db.session.add(quote)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.post(
                    url_for('strequeadmin.remove_quote', quote_id=1),
                    follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert "Citat borttaget" in text
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.post(
                    url_for('strequeadmin.remove_quote', quote_id=1),
                    #follow_redirects=True
            )
            assert response.headers['Location'] == '/'
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.post('http://localhost/admin/quotes/remove/1')
            assert response.status_code == 302


class TestArticlePage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.articles'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.articles'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/articles/')
            assert response.status_code == 302


class TestEditArticlePage:
    """description"""

    def test_status_admin(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.edit_article'))
            assert response.status_code == 200

    def test_status_regular_user(self, client):
        with logged_in(client):
            response = client.get(url_for('strequeadmin.edit_article'))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
        with client:
            response = client.get('http://localhost/admin/articles/new')
            assert response.status_code == 302


class TestRemoveArticlePage:
    """description"""

    def test_status_admin(self, client):
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
        with logged_in_admin(client):
            response = client.post(
                    url_for(
                        'strequeadmin.remove_article',
                        article_id=1
                    ),
                    follow_redirects=True
            )
            text = response.get_data(as_text=True)
            assert 'Produkt "Holy Grail" borttagen' in text
            assert response.status_code == 200

    def test_status_regular_user(self, client):
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
            response = client.post(url_for('strequeadmin.remove_article', article_id=1))
            assert response.status_code == 302

    def test_not_logged_in(self, client):
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

        with client:
            response = client.post('http://localhost/admin/articles/remove/1')
            assert response.status_code == 302


class TestProfilePages:
    def test_profile_pages_render(self, client):
        """Smoke test that the profile-owned pages render for the user."""
        with logged_in(client) as user:
            for url in (
                f'/profile/{user.id}/edit/',
                f'/profile/{user.id}/nicknames',
                f'/profile/{user.id}/history',
                f'/profile/{user.id}/api-keys',
                f'/profile/{user.id}/api-keys/new',
                f'/profile/{user.id}/edit/password',
            ):
                response = client.get(url)
                assert response.status_code == 200, url

            response = client.get(f'/profile/{user.id}/vcard')
            assert response.status_code == 200
            assert response.mimetype == 'text/vcard'

    def test_profile_requires_login(self, client):
        """Anonymous users are redirected to the login page."""
        response = client.get('/profile/1/')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']


class TestAdminBulkTransactions:
    """Test the two-step admin bulk transaction flow"""

    def test_bulk_transactions_form_shows_confirmation(self, client):
        user = models.User(
            email='brian@pfoj.tld',
            first_name='Brian',
            last_name='Cohen',
        )
        models.db.session.add(user)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.bulk_transactions'),
                data={
                    f'user-{user.id}-value': '12.50',
                    f'user-{user.id}-text': 'Sångarstriden',
                }
            )
            text = response.get_data(as_text=True)

            # The confirmation page lists the pending transaction...
            assert response.status_code == 200
            assert 'vill du fortsätta?' in text
            assert user.full_name in text
            assert f'name="user-{user.id}-value" value="1250"' in text

            # ...but nothing has happened yet.
            assert user.balance == 0

    def test_confirm_bulk_transactions_updates_balance(self, client):
        user = models.User(
            email='brian@pfoj.tld',
            first_name='Brian',
            last_name='Cohen',
        )
        models.db.session.add(user)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.confirm_bulk_transactions'),
                data={
                    f'user-{user.id}-value': '1250',
                    f'user-{user.id}-text': 'Sångarstriden',
                },
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Transaktionerna utfördes!' in text
            assert user.balance == 1250

            transaction = models.AdminTransaction.query.one()
            assert transaction.user_id == user.id
            assert transaction.value == 1250
            assert transaction.text == 'Sångarstriden'

            notification = models.Notification.query.filter_by(
                user_id=user.id, type='admintransaction').one()
            assert 'Insättning' in notification.text

    def test_bulk_transactions_without_values_does_nothing(self, client):
        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.bulk_transactions'),
                data={},
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert 'Inga transaktioner utförda' in text
            assert models.AdminTransaction.query.count() == 0


class TestVoidTransaction:
    """Test the admin void transaction view"""

    def test_admin_void_transaction_refunds(self, client):
        with logged_in_admin(client) as admin:
            user = models.User(
                email='brian@pfoj.tld',
                first_name='Brian',
                last_name='Cohen',
            )
            models.db.session.add(user)
            models.db.session.commit()

            transaction = user.admin_transaction(-1000, 'Uttag', admin)
            assert user.balance == -1000

            response = client.post(
                url_for('strequeadmin.void_transaction'),
                json={'transaction_id': transaction.id}
            )

            assert response.status_code == 200
            assert response.json.get('transaction_id') == transaction.id
            assert response.json.get('balance') == 0
            assert transaction.voided
            assert user.balance == 0

    def test_void_already_voided_transaction_rejected(self, client):
        with logged_in_admin(client) as admin:
            transaction = admin.admin_transaction(-1000, 'Uttag', admin)
            transaction.void_and_refund()

            response = client.post(
                url_for('strequeadmin.void_transaction'),
                json={'transaction_id': transaction.id}
            )

            assert response.status_code == 400
            assert admin.balance == 0  # no double refund

    def test_void_nonexistent_transaction_rejected(self, client):
        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.void_transaction'),
                json={'transaction_id': 4711}
            )
            assert response.status_code == 400

    def test_non_admin_cannot_void_transaction(self, client):
        with logged_in(client) as user:
            transaction = user.admin_transaction(-1000, 'Uttag', user)

            response = client.post(
                url_for('strequeadmin.void_transaction'),
                json={'transaction_id': transaction.id}
            )

            # admin_required returns 403 for JSON (AJAX) requests.
            assert response.status_code == 403
            assert not transaction.voided
            assert user.balance == -1000


class TestArticleCrud:
    """Test creating and editing articles"""

    def test_add_article(self, client):
        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.edit_article'),
                data={
                    'name': 'Holy Grail',
                    'value': '8.50',
                    'standardglas': '2',
                    'weight': '1',
                    'is_active': 'y',
                },
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Produkt "Holy Grail" skapad.' in text

            article = models.Article.query.one()
            assert article.name == 'Holy Grail'
            assert article.value == 850  # stored in ören
            assert article.is_active

    def test_edit_article(self, client):
        article = models.Article(
            weight=1,
            name='Holy Grail',
            value=10000,
            standardglas=2,
            is_active=True
        )
        models.db.session.add(article)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.edit_article', article_id=article.id),
                data={
                    'name': 'Unholy Grail',
                    'value': '50',
                    'standardglas': '1',
                    'weight': '2',
                },
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Produkt "Unholy Grail" ändrad.' in text
            assert article.name == 'Unholy Grail'
            assert article.value == 5000
            assert article.weight == 2
            assert article.is_active is False

    def test_add_article_invalid_value_rejected(self, client):
        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.edit_article'),
                data={
                    'name': 'Huge Grail',
                    'value': '9001',  # over the max of 1000
                    'standardglas': '1',
                    'weight': '1',
                }
            )

            assert response.status_code == 200
            assert models.Article.query.count() == 0


class TestGroupCrud:
    """Test creating and editing groups"""

    def test_add_group(self, client):
        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.edit_group'),
                data={'name': 'Knights who say Ni', 'weight': '10'},
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Grupp "Knights who say Ni" skapad.' in text

            group = models.Group.query.one()
            assert group.name == 'Knights who say Ni'
            assert group.weight == 10
            assert group.active is False

    def test_edit_group(self, client):
        group = models.Group(name='Knights who say Ni', weight=10)
        models.db.session.add(group)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.edit_group', group_id=group.id),
                data={
                    'name': 'Knights who say Ekke Ekke',
                    'weight': '20',
                    'active': 'y',
                },
                follow_redirects=True
            )

            assert response.status_code == 200
            assert group.name == 'Knights who say Ekke Ekke'
            assert group.weight == 20
            assert group.active is True

    def test_add_group_requires_name(self, client):
        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.edit_group'),
                data={'name': '', 'weight': '10'}
            )

            assert response.status_code == 200
            assert models.Group.query.count() == 0


class TestCreateUserFromRequestPost:
    """Test creating a user from a registration request"""

    def test_create_user_removes_request(self, client):
        r = models.RegistrationRequest(
            email="monty@python.example.org",
            first_name="Monty",
            last_name="Python",
            phone="+46761234567",
            message="Hejsan!"
        )
        models.db.session.add(r)
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.add_user', request_id=r.id),
                data={
                    'first_name': 'Monty',
                    'last_name': 'Python',
                    'email': 'monty@python.example.org',
                    'phone': '+46761234567',
                    'group_id': '-1',
                    'active': 'y',
                },
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'skapad och förfrågan borttagen!' in text

            user = models.User.query.filter_by(
                email='monty@python.example.org').one()
            assert user.first_name == 'Monty'
            assert user.active is True
            assert models.RegistrationRequest.query.count() == 0


class TestBalanceReminderEmails:
    """Test sending balance reminder emails"""

    def test_emails_sent_only_to_negative_balance_users(self, client,
                                                        monkeypatch):
        sent = []
        monkeypatch.setattr(
            'flasquelistan.util.send_email',
            lambda fromaddr, toaddr, subject, body:
                sent.append(toaddr)
        )

        negative = models.User(
            email='negative@python.tld',
            first_name='Malvina',
            last_name='Teknolog',
            balance=-1000,
        )
        positive = models.User(
            email='positive@python.tld',
            first_name='Osquar',
            last_name='Teknolog',
            balance=1000,
        )
        models.db.session.add_all([negative, positive])
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.post(url_for('strequeadmin.spam'))
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Skickade 1 saldopåminnelser!' in text
            assert sent == ['negative@python.tld']


class TestStatsPages:
    """Test the admin statistics pages"""

    def test_streque_stats_with_date_range(self, client):
        article = models.Article(
            weight=1,
            name='Holy Grail',
            value=10000,
            standardglas=2,
            is_active=True
        )
        models.db.session.add(article)
        models.db.session.commit()

        with logged_in_admin(client):
            current_user.strequa(article, current_user)

            today = datetime.date.today()
            yesterday = today - datetime.timedelta(days=1)
            response = client.get(
                url_for('strequeadmin.streque_stats',
                        from_date=yesterday.isoformat(),
                        to_date=today.isoformat())
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert current_user.full_name in text

    def test_streque_stats_invalid_dates(self, client):
        with logged_in_admin(client):
            response = client.get(
                url_for('strequeadmin.streque_stats',
                        from_date='banana',
                        to_date='2020-01-01')
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Ogiltigt datumintervall!' in text

    def test_streque_stats_form_redirects_with_dates(self, client):
        with logged_in_admin(client):
            response = client.post(
                url_for('strequeadmin.streque_stats'),
                data={'start': '2020-01-01', 'end': '2020-01-31'}
            )

            assert response.status_code == 302
            assert 'from_date=2020-01-01' in response.headers['Location']
            assert 'to_date=2020-01-31' in response.headers['Location']

    def test_transactions_invalid_dates(self, client):
        with logged_in_admin(client):
            response = client.get(
                url_for('strequeadmin.transactions',
                        from_date='not-a-date',
                        to_date='also-not-a-date')
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Ogiltigt datumintervall!' in text

    def test_stats_page(self, client):
        negative = models.User(
            email='negative@python.tld',
            first_name='Malvina',
            last_name='Teknolog',
            balance=-1000,
        )
        positive = models.User(
            email='positive@python.tld',
            first_name='Osquar',
            last_name='Teknolog',
            balance=1000,
        )
        models.db.session.add_all([negative, positive])
        models.db.session.commit()

        with logged_in_admin(client):
            response = client.get(url_for('strequeadmin.stats'))
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Malvina Teknolog' in text
            assert 'Osquar Teknolog' in text


class TestStrequelistanPages:
    """Test miscellaneous strequelistan pages"""

    def test_payments_page(self, client):
        # BUG: the strequelistan.payments view renders 'payments.html', but
        # no such template exists, so the page crashes with a server error
        # for every user. This test documents the current (broken) behavior.
        with logged_in(client):
            with pytest.raises(TemplateNotFound):
                client.get(url_for('strequelistan.payments'))

    def test_paperlist_active_filter(self, client):
        # The paper list only shows users that belong to a group.
        group = models.Group(name='Knights who say Ni', weight=10)
        models.db.session.add(group)
        models.db.session.commit()

        inactive = models.User(
            email='inactive@python.tld',
            first_name='Inactive',
            last_name='Member',
            active=False,
            group_id=group.id,
        )
        models.db.session.add(inactive)
        models.db.session.commit()

        with logged_in_admin(client) as admin:
            admin.active = True
            admin.group_id = group.id
            models.db.session.commit()

            response = client.get(
                url_for('strequelistan.paperlist', active='true')
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert admin.full_name in text
            assert inactive.full_name not in text

            # Without the filter, both users are listed.
            response = client.get(url_for('strequelistan.paperlist'))
            text = response.get_data(as_text=True)
            assert admin.full_name in text
            assert inactive.full_name in text

    def test_paperlist_empty_rows(self, client):
        with logged_in(client):
            response = client.get(
                url_for('strequelistan.paperlist', empty='3')
            )
            assert response.status_code == 200

    def test_paperlist_invalid_empty_param(self, client):
        with logged_in(client):
            response = client.get(
                url_for('strequelistan.paperlist', empty='bogus')
            )
            assert response.status_code == 200

    def test_history_ignores_date_args(self, client):
        with logged_in(client):
            response = client.get(
                url_for('strequelistan.history',
                        from_date='2020-01-01',
                        to_date='banana')
            )
            assert response.status_code == 200


class TestQuoteViews:
    """Test adding and viewing quotes"""

    def test_add_quote(self, client):
        with logged_in(client):
            response = client.post(
                url_for('quotes.add_quote'),
                data={
                    'text': 'He is not the Messiah!',
                    'who': 'Brians mother',
                },
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Citat tillagt!' in text

            quote = models.Quote.query.one()
            assert quote.text == 'He is not the Messiah!'
            assert quote.who == 'Brians mother'

    def test_add_quote_requires_text(self, client):
        with logged_in(client):
            response = client.post(
                url_for('quotes.add_quote'),
                data={'text': '', 'who': 'Nobody'}
            )

            assert response.status_code == 200
            assert models.Quote.query.count() == 0

    def test_single_quote_page(self, client):
        quote = models.Quote(
            text="And now for something completely different.",
            who="Newsreader [John Cleese]"
        )
        models.db.session.add(quote)
        models.db.session.commit()

        with logged_in(client):
            response = client.get(url_for('quotes.quote', quote_id=quote.id))
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert quote.text in text

    def test_unknown_quote_404(self, client):
        with logged_in(client):
            response = client.get(url_for('quotes.quote', quote_id=4711))
            assert response.status_code == 404
