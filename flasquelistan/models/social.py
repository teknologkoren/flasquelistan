import datetime

import flask
import markupsafe

from flasquelistan import util
from flasquelistan.models.base import db


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

    @staticmethod
    def format_notification_html(reference):
        poke = db.session.get(Poke, reference)
        if not poke:
            return None
        
        profile_link = flask.url_for('profile.show_profile', user_id=poke.poker_id)
        safe_name = markupsafe.escape(poke.poker.displayname)
        return f'<a href="{profile_link}">{safe_name}</a> puffade dig!'

    @staticmethod
    def format_notification_markdown(reference):
        poke = db.session.get(Poke, reference)
        if not poke:
            return None

        profile_link = flask.url_for('profile.show_profile', user_id=poke.poker_id, _external=True)
        return f"[{poke.poker.displayname}]({profile_link}) puffade dig!"

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

    @property
    def formatted_html(self):
        if self.type == 'poke':
            html = Poke.format_notification_html(self.reference)
            if html:
                return html
        
        return markupsafe.escape(self.text)

    @property
    def formatted_markdown(self):
        if self.type == 'poke':
            md = Poke.format_notification_markdown(self.reference)
            if md:
                return md
        
        return self.text
