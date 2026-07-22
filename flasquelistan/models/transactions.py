import datetime

import flask_babel
import markdown
from sqlalchemy.ext.hybrid import hybrid_method

from flasquelistan import util
from flasquelistan.models.base import db
from flasquelistan.models.social import Notification


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    weight = db.Column(db.Integer)
    name = db.Column(db.String(15), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # Ören
    description = db.Column(db.Text)
    # Swedish "units of alcohol", 12 g of alcohol
    standardglas = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def formatted_value(self):
        return flask_babel.format_currency(self.value / 100, 'SEK')

    @property
    def html_description(self):
        return markdown.markdown(self.description)

    @property
    def api_dict(self):
        data = dict()
        data['id'] = self.id
        data['weight'] = self.weight
        data['name'] = self.name
        data['value'] = self.value
        data['description'] = self.description
        data['standardglas'] = self.standardglas
        data['is_active'] = self.is_active
        return data

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        return f"Article {self.name}"


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(50))
    value = db.Column(db.Integer, nullable=False)  # Ören
    voided = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    api_key_id = db.Column(db.Integer, db.ForeignKey('api_key.id'))
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.datetime.utcnow)
    type = db.Column(db.String(50))

    user = db.relationship(
        'User',
        back_populates='transactions',
        foreign_keys=[user_id]
    )

    created_by = db.relationship(
        'User',
        foreign_keys=[created_by_id]
    )

    api_key = db.relationship(
        'ApiKey',
        foreign_keys=[api_key_id]
    )

    __mapper_args__ = {
        'polymorphic_identity': 'transaction',
        'polymorphic_on': type,
    }

    @property
    def formatted_value(self):
        return flask_babel.format_currency(self.value / 100, 'SEK')

    def void_and_refund(self):
        if self.voided:
            return False

        self.user.balance -= self.value

        self.voided = True
        db.session.commit()

        util.emit_balance_change_event(self.user, self.user.balance + self.value)

        return True

    @property
    def api_dict(self):
        data = dict()
        data['id'] = self.id
        data['text'] = self.text
        data['value'] = self.value
        data['voided'] = self.voided
        data['user_id'] = self.user_id
        data['created_by_id'] = self.created_by_id
        data['api_key_id'] = self.api_key_id
        data['timestamp'] = self.timestamp
        data['type'] = self.type
        data['formatted_value'] = self.formatted_value
        return data

    def __str__(self):
        return f"{self.__class__.__name__}: {self.value} @ {self.user}"

    def __repr__(self):
        return f"{self.__class__.__name__}: {self.value} @ {self.user_id}"


class Streque(Transaction):
    standardglas = db.Column(db.Float)

    __mapper_args__ = {
        'polymorphic_identity': 'streque',
    }

    @hybrid_method
    def too_old(self, old=15):
        """Too old to be voided by user."""
        too_old = datetime.datetime.utcnow() - datetime.timedelta(minutes=old)
        return self.timestamp < too_old

    @property
    def api_dict(self):
        data = Transaction.api_dict.fget(self)
        data['standardglas'] = self.standardglas
        return data


class AdminTransaction(Transaction):
    __mapper_args__ = {
        'polymorphic_identity': 'admin_transaction',
    }

    def create_notification(self):
        if self.value >= 0:
            with flask_babel.force_locale('sv_SE'):
                text = (
                    "Insättning!\n{money}: {message}".format(
                        money=flask_babel.format_currency(self.value / 100, 'SEK'),
                        message=self.text
                    )
                )
        elif self.value < 0:
            with flask_babel.force_locale('sv_SE'):
                text = (
                    "Uttag!\n{money}: {message}".format(
                        money=flask_babel.format_currency(self.value / 100, 'SEK'),
                        message=self.text
                    )
                )

        notification = Notification(
            text=text,
            user_id=self.user_id,
            type='admintransaction',
            reference=str(self.id)
        )
        db.session.add(notification)
        db.session.commit()
        util.emit_notification_event(notification)


class UserTransaction(Transaction):
    __mapper_args__ = {
        'polymorphic_identity': 'user_transaction'
    }


class CreditTransfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    payer_transaction_id = db.Column(
        db.Integer,
        db.ForeignKey('transaction.id')
    )
    payee_transaction_id = db.Column(
        db.Integer,
        db.ForeignKey('transaction.id')
    )

    payer_transaction = db.relationship(
        'UserTransaction',
        foreign_keys=[payer_transaction_id]
    )
    payee_transaction = db.relationship(
        'UserTransaction',
        foreign_keys=[payee_transaction_id]
    )

    @classmethod
    def create(cls, payer, payee, created_by, value, message):
        if value <= 0:
            return False

        suffix = f": {message}" if message else ""
        payer_message = f"Till {payee.full_name}{suffix}"
        payee_message = f"Från {payer.full_name}{suffix}"

        payer_tx = (
            UserTransaction(
                user_id=payer.id,
                created_by_id=created_by.id,
                value=-value,
                text=payer_message
            )
        )

        payee_tx = (
            UserTransaction(
                user_id=payee.id,
                created_by_id=created_by.id,
                value=value,
                text=payee_message
            )
        )

        payer.balance -= value
        payee.balance += value

        util.emit_balance_change_event(payer, payer.balance + value)
        util.emit_balance_change_event(payee, payee.balance - value)

        db.session.add(payer_tx)
        db.session.add(payee_tx)
        db.session.commit()

        credit_transfer = cls(
            payer_transaction_id=payer_tx.id,
            payee_transaction_id=payee_tx.id
        )

        db.session.add(credit_transfer)
        db.session.commit()

        return credit_transfer

    def void(self):
        self.payer_transaction.void_and_refund()
        self.payee_transaction.void_and_refund()

    def __str__(self):
        return f"{self.payer_transaction_id} -> {self.payee_transaction_id}"

    def __repr__(self):
        return f"CreditTransfer {self.payer_transaction_id} -> {self.payee_transaction_id}"
