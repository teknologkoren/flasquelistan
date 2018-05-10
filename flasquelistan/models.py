import datetime
import random
import string
import flask_babel
import flask_login
import flask_sqlalchemy
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from flasquelistan import util

db = flask_sqlalchemy.SQLAlchemy()


class User(flask_login.UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    nickname = db.Column(db.String(50))
    phone = db.Column(db.String(20), nullable=True)
    balance = db.Column(db.Integer, default=0)  # Ören (1/100kr)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    group = db.relationship('Group')

    transactions = db.relationship("Transaction", back_populates="user")

    # Do not change the following directly, use User.password
    _password = db.Column(db.String(128))
    _password_timestamp = db.Column(db.DateTime)

    def __init__(self, *args, **kwargs):
        if 'password' not in kwargs:
            password = ''.join(random.choice(string.ascii_letters +
                                             string.digits) for _ in range(30))
            kwargs['password'] = password

        super().__init__(*args, **kwargs)

    @hybrid_property
    def password(self):
        """Return password hash."""
        return self._password

    @password.setter
    def password(self, plaintext):
        """Generate and save password hash, update password timestamp."""
        self._password = util.bcrypt.generate_password_hash(plaintext)

        # Save in UTC, password resets compare this to UTC time!
        self._password_timestamp = datetime.datetime.utcnow()

    def verify_password(self, plaintext):
        """Return True if plaintext matches password, else return False."""
        return util.bcrypt.check_password_hash(self._password, plaintext)

    @staticmethod
    def authenticate(email, password):
        """Check email and password and return user if matching.

        It might be tempting to return the user that mathes the email
        and a boolean representing if the password was correct, but
        please don't. The email alone does not identify a user, only
        the email toghether with a matching password is enough to
        identify which user we want! No matching email and password ->
        no user.
        """
        user = User.query.filter_by(email=email).first()

        if user and user.verify_password(password):
            return user

        return None

    def strequa(self, amount):
        value = Streque.get().value

        transaction = Transaction(value=value, amount=amount, user_id=self.id)
        self.balance -= transaction.sum

        db.session.add(transaction)
        db.session.commit()

        return transaction

    @property
    def formatted_balance(self):
        return flask_babel.format_currency(self.balance/100, 'SEK')

    def __str__(self):
        return "{} {} <{}>".format(self.first_name, self.last_name, self.email)


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Integer)
    users = db.relationship('User', back_populates='group')

    def __str__(self):
        return self.name


class Streque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)  # Ören

    @classmethod
    def get(cls):
        return cls.query.first()


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)  # Ören
    amount = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship("User", back_populates="transactions")
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.datetime.utcnow)

    @property
    def sum(self):
        return self.value * self.amount

    @hybrid_method
    def too_old(self, old=15):
        """Too old to be voided by user."""
        too_old = datetime.datetime.utcnow() - datetime.timedelta(minutes=old)
        return self.timestamp < too_old

    def void_and_refund(self):
        self.user.balance += self.sum
        db.session.delete(self)
        db.session.commit()
        return self.sum

    def __str__(self):
        return "{} @ {}".format(self.value, self.user)


class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(150), nullable=False)
    who = db.Column(db.String(150))
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.datetime.utcnow)

    def __str__(self):
        return "{}... — {}".format(self.text[:20], self.who[:10] or "<None>")
