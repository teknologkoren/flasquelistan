"""Transfer objects from an accidentally deleted account to a new one"""
import sys

import sqlite3

OLD_USER_ID, NEW_USER_ID = sys.argv[1], sys.argv[2]

conn = sqlite3.connect('db.sqlite')
conn.row_factory = sqlite3.Row
c = conn.cursor()


def transfer():
    c.execute(
        'UPDATE "transaction" SET user_id=? WHERE user_id IS NULL',
        (NEW_USER_ID,)
    )

    c.execute(
        'UPDATE "transaction" SET created_by_id=? WHERE created_by_id=?',
        (NEW_USER_ID, OLD_USER_ID)
    )

    c.execute(
        'UPDATE profile_picture SET user_id=? WHERE user_id IS NULL',
        (NEW_USER_ID,)
    )

    conn.commit()

    c.execute(
        'SELECT * FROM "transaction" WHERE user_id=?',
        (NEW_USER_ID,)
    )
    transactions = c.fetchall()

    total_balance = 0
    for transaction in transactions:
        total_balance += transaction[2]

    c.execute(
        'UPDATE user SET balance=? WHERE id=?',
        (total_balance, NEW_USER_ID)
    )

    conn.commit()


if __name__ == "__main__":
    transfer()
