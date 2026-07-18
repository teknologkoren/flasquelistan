#!/usr/bin/env python3

from flasquelistan import models


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
