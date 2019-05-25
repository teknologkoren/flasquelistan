import datetime
import sqlite3

import app
from flasquelistan import models

conn = sqlite3.connect('db.sqlite3')
conn.row_factory = sqlite3.Row
c = conn.cursor()


def get_table(table):
    query = 'SELECT * FROM {}'.format(table)
    c.execute(query)

    return c.fetchall()


def insert_users():
    streque_users = get_table('EmailUser_myuser')
    amountofusers = len(streque_users)

    for i, user in enumerate(streque_users, start=1):
        print("({}/{}) {} {} <{}>"
              .format(
                  i,
                  amountofusers,
                  user['first_name'],
                  user['last_name'],
                  user['email'])
              )

        fuser = models.User(
            id=user['id'],
            email=user['email'],
            first_name=user['first_name'],
            last_name=user['last_name'],
            nickname=user['nickname'],
            phone=user['phone_number'],
            balance=user['balance']*100,
            is_admin=user['is_admin'],
            active=user['is_active'],
            group_id=user['group_id'],
            body_mass=user['weight'],
            y_chromosome=user['y_chromosome'],
        )

        if user['avatar']:
            filename = user['avatar'][18:]

            pic = models.ProfilePicture(
                filename=filename,
                user_id=user['id'],
            )

            fuser.profile_picture = pic
            models.db.session.add(pic)

        models.db.session.add(fuser)

    models.db.session.commit()


def insert_groups():
    groups = get_table('strecklista_group')

    for group in groups:
        print(group['name'])

        fgroup = models.Group(
            id=group['id'],
            name=group['name'],
            weight=group['sortingWeight'],
        )

        models.db.session.add(fgroup)

    models.db.session.commit()


def insert_articles():
    products = get_table('strecklista_pricegroup')

    for product in products:
        print(product['name'])

        article = models.Article(
            name=product['name'],
            weight=product['sortingWeight'],
            value=product['defaultPrice']*100,
            standardglas=1,
        )

        models.db.session.add(article)

    models.db.session.commit()


def insert_transactions():
    transactions = get_table('strecklista_transaction')
    amountoftransactions = len(transactions)

    for i, transaction in enumerate(transactions, start=1):
        print("({}/{}) {}".format(i,
                                  amountoftransactions,
                                  transaction['message']))

        if transaction['admintransaction']:
            ftx = models.AdminTransaction(
                id=transaction['id'],
                text=transaction['message'],
                value=transaction['amount']*100,
                voided=transaction['returned'],
                user_id=transaction['user_id'],
                timestamp=datetime.datetime.fromisoformat(
                    transaction['timestamp']
                ),
            )
        else:
            ftx = models.Streque(
                id=transaction['id'],
                text=transaction['message'],
                value=-transaction['amount']*100,
                voided=transaction['returned'],
                user_id=transaction['user_id'],
                timestamp=datetime.datetime.fromisoformat(
                    transaction['timestamp']
                ),
                standardglas=1,
            )

        models.db.session.add(ftx)

    models.db.session.commit()


def insert_quotes():
    quotes = get_table('strecklista_quote')
    amountofquotes = len(quotes)

    for i, quote in enumerate(quotes, start=1):
        print("({}/{}) {}".format(i, amountofquotes, quote['text']))

        timestamp = datetime.datetime.fromisoformat(quote['timestamp'])

        fquote = models.Quote(
            text=quote['text'],
            who=quote['who'],
            timestamp=timestamp,
        )

        models.db.session.add(fquote)

    models.db.session.commit()


if __name__ == "__main__":
    with app.app.app_context():
        insert_users()
        insert_groups()
        insert_articles()
        insert_transactions()
        insert_quotes()
