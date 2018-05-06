import os
import tempfile
import pytest
from flasquelistan import factory, models


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    config = {
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + db_path,
        'TESTING': True,
    }

    app = factory.create_app(config)
    with app.app_context():
        yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


def test_empty_db(client):
    """Test with blank database"""
    rv = client.get('/')
    assert b'Strequelistan' in rv.data

    rv = client.get('/citat')
    assert b'No quotes yet!' in rv.data


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


def test_index_page(app, client):
    import json

    monty = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
        phone='0700011223',
        balance=10000,
    )

    rick = models.User(
        email='rick_astley@domain.tld',
        first_name='Rick',
        nickname='Roll',
        last_name='Astley',
        phone='0703322110',
    )

    streque = models.Streque(value=400)

    models.db.session.add_all([monty, rick, streque])
    models.db.session.commit()

    rv = client.get('/')
    assert b'Monty' in rv.data
    assert b'Roll' in rv.data

    rv = client.post('/strequa',
                     data=json.dumps(dict(user_id=monty.id, amount=4)),
                     content_type='application/json')

    data = json.loads(rv.data)
    assert data['user_id'] == monty.id
    assert data['amount'] == 4
    assert data['balance'] == 8400
    assert monty.balance == 8400

    rv = client.post('/strequa',
                     data=json.dumps(dict(user_id=rick.id, amount=1)),
                     content_type='application/json')

    data = json.loads(rv.data)
    assert data['user_id'] == rick.id
    assert data['amount'] == 1
    assert data['balance'] == -400
    assert rick.balance == -400


def test_strequa(app):
    import datetime

    streque = models.Streque(value=400)
    user = models.User(email='monty@python.tld', balance=10000)
    models.db.session.add(streque)
    models.db.session.add(user)
    models.db.session.commit()

    time_before = datetime.datetime.utcnow()
    transaction = user.strequa(3)
    time_after = datetime.datetime.utcnow()

    assert transaction.amount == 3
    assert transaction.value == 400
    assert transaction.user == user
    assert time_after > transaction.timestamp > time_before

    assert user.balance == 8800
    assert user.transactions[0] == transaction


def test_void(app):
    streque = models.Streque(value=400)
    user = models.User(email='monty@python.tld', balance=10000)
    models.db.session.add_all([streque, user])
    models.db.session.commit()

    transaction = user.strequa(4)

    assert user.balance == 8400

    transaction.void_and_refund()

    assert user.balance == 10000
    assert len(models.Transaction.query.all()) == 0
