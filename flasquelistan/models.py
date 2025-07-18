import base64
import datetime
import enum
import hashlib
import random
import secrets
import string

import bcrypt
import flask
import flask_babel
import flask_login
import flask_sqlalchemy
import markdown
import vobject
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property

from flasquelistan import util

TESTING = False
db = flask_sqlalchemy.SQLAlchemy()


class User(flask_login.UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    nickname = db.Column(db.String(50))
    birthday = db.Column(db.Date, nullable=True)
    _phone = db.Column("phone", db.String(20), nullable=True)
    balance = db.Column(db.Integer, default=0)  # Ören (1/100kr)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    body_mass = db.Column(db.Integer, nullable=True)
    y_chromosome = db.Column(db.Boolean, nullable=True)
    lang = db.Column(db.String(20), nullable=True, default="sv_SE")
    discord_user_id = db.Column(db.String(20))
    discord_username = db.Column(db.String(40))

    # use_alter=True adds fk after ProfilePicture has been created to avoid
    # circular dependency
    profile_picture_id = db.Column(
        db.Integer,
        db.ForeignKey('profile_picture.id', use_alter=True)
    )

    group = db.relationship('Group')
    transactions = db.relationship(
        'Transaction',
        back_populates='user',
        lazy='dynamic',
        foreign_keys='Transaction.user_id'
    )
    profile_picture = db.relationship(
        'ProfilePicture',
        foreign_keys=profile_picture_id,
        lazy='joined'
    )
    api_keys = db.relationship(
        'ApiKey',
        back_populates='user',
        foreign_keys='ApiKey.user_id'
    )
    nickname_changes = db.relationship(
        'NicknameChange',
        back_populates='user',
        lazy='dynamic',
        foreign_keys='NicknameChange.user_id'
    )

    # Do not change the following directly, use User.password
    _password_hash = db.Column(db.String(128))
    _password_timestamp = db.Column(db.DateTime)

    @property
    def api_dict(self):
        data = dict()
        data['id'] = self.id
        data['email'] = self.email
        data['first_name'] = self.first_name
        data['last_name'] = self.last_name
        data['full_name'] = self.full_name
        data['nickname'] = self.nickname
        data['birthday'] = self.birthday
        data['phone'] = self.phone
        data['balance'] = self.balance
        data['is_admin'] = self.is_admin
        data['active'] = self.active
        data['group'] = {'id': self.group_id,
                         'name': self.group.name} if self.group else None
        data['lang'] = self.lang
        data['discord_user_id'] = self.discord_user_id
        data['discord_username'] = self.discord_username
        data['bac_emoji'] = self.bac_emoji
        if self.profile_picture:
            data['profile_picture'] = {
                'id': self.profile_picture_id,
                'url': util.url_for_image(
                    self.profile_picture.filename, 'profilepicture'
                )}
        else:
            data['profile_picture'] = None
        return data

    def __init__(self, *args, **kwargs):
        if 'password' not in kwargs:
            password = ''.join(
                random.choice(string.ascii_letters + string.digits) for _ in range(30)
            )
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
        if self.birthday:
            j.add('bday')
            j.bday.value = self.birthday.strftime('%Y%m%d')
        return j.serialize()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def displayname(self):
        name = self.nickname or self.full_name
        if self.has_birthday:
            return f"{name} 🎂"
        else:
            return name

    @property
    def has_birthday(self):
        today = datetime.date.today()
        return (
            self.birthday
            and self.birthday.month == today.month
            and self.birthday.day == today.day
        )

    @hybrid_property
    def phone(self):
        return self._phone

    @phone.setter
    def phone(self, phone):
        """Set phone number, but normalize it first if possible."""

        normalized = util.format_phone_number(phone, e164=True)
        if normalized:
            self._phone = normalized
        else:
            self._phone = phone

    def formatted_phone(self, e164=False):
        return util.format_phone_number(self.phone, e164)

    @property
    def formatted_balance(self):
        return flask_babel.format_currency(self.balance / 100, 'SEK')

    @hybrid_property
    def password(self):
        """Return password hash."""
        return self._password_hash

    @password.setter
    def password(self, plaintext):
        """Generate and save password hash, update password timestamp."""

        if TESTING:
            rounds = 4
        else:
            rounds = 12

        hash = bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds))
        self._password_hash = hash.decode()

        # Save in UTC, password resets compare this to UTC time!
        self._password_timestamp = datetime.datetime.utcnow()

    def verify_password(self, plaintext):
        """Return True if plaintext matches password, else return False."""
        if self._password_hash.startswith('pbkdf2'):
            # Old hash from teknologkoren/Strequelistan

            # Extract hash info from django hash
            # 'pbkdf2_<method>$<rounds>$<salt>$<b64(hash)>'
            hash_meta = self._password_hash.split('$')
            hash_method = hash_meta[0].split('_')[1]
            hash_rounds = hash_meta[1]
            hash_salt = hash_meta[2]
            hash_data = hash_meta[3]

            candidate_hash = hashlib.pbkdf2_hmac(
                hash_method,
                plaintext.encode(),
                hash_salt.encode(),
                int(hash_rounds)
            )

            correct = candidate_hash == base64.b64decode(hash_data)

            if correct:
                # Upgrade hash to bcrypt
                self.password = plaintext
                db.session.commit()

        else:
            correct = bcrypt.checkpw(
                plaintext.encode(),
                self._password_hash.encode()
            )

        return correct

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

    def strequa(self, article, by_user, by_api_key=None):
        value = article.value

        streque = Streque(
            value=-value,
            text=article.name,
            user_id=self.id,
            created_by_id=by_user.id,
            api_key_id=by_api_key.id if by_api_key else None,
            standardglas=article.standardglas
        )
        self.balance -= value

        db.session.add(streque)
        db.session.commit()

        util.emit_balance_change_event(self, self.balance + value)

        return streque

    def admin_transaction(self, value, message, by_user):
        transaction = AdminTransaction(value=value,
                                       text=message,
                                       created_by_id=by_user.id,
                                       user_id=self.id)

        self.balance += value  # Value can be negative!

        db.session.add(transaction)
        db.session.commit()

        util.emit_balance_change_event(self, self.balance - value)

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
            alcohol_in_body -= burn_constant * elapsed_seconds

            # Algorithm will burn away more alcohol that there is in the body
            # which is not possible.
            if alcohol_in_body < 0:

                alcohol_in_body = 0

            alcohol_in_body += (streque.standardglas
                                * standardglas_alcohol_content)

            previous_streque_time = streque.timestamp

        # Same as the loop above but burning away alcohol since last streque
        elapsed_seconds = (datetime.datetime.utcnow()
                           - previous_streque_time).total_seconds()

        alcohol_in_body -= burn_constant * elapsed_seconds

        if alcohol_in_body < 0:
            return 0

        body_mass = self.body_mass or 70
        final_bac = 1000 * alcohol_in_body / (body_mass * body_mass_constant)

        # Round to 2 decimals ("#.## permille")
        blood_alcohol_concentration = round(final_bac, 2)

        return blood_alcohol_concentration

    @property
    def bac_emoji(self):
        bac = self.bac
        if bac < 0.1:
            return None
        elif bac < 0.3:
            return '🍺'
        elif bac < 0.5:
            return '🍻'
        elif bac < 1:
            return '👌'
        elif bac < 1.5:
            return '🕺'
        elif bac < 2:
            return '😟'
        elif bac < 2.5:
            return '🤢'
        elif bac < 3:
            return '😵'
        elif bac < 3.5:
            return '💀'
        elif bac < 4:
            return '🇷🇺'
        else:
            return '🇫🇮'

    @property
    def emoji(self):
        # md5-hash based on user id
        md5 = hashlib.md5(str(self.id).encode())
        # "random" number between 0x0 and 0x44
        i = int.from_bytes(md5.digest(), 'little') % 0x45
        # add number to start of the 'Emoticons' unicode block
        return chr(0x1f600 + i)

    def poke(self, poker):
        last_poke = (
            Poke.query
            .filter(
                (
                    ((Poke.poker_id == poker.id) & (Poke.pokee_id == self.id)) |
                    ((Poke.poker_id == self.id) & (Poke.pokee_id == poker.id))
                )
            )
            .order_by(Poke.timestamp.desc())
            .first()
        )
        # If the last poke was not made by the user that is trying to poke or
        # if the there hasn't been any pokes between these users, we allow the poke.
        if last_poke and last_poke.poker == poker:
            return False

        poke = Poke(poker_id=poker.id, pokee_id=self.id)
        db.session.add(poke)
        db.session.commit()

        return poke


    def __str__(self):
        return f"{self.first_name} {self.last_name} <{self.email}>"

    def __repr__(self):
        return f"User {self.first_name} {self.last_name} <{self.email}>"


class RegistrationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254))
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    message = db.Column(db.Text)

    def __str__(self):
        return f"RegistrationRequest {self.first_name} {self.last_name} <{self.email}>"


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    weight = db.Column(db.Integer)

    # Whether users in the group are considered active choir members.
    active = db.Column(db.Boolean, nullable=False, default=False)

    # A Discord role to add to group members who have connected their Discord accounts.
    discord_role_id = db.Column(db.String(20), nullable=True)

    users = db.relationship('User', back_populates='group')

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        return f"Group {self.name}"


class NicknameChangeStatus(enum.Enum):
    PENDING = 1
    APPROVED = 2
    REJECTED = 3


class NicknameChange(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # The user who this nickname belongs to.
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    nickname = db.Column(db.String(50), nullable=False)
    status = db.Column(db.Enum(NicknameChangeStatus),
                       nullable=False, default=NicknameChangeStatus.PENDING)

    # The user who suggested the change. Should be null for imported legacy nickname
    # changes.
    suggester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # The user who reviewed the change. If explicit approval was not required, this should
    # be null. For imported legacy nickname changes, this should also be null.
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
 
    # Whenever the nickname change was created.
    created_timestamp = db.Column(db.DateTime)

    # Whenever the nickname change was reviewed. If explicit approval was not required,
    # this should be the same as `created_timestamp`.
    reviewed_timestamp = db.Column(db.DateTime)

    # This is the latest timestamp before `created_timestamp` when we know that the user
    # had a different nickname. This should only be set for legacy nickname changes,
    # where we only have snapshots from (sometimes sparse) backups. 
    lower_bound_timestamp = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', foreign_keys=user_id,
                           back_populates='nickname_changes')
    suggester = db.relationship('User', foreign_keys=suggester_id)
    reviewer = db.relationship('User', foreign_keys=reviewer_id)


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

        suffix = ": {}".format(message) if message else ""
        payer_message = "Till {}{}".format(payee.full_name, suffix)
        payee_message = "Från {}{}".format(payer.full_name, suffix)

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


class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(150), nullable=False)
    who = db.Column(db.String(150))
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.datetime.utcnow)

    def has_date(self):
        return self.timestamp >= datetime.datetime(2016, 11, 2)

    def has_time(self):
        return self.timestamp >= datetime.datetime(2019, 7, 7)

    def cleaned(self):
        lines = [line for line in self.text.splitlines() if line]
        return "\n".join(lines)

    @property
    def api_dict(self):
        data = dict()
        data['id'] = self.id
        data['text'] = self.cleaned()
        data['who'] = self.who
        data['has_date'] = self.has_date()
        data['has_time'] = self.has_time()
        data['time'] = self.timestamp
        data['timestamp'] = self.timestamp.timestamp()
        return data

    def __str__(self):
        return "\"{}...\" — {}".format(self.text[:20], self.who[:10] or "<None>")

    def __repr__(self):
        return "Quote \"{}...\" — {}".format(self.text[:20], self.who[:10] or "<None>")


class ProfilePicture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    user = db.relationship('User', foreign_keys=user_id,
                           backref='profile_pictures')
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.datetime.utcnow)

    def __str__(self):
        return f"{self.user_id}: {self.filename}"

    def __repr__(self):
        return f"ProfilePicture {self.filename} {self.user_id}"


class Poke(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poker_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    pokee_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.datetime.utcnow)

    poker = db.relationship('User', foreign_keys=poker_id)
    pokee = db.relationship('User', foreign_keys=pokee_id)

    def create_notification(self):
        notification = Notification(
            text=f"{self.poker.displayname} puffade dig!",
            user_id=self.pokee_id,
            type="poke",
            reference=str(self.id)
        )
        db.session.add(notification)
        db.session.commit()
        util.emit_notification_event(notification)
        return notification

    def __str__(self):
        return f"{self.poker.displayname} poked {self.pokee.displayname}"

    def __repr__(self):
        return f"Poke {self.id} from {self.poker_id} to {self.pokee_id}"


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_sent = db.Column(db.Boolean, nullable=False, default=False)
    is_acknowledged = db.Column(db.Boolean, nullable=False, default=False)

    # So the following is not exactly best practice. E.g., for a streque we
    # would save type='streque' and reference=str(<streque primary key>), to be
    # able to recall and remove the notification if it was voided before the
    # notification was sent.
    # The use case, IMO, calls for this simplicity. It could be used for:
    #  * Removing obsolete notifications
    #  * Grouping notifications of the same type
    #  * Probably some other, non-critical things
    # It is not needed for the object's own integrity. If we can't figure out
    # what the type means, or the type or reference otherwise does not make
    # sense, we just display the notification as is. It is then a generic,
    # potentially obsolete notification. And that's ok ¯\_(ツ)_/¯
    type = db.Column(db.String(50), nullable=True)
    reference = db.Column(db.String(50), nullable=True)

    user = db.relationship('User', foreign_keys=user_id,
                           backref='notifications')
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.datetime.utcnow)

    def __str__(self):
        return "{} \"{}...\"".format(self.user_id, self.text[:20])

    def __repr__(self):
        return "Notification \"{}...\" to user {}".format(self.text[:20], self.user_id)


class ApiKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    _api_key_hash = db.Column(
        db.String(50), nullable=False, unique=True, index=True)
    created_timestamp = db.Column(db.DateTime, nullable=False,
                                  default=datetime.datetime.utcnow)
    last_used_timestamp = db.Column(db.DateTime)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)

    # Human-readable identifier of the key. Useful to show which API client
    # performed an action, as well as for developers to keep track of their
    # keys.
    name = db.Column(db.String(50), nullable=False, unique=True)

    # Optional short identifier, to be shown next to the date of transactions
    # made using the key. This should preferably be an emoji, for example '📞'
    # for streques made by phone call. If this is null or empty, transactions
    # created with this key will look the same as ones made through the
    # website.
    short_name = db.Column(db.String(10), nullable=True)

    # Whether clients using the key should be able to perform admin actions.
    # API key admin privileges are only valid if the associated user is also
    # an admin.
    has_admin_privileges = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship(
        'User',
        back_populates='api_keys',
        foreign_keys=[user_id]
    )

    @hybrid_property
    def api_key(self):
        """Return API key hash."""
        return self._api_key_hash

    @api_key.setter
    def api_key(self, key):
        """Set the API key. A hash of it will be persisted in the database.

        The key must be a securely generated random string with at least
        128 bits of entropy.
        """
        self._api_key_hash = ApiKey.hash_key(key)

    @property
    def is_admin(self):
        """Whether the key has admin privileges _and_ the associated user is
        an admin"""
        return self.has_admin_privileges and self.user.is_admin

    @property
    def can_be_deleted(self):
        """Whether the key can deleted. Keys associated with transactions or
        other objects cannot be deleted."""
        return Transaction.query.filter(Transaction.api_key_id.is_(self.id)).count() == 0

    @staticmethod
    def generate_key():
        """Return a new cryptographically strong random API key with 128 bits
        of entropy."""
        return secrets.token_hex(16)

    @staticmethod
    def hash_key(key):
        # Using sha256 without a salt is good enough here. Since the randomly
        # generated API key already has a lot of entropy, a slow hash function
        # like bcrypt (which we use for passwords) would be overkill, and just
        # introduce unnecessary latency on every API call.
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def authenticate(key):
        """If key is a valid and active api key, return the corresponding
        ApiKey. If not, return None."""
        try:
            api_key = ApiKey.query.filter_by(
                _api_key_hash=ApiKey.hash_key(key)).one()
        except:
            return None

        if not api_key.is_enabled:
            return None

        api_key.last_used_timestamp = datetime.datetime.utcnow()
        db.session.commit()
        return api_key

    def __str__(self):
        return f"ApiKey \"{self.name}\" belonging to {self.user}"
