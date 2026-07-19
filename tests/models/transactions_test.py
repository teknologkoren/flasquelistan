#!/usr/bin/env python3

import datetime

from flasquelistan import models

from tests.helpers import make_user


def test_admintransaction_model(app):
    admin_tx = models.AdminTransaction(
        value=100
    )

    models.db.session.add(admin_tx)
    models.db.session.commit()

    assert admin_tx.id > 0


def test_credittransfer_model(app):
    monty = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
        balance=10000
    )

    brian = models.User(
        email='brian@pfoj.tld',
        first_name='Brian',
        last_name='Smith',
        balance=0
    )

    models.db.session.add(monty)
    models.db.session.add(brian)
    models.db.session.commit()

    transfer = models.CreditTransfer.create(
        payer = monty,
        payee = brian,
        created_by = monty,
        value = 1000,
        message = "Always look on the bright side of life!"
    )

    assert monty.balance == 9000
    assert brian.balance == 1000

    assert transfer.payer_transaction.user == monty
    assert transfer.payee_transaction.user == brian

    transfer.void()

    assert monty.balance == 10000
    assert brian.balance == 0

    assert transfer.payer_transaction.voided
    assert transfer.payee_transaction.voided


def test_article_model(app):
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

    assert article.id > 0


def test_streque_model(app):
    streque = models.Streque(value=400)

    models.db.session.add(streque)
    models.db.session.commit()

    assert streque.id > 0


def test_transaction_model(app):
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
        balance=0
    )

    models.db.session.add(user)
    models.db.session.commit()

    transaction = models.Transaction(
        text='1 alcohol',
        value=-1000,
        user_id=user.id,
        created_by_id=user.id
    )

    models.db.session.add(transaction)
    models.db.session.commit()

    assert transaction.id > 0
    assert transaction.user == user
    assert transaction.created_by == user

    transaction.void_and_refund()

    assert transaction.voided
    assert user.balance == 1000


def test_usertransaction_model(app):
    user_tx = models.UserTransaction(
        value=100
    )

    models.db.session.add(user_tx)
    models.db.session.commit()

    assert user_tx.id > 0


class TestVoidAndRefund:
    def test_refunds_balance_once(self, app):
        user = make_user()

        transaction = models.Transaction(
            text='1 alcohol',
            value=-1000,
            user_id=user.id,
            created_by_id=user.id,
        )
        models.db.session.add(transaction)
        models.db.session.commit()

        assert transaction.void_and_refund() is True
        assert transaction.voided
        assert user.balance == 1000

        # Voiding again is a no-op and must not refund twice.
        assert transaction.void_and_refund() is False
        assert user.balance == 1000


class TestCreditTransfer:
    def test_create_rejects_non_positive_value(self, app):
        payer = make_user(balance=1000)
        payee = make_user(email='brian@pfoj.tld', first_name='Brian',
                          last_name='Smith')

        for value in (0, -100):
            transfer = models.CreditTransfer.create(
                payer=payer,
                payee=payee,
                created_by=payer,
                value=value,
                message=None,
            )
            assert transfer is False

        assert payer.balance == 1000
        assert payee.balance == 0
        assert models.UserTransaction.query.count() == 0
        assert models.CreditTransfer.query.count() == 0

    def test_create_moves_money_and_sets_texts(self, app):
        payer = make_user(balance=10000)
        payee = make_user(email='brian@pfoj.tld', first_name='Brian',
                          last_name='Smith')

        transfer = models.CreditTransfer.create(
            payer=payer,
            payee=payee,
            created_by=payer,
            value=1000,
            message='tack för senast',
        )

        assert payer.balance == 9000
        assert payee.balance == 1000
        # The money only moves, the total is conserved.
        assert payer.balance + payee.balance == 10000

        assert transfer.payer_transaction.value == -1000
        assert transfer.payee_transaction.value == 1000
        assert transfer.payer_transaction.text == \
            'Till Brian Smith: tack för senast'
        assert transfer.payee_transaction.text == \
            'Från Monty Python: tack för senast'

    def test_create_without_message_omits_suffix(self, app):
        payer = make_user(balance=10000)
        payee = make_user(email='brian@pfoj.tld', first_name='Brian',
                          last_name='Smith')

        transfer = models.CreditTransfer.create(
            payer=payer,
            payee=payee,
            created_by=payer,
            value=500,
            message=None,
        )

        assert transfer.payer_transaction.text == 'Till Brian Smith'
        assert transfer.payee_transaction.text == 'Från Monty Python'

    def test_void_refunds_both_sides_once(self, app):
        payer = make_user(balance=10000)
        payee = make_user(email='brian@pfoj.tld', first_name='Brian',
                          last_name='Smith')

        transfer = models.CreditTransfer.create(
            payer=payer,
            payee=payee,
            created_by=payer,
            value=1000,
            message=None,
        )

        transfer.void()
        assert payer.balance == 10000
        assert payee.balance == 0
        assert transfer.payer_transaction.voided
        assert transfer.payee_transaction.voided

        # A second void must not move any more money.
        transfer.void()
        assert payer.balance == 10000
        assert payee.balance == 0


class TestAdminTransactionNotification:
    def test_deposit_notification(self, app):
        user = make_user()
        transaction = user.admin_transaction(10000, 'påfyllning', by_user=user)
        transaction.create_notification()

        notification = models.Notification.query.filter_by(
            type='admintransaction').one()
        assert notification.user_id == user.id
        assert notification.reference == str(transaction.id)
        assert notification.text.startswith('Insättning!')
        assert 'påfyllning' in notification.text

    def test_withdrawal_notification(self, app):
        user = make_user()
        transaction = user.admin_transaction(-2500, 'straffavgift',
                                             by_user=user)
        transaction.create_notification()

        notification = models.Notification.query.filter_by(
            type='admintransaction').one()
        assert notification.text.startswith('Uttag!')
        assert 'straffavgift' in notification.text

    def test_admin_transaction_updates_balance(self, app):
        user = make_user(balance=1000)
        user.admin_transaction(-300, 'uttag', by_user=user)
        assert user.balance == 700
        user.admin_transaction(500, 'insättning', by_user=user)
        assert user.balance == 1200


class TestStreque:
    def test_too_old_boundary(self, app):
        user = make_user()
        streque = models.Streque(value=-400, user_id=user.id)
        models.db.session.add(streque)
        models.db.session.commit()

        now = datetime.datetime.utcnow()
        streque.timestamp = now - datetime.timedelta(minutes=14)
        assert not streque.too_old()

        streque.timestamp = now - datetime.timedelta(minutes=16)
        assert streque.too_old()

    def test_strequa_updates_balance_and_records_metadata(self, app):
        user = make_user()
        article = models.Article(
            weight=1,
            name='Öl',
            value=400,
            standardglas=1,
            is_active=True,
        )
        models.db.session.add(article)
        models.db.session.commit()

        streque = user.strequa(article, by_user=user)

        assert user.balance == -400
        assert streque.value == -400
        assert streque.text == 'Öl'
        assert streque.standardglas == 1
        assert streque.created_by_id == user.id
        assert streque.api_key_id is None

    def test_api_dict_includes_standardglas(self, app):
        user = make_user()
        streque = models.Streque(value=-400, user_id=user.id, standardglas=1.5)
        models.db.session.add(streque)
        models.db.session.commit()

        # formatted_value needs a request context for locale selection
        with app.test_request_context():
            data = streque.api_dict
        assert data['standardglas'] == 1.5
        assert data['value'] == -400
        assert data['type'] == 'streque'
