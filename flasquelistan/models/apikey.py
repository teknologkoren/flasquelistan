import datetime
import hashlib
import secrets

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.exc import NoResultFound

from flasquelistan.models.base import db
from flasquelistan.models.transactions import Transaction


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
        except NoResultFound:
            return None

        if not api_key.is_enabled:
            return None

        api_key.last_used_timestamp = datetime.datetime.utcnow()
        db.session.commit()
        return api_key

    def __str__(self):
        return f"ApiKey \"{self.name}\" belonging to {self.user}"
