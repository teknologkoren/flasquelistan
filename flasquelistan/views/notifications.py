import flask
from flask_login import current_user, login_required

from flasquelistan import models

mod = flask.Blueprint('notifications', __name__)
mod.before_request(login_required(lambda: None))


@mod.route('/notifications')
def notifications():
    notifications = (
        models.Notification
        .query
        .filter_by(
            user_id=current_user.id,
            is_acknowledged=False
        )
        .order_by(models.Notification.timestamp.desc())
        .all()
    )

    if notifications:
        for notification in notifications:
            notification.is_sent = True
        models.db.session.commit()

    return flask.render_template(
        'notifications.html',
        notifications=notifications
    )


@mod.route('/notifications/mark-read')
def mark_notifications_read():
    # Mark all *sent* notifications as acknowledged.
    notifications = (
        models.Notification
        .query
        .filter_by(
            user_id=current_user.id,
            is_sent=True
        )
        .all()
    )

    if notifications:
        for notification in notifications:
            notification.is_acknowledged = True
        models.db.session.commit()

    return flask.redirect(flask.url_for('strequelistan.index'))
