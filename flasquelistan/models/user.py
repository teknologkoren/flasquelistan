import base64
import datetime
import enum
import hashlib
import random
import string

import bcrypt
import flask_babel
import flask_login
import vobject
from sqlalchemy.ext.hybrid import hybrid_property

from flasquelistan import models, util
from flasquelistan.models.base import db
from flasquelistan.models.social import Poke
from flasquelistan.models.transactions import AdminTransaction, Streque


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

        if models.TESTING:
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

    def get_last_poke(self, other_user):
        return (
            Poke.query
            .filter(
                (
                    ((Poke.poker_id == other_user.id) & (Poke.pokee_id == self.id)) |
                    ((Poke.poker_id == self.id) & (Poke.pokee_id == other_user.id))
                )
            )
            .order_by(Poke.timestamp.desc())
            .first()
        )

    def poke(self, poker):
        last_poke = self.get_last_poke(poker)

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
