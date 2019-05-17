import datetime
import os
import random
import string
import flask_babel
import flask_login
import flask_sqlalchemy
import markdown
import phonenumbers
import vobject
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
    active = db.Column(db.Boolean, nullable=False, default=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    body_mass = db.Column(db.Integer, nullable=True)
    y_chromosome = db.Column(db.Boolean, nullable=True)
    api_secret = db.Column(db.String(50), default=os.urandom(16).hex)

    # use_alter=True adds fk after ProfilePicture has been created to avoid
    # circular dependency
    profile_picture_id = db.Column(db.Integer,
                                   db.ForeignKey('profile_picture.id',
                                                 use_alter=True))

    group = db.relationship('Group')
    transactions = db.relationship('Transaction',
                                   back_populates='user',
                                   lazy='dynamic')
    profile_picture = db.relationship('ProfilePicture',
                                      foreign_keys=profile_picture_id)

    # Do not change the following directly, use User.password
    _password = db.Column(db.String(128))
    _password_timestamp = db.Column(db.DateTime)

    @property
    def json(self):
        data = {}
        data['id'] = self.id
        data['email'] = self.email
        data['first_name'] = self.first_name
        data['last_name'] = self.last_name
        data['full_name'] = self.full_name
        data['nickname'] = self.nickname
        data['phone'] = self.phone
        data['formatted_phone'] = self.formatted_phone()
        data['balance'] = self.balance
        data['formatted_balance'] = self.formatted_balance
        data['is_admin'] = self.is_admin
        data['active'] = self.active
        data['group'] = self.group_id
        data['body_mass'] = self.body_mass
        data['y_chromosome'] = self.y_chromosome
        data['api_secret'] = self.api_secret
        data['profile_picture'] = self.profile_picture_id
        data['bac'] = self.bac
        return data

    def __init__(self, *args, **kwargs):
        if 'password' not in kwargs:
            password = ''.join(random.choice(string.ascii_letters +
                                             string.digits) for _ in range(30))
            kwargs['password'] = password

        super().__init__(*args, **kwargs)

    @property
    def vcard(self):
        j = vobject.vCard()
        j.add('n')
        j.n.value = vobject.vcard.Name(family=self.last_name,
                                       given=self.first_name)
        j.add('fn')
        j.fn.value = self.full_name
        j.add('email')
        j.email.value = self.email
        j.email.type_param = 'INTERNET'
        if self.phone:
            j.add('tel')
            j.tel.type_param = 'cell'
            j.tel.value = self.formatted_phone()
        return j.serialize()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def formatted_balance(self):
        return flask_babel.format_currency(self.balance/100, 'SEK')

    def formatted_phone(self, e164=False):
        """Returns formatted number or False if not a valid number."""
        try:
            # If no country code, assume Swedish
            parsed = phonenumbers.parse(self.phone, 'SE')
        except phonenumbers.phonenumberutil.NumberParseException:
            return False

        if not (phonenumbers.is_possible_number(parsed) and
                phonenumbers.is_valid_number(parsed)):
            return False

        formatted = phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.E164 if e164
            else phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )

        return formatted

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

    def strequa(self, article):
        value = article.value

        streque = Streque(value=value, text=article.name, user_id=self.id,
                          standardglas=article.standardglas)
        self.balance -= value

        db.session.add(streque)
        db.session.commit()

        return streque

    def admin_transaction(self, value, message):
        transaction = AdminTransaction(value=value,
                                       text=message,
                                       user_id=self.id)

        self.balance += value  # Value can be negative!

        db.session.add(transaction)
        db.session.commit()

        return transaction

    @property
    def bac(self):
        too_old = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        streques = (Streque.query
                    .filter(Streque.user_id == self.id,
                            Streque.voided.is_(False),
                            Streque.timestamp >= too_old,
                            Streque.standardglas > 0)
                    .order_by(Streque.timestamp)
                    .all())

        if not streques:
            # No drinks with alcohol within the time threshold, return 0 to
            # skip lots of logic below
            return 0

        # 1 unit of alcohol (12 g of pure ethanol) in kg
        standardglas_alcohol_content = 0.012

        # kg of alcohol burned/second
        burn_constant = 1.667e-06

        if self.y_chromosome is False:
            # Female
            body_mass_constant = 0.55
        elif self.y_chromosome is True:
            # Male
            body_mass_constant = 0.7
        else:
            # Somewhere in between
            body_mass_constant = 0.62

        # No alcohol starting out
        alcohol_in_body = 0
        # No streque before first one
        previous_streque_time = None
        for streque in streques:
            if previous_streque_time:
                elapsed_seconds = (streque.timestamp
                                   - previous_streque_time).total_seconds()
            else:
                elapsed_seconds = 0

            # burn_constant will multiply by 0 first iteration, not burning
            # away any alcohol.
            alcohol_in_body += (
                streque.standardglas * standardglas_alcohol_content
                - burn_constant * elapsed_seconds
            )

            # Algorithm will burn away more alcohol that there is in the body
            # which is not possible.
            if alcohol_in_body < 0:
                alcohol_in_body = 0

            previous_streque_time = streque.timestamp

        # Same as the loop above but burning away alcohol since last streque
        elapsed_seconds = (datetime.datetime.utcnow()
                           - previous_streque_time).total_seconds()

        alcohol_in_body -= burn_constant * elapsed_seconds

        if alcohol_in_body < 0:
            return 0

        blood_alcohol_concentration = (
            round(
                1000 * alcohol_in_body / ((self.body_mass or 70)
                                          * body_mass_constant),
                2  # Round to 2 decimals ("#.## permille")
            )
        )

        return blood_alcohol_concentration

    def generate_api_secret(self, lenght=32):
        return hexlify(os.urandom(length)).decode()

    def __str__(self):
        return "{} {} <{}>".format(self.first_name, self.last_name, self.email)


class RegistrationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254))
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    message = db.Column(db.Text)

    def __str__(self):
        return "Registration request {} {} <{}>".format(self.first_name,
                                                        self.last_name,
                                                        self.email)


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    weight = db.Column(db.Integer)

    users = db.relationship('User', back_populates='group')

    def __str__(self):
        return self.name

    @property
    def json(self):
        data = {}
        data['name'] = self.name
        data['weight'] = self.weight
        return data

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    weight = db.Column(db.Integer)
    name = db.Column(db.String(15), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # Ören
    description = db.Column(db.Text)
    # Swedish "units of alcohol", 12 g of alcohol
    standardglas = db.Column(db.Float)

    @property
    def formatted_value(self):
        return flask_babel.format_currency(self.value/100, 'SEK')

    @property
    def html_description(self):
        return markdown.markdown(self.description)

    @property
    def json(self):
        data = {}
        data['id'] = self.id
        data['weight'] = self.weight
        data['name'] = self.name
        data['description'] = self.description
        data['standardglas'] = self.standardglas
        return data


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(50))
    value = db.Column(db.Integer, nullable=False)  # Ören
    voided = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.datetime.utcnow)
    type = db.Column(db.String(50))

    user = db.relationship('User', back_populates='transactions')

    __mapper_args__ = {
        'polymorphic_identity': 'transaction',
        'polymorphic_on': type,
    }

    def void_and_refund(self):
        if self.voided:
            return False

        self.user.balance -= self.value

        self.voided = True
        db.session.commit()

        return True

    @property
    def formatted_value(self):
        return flask_babel.format_currency(self.value/100, 'SEK')

    def __str__(self):
        return "{}: {} @ {}".format(self.__class__.__name__,
                                    self.value, self.user)
    @property
    def json(self):
        data = {}
        data['id'] = self.id
        data['text'] = self.text
        data['voided'] = self.voided
        data['value'] = self.value
        data['formatted_value'] = self.formatted_value
        data['user_id'] = self.user_id
        data['timestamp'] = self.timestamp.isoformat()
        data['type'] = self.type
        return data

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

class AdminTransaction(Transaction):
    __mapper_args__ = {
        'polymorphic_identity': 'admin_transaction',
    }

class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(150), nullable=False)
    who = db.Column(db.String(150))
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.datetime.utcnow)

    def __str__(self):
        return "{}... — {}".format(self.text[:20], self.who[:10] or "<None>")

    @property
    def json(self):
        data = {}
        data['id'] = self.id
        data['text'] = self.text
        data['who'] = self.who
        data['timestamp'] =  self.timestamp.isoformat()
        return data

class ProfilePicture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    user = db.relationship('User', foreign_keys=user_id,
                           backref='profile_pictures')
