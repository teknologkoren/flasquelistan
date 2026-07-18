#!/usr/bin/env python3

import datetime
from unittest import mock

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


def test_group_model(app):
    group = models.Group(
        name="Knights who say 'Ni!'",
        weight=1000
    )

    models.db.session.add(group)
    models.db.session.commit()

    assert group.id > 0


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


def test_profilepicture_model(app):
    brian = models.User(
        email='brian@pfoj.tld',
        first_name='Brian',
        last_name='Smith',
        balance=0
    )

    models.db.session.add(brian)
    models.db.session.commit()

    pic = models.ProfilePicture(
        filename='brian.gif',
        user_id=brian.id
    )

    models.db.session.add(pic)
    models.db.session.commit()

    assert pic.id > 0
    assert pic.user == brian


def test_quote_model(app):
    quote = models.Quote(
        text="Ni!",
        who="The knights who say 'Ni!'"
    )

    models.db.session.add(quote)
    models.db.session.commit()

    assert quote.id > 0


def test_registrationrequest_model(app):
    reg_req = models.RegistrationRequest(
        email='brian@pfoj.tld',
        first_name='Brian',
        last_name='Smith',
        phone='0711234567',
        message="Ni!"
    )

    models.db.session.add(reg_req)
    models.db.session.commit()

    assert reg_req.id > 0


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


def test_user_model(app):
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
        phone='074-345 32 10',
    )

    models.db.session.add(user)
    models.db.session.commit()

    assert user.id > 0

    # Valid phone numbers are automatically normalized.
    assert user.phone == '+46743453210'

    # Invalid phone numbers are allowed as well (but not normalized).
    invalid_example_number = '+4674-876 543 226 189 416 854 65'
    user.phone = invalid_example_number
    models.db.session.commit()
    assert user.phone == invalid_example_number

    # Phone number is not required.
    user.phone = ''
    models.db.session.commit()
    assert user.phone == ''


def test_usertransaction_model(app):
    user_tx = models.UserTransaction(
        value=100
    )

    models.db.session.add(user_tx)
    models.db.session.commit()

    assert user_tx.id > 0


def make_drinker(email='monty@python.tld'):
    user = models.User(
        email=email,
        first_name='Monty',
        last_name='Python',
        body_mass=70,
        y_chromosome=True,
    )
    models.db.session.add(user)
    models.db.session.commit()
    return user


def add_streque(user, standardglas=2, timestamp=None, voided=False):
    streque = models.Streque(
        value=-1000,
        text='beer',
        user_id=user.id,
        standardglas=standardglas,
        voided=voided,
    )
    if timestamp:
        streque.timestamp = timestamp

    models.db.session.add(streque)
    models.db.session.commit()
    return streque


def test_bac_emoji_buckets(app):
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
    )

    cases = [
        (0.0, None),
        (0.09, None),
        (0.1, '🍺'),
        (0.29, '🍺'),
        (0.3, '🍻'),
        (0.5, '👌'),
        (1.0, '🕺'),
        (1.5, '😟'),
        (2.0, '🤢'),
        (2.5, '😵'),
        (3.0, '💀'),
        (3.5, '🇷🇺'),
        (4.0, '🇫🇮'),
        (10.0, '🇫🇮'),
    ]

    with mock.patch.object(models.User, 'bac',
                           new_callable=mock.PropertyMock) as bac:
        for value, emoji in cases:
            bac.return_value = value
            assert user.bac_emoji == emoji


def test_bac_positive_after_recent_streque(app):
    user = make_drinker()
    add_streque(user, standardglas=2)

    assert user.bac > 0


def test_bac_zero_with_no_streques(app):
    user = make_drinker()

    assert user.bac == 0


def test_bac_decays_to_zero_for_old_streques(app):
    user = make_drinker()

    # Within the 7 day window, but the alcohol has long since been
    # burned away.
    three_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=3)
    add_streque(user, standardglas=2, timestamp=three_days_ago)

    assert user.bac == 0


def test_bac_ignores_streques_older_than_a_week(app):
    user = make_drinker()

    eight_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=8)
    add_streque(user, standardglas=100, timestamp=eight_days_ago)

    assert user.bac == 0


def test_bac_ignores_voided_streques(app):
    user = make_drinker()
    add_streque(user, standardglas=2, voided=True)

    assert user.bac == 0


def test_bac_ignores_non_alcoholic_streques(app):
    user = make_drinker()
    add_streque(user, standardglas=0)

    assert user.bac == 0


def test_poke_and_poke_back(app):
    monty = make_drinker()
    brian = make_drinker(email='brian@pfoj.tld')

    # First poke is allowed.
    poke = brian.poke(poker=monty)
    assert poke
    assert brian.get_last_poke(monty) == poke

    # Same poker poking again before a poke-back is blocked.
    assert brian.poke(poker=monty) is False

    # Poking back is allowed.
    poke_back = monty.poke(poker=brian)
    assert poke_back
    assert monty.get_last_poke(brian) == poke_back

    # And now the original poker may poke again.
    assert brian.poke(poker=monty)


def test_vcard(app):
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
        phone='074-345 32 10',
        birthday=datetime.date(1990, 5, 4),
    )
    models.db.session.add(user)
    models.db.session.commit()

    vcard = user.vcard

    assert 'Monty Python' in vcard
    assert 'monty@python.tld' in vcard
    assert '+46 74 345 32 10' in vcard
    assert '19900504' in vcard


def test_vcard_without_phone_and_birthday(app):
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
    )
    models.db.session.add(user)
    models.db.session.commit()

    vcard = user.vcard

    assert 'Monty Python' in vcard
    assert 'TEL' not in vcard
    assert 'BDAY' not in vcard
