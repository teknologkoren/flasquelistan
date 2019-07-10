from contextlib import contextmanager

import pytest
from flask import url_for
from flask_login import current_user

from flasquelistan import factory, models


@pytest.fixture
def app():
    config = {
        # Use an in-memory database for faster test execution.
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        # Disable CSRF in unit tests.
        'WTF_CSRF_ENABLED': False,
        'TESTING': True,
    }

    app = factory.create_app(config)
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


@contextmanager
def logged_in(client):
    """Fixture for a signed in user"""
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
    )

    models.db.session.add(user)
    models.db.session.commit()

    user.password = 'solidsnake'
    models.db.session.commit()

    with client:
        rv = login(client, 'monty@python.tld', 'solidsnake')
        assert rv.status_code == 302
        yield user


def login(client, email, password):
    return client.post('/login', data=dict(
         email=email, password=password
    ))


def logout(client):
    return client.get('/logout', follow_redirects=True)


def test_must_login_redirect(client):
    """Tests that users get redirected to the login page"""
    rv = client.get('/')

    assert rv.status_code == 302
    assert rv.headers['Location'] == 'http://localhost/login?next=%2F'


def test_successful_login(app):
    user = models.User(
            email='monty@python.tld',
            first_name='Monty',
            last_name='Python',
    )

    models.db.session.add(user)
    models.db.session.commit()

    user.password = 'solidsnake'
    models.db.session.commit()

    with app.test_client() as client:
        rv = login(client, 'monty@python.tld', 'solidsnake')
        assert rv.status_code == 302
        assert rv.headers['Location'] == 'http://localhost/'


def test_empty_quotes(client):
    """Test with blank database"""
    with logged_in(client):
        response = client.get(url_for('quotes.index'))
        text = response.get_data(as_text=True)

        assert 'No quotes yet!' in text


def test_single_user_no_quotes(client):
    with logged_in(client):
        response = client.get(url_for('strequelistan.index'))
        text = response.get_data(as_text=True)

        assert 'Monty Python' in text
        assert 'permalänk' not in text


def test_strequa_json(client):
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


def test_strequa_form(client):
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
def test_user_model(app):
    user = models.User(
            email='monty@python.tld',
            first_name='Monty',
            last_name='Python',
            phone='0700011223',
    )

    models.db.session.add(user)
    models.db.session.commit()

    assert user.id > 0


def test_streque_model(app):
    streque = models.Streque(value=400)

    models.db.session.add(streque)
    models.db.session.commit()

    assert streque.id > 0


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


def test_admintransaction_model(app):
    admin_tx = models.AdminTransaction(
        value=100
    )

    models.db.session.add(admin_tx)
    models.db.session.commit()

    assert admin_tx.id > 0


def test_usertransaction_model(app):
    user_tx = models.UserTransaction(
        value=100
    )

    models.db.session.add(user_tx)
    models.db.session.commit()

    assert user_tx.id > 0


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
        monty,
        brian,
        1000,
        "Always look on the bright side of life!"
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


def test_quote_model(app):
    quote = models.Quote(
        text="Ni!",
        who="The knights who say 'Ni!'"
    )

    models.db.session.add(quote)
    models.db.session.commit()

    assert quote.id > 0


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
