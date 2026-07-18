#!/usr/bin/env python3


from flask import url_for
from flask_login import current_user

from flasquelistan import models

from tests.helpers import logged_in
from tests.helpers import logged_in_admin


class TestAdminPage:
    """Tests for the 'Admin' page"""
    def test_status(self, client):
        with logged_in_admin(client):
            response = client.get(url_for('admin.index'))
            assert response.status_code == 200



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
