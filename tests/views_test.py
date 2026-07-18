#!/usr/bin/env python3


from flask import url_for
from flask_login import current_user

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
