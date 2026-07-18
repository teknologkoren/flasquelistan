#!/usr/bin/env python3


from flask import url_for
from flask_login import current_user

import datetime

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
