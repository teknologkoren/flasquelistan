from flasquelistan.models.base import db


class DiscordRoleView(db.Model):
    """A set of Discord roles that admins edit side by side on the Discord
    role admin page, e.g. the singing groups SG1, SG2 and SG3.

    The views also act as the allowlist: a role can only be edited on that
    page if it is part of a view.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    # Whether adding someone to one of the roles removes them from the
    # view's other roles by default. Only a default for the editor; nothing
    # enforces it.
    exclusive = db.Column(db.Boolean, nullable=False, default=False)
    weight = db.Column(db.Integer, nullable=False, default=0)

    roles = db.relationship('DiscordRoleViewRole', back_populates='view',
                            cascade='all, delete-orphan')

    @property
    def role_ids(self):
        return {role.role_id for role in self.roles}

    def __str__(self):
        return f"{self.name}"


class DiscordRoleViewRole(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    view_id = db.Column(db.Integer, db.ForeignKey('discord_role_view.id'), nullable=False)
    role_id = db.Column(db.String(20), nullable=False)

    view = db.relationship('DiscordRoleView', back_populates='roles')

    __table_args__ = (db.UniqueConstraint('view_id', 'role_id'),)
