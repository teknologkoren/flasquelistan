import datetime
import hashlib

import flask
from flask import current_app
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required
from sqlalchemy.sql.expression import extract, func, not_

from flasquelistan import forms, models, util

mod = flask.Blueprint('strequelistan', __name__)
mod.before_request(login_required(lambda: None))


@mod.route('/')
def index():
    groups = (models.Group
              .query
              .filter(models.Group.users.any())  # Only groups with users
              .order_by(models.Group.weight.desc())
              .all()
              )

    vip = (
        models.User
        .query
        .filter(
            models.User.active.is_(True),
            models.User.balance >= 1000 * 100,
        )
        .order_by(models.User.balance.desc())
        .all()
    )

    too_old = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    users_with_streques = (
        models.User
        .query
        .join(models.User.transactions)
        .filter(
            models.Transaction.type.is_('streque'),
            models.Streque.voided.is_(False),
            models.Streque.timestamp >= too_old,
            models.Streque.standardglas > 0
        )
        .all()
    )

    current_app.jinja_env.filters['is_active'] = \
        lambda items: [i for i in items if i.active]

    today = datetime.date.today()
    birthdays = (
        models.User
        .query
        .filter(
            extract('month', models.User.birthday) == today.month,
            extract('day', models.User.birthday) == today.day
        )
        .order_by(models.User.first_name)
        .all()
    )
    if birthdays:
        emojis = ['🎂', '🍰', '🧁', '✨', '🍾', '🎉', '🎈']
        md5 = hashlib.md5(today.isoformat().encode())
        i = int.from_bytes(md5.digest(), 'little') % len(emojis)
        birthday_emoji = emojis[i]
    else:
        birthday_emoji = None

    random_quote = models.Quote.query.order_by(func.random()).first()

    articles = (
        models.Article
        .query
        .filter_by(is_active=True)
        .order_by(models.Article.weight.desc())
        .all()
    )

    # If the user has not yet connected their Discord account, and they are in a group
    # connected to Discord, show a flash message.
    if (not current_user.discord_user_id and
        current_user.group and
        current_user.group.discord_role_id):
        flask.flash(
            _l('Kören har flyttat från Messenger till Discord!') +
            f' <a href="{ flask.url_for("discord_oauth.discord")}">' +
            _l('Gå med i vår Discord-server här.') +
            '</a>',
            'info'
        )

    if current_app.config.get('DISPLAY_BALANCE_WARNINGS', True):
        if current_user.balance <= 0:
            flask.flash(
                _l("Det finns inga pengar på kontot. Dags att fylla på!"),
                'error'
            )
        elif current_user.balance < 10000:
            flask.flash(
                _l("Det är ont om pengar på kontot. Dags att fylla på?"),
                'warning'
            )

    notification_count = (
        models.Notification
        .query
        .filter_by(
            user_id=current_user.id,
            is_acknowledged=False
        )
        .count()
    )

    if current_user.is_admin:
        has_pending_nicknames = (models.NicknameChange.query
            .filter_by(status=models.NicknameChangeStatus.PENDING).count() > 0)
    else:
        has_pending_nicknames = False

    return flask.render_template(
        'strequelistan.html',
        groups=groups,
        quote=random_quote,
        articles=articles,
        notification_count=notification_count,
        has_pending_nicknames=has_pending_nicknames,
        users_with_streques=users_with_streques,
        birthdays=birthdays,
        birthday_emoji=birthday_emoji,
        vip=vip
    )


@mod.route('/strequa', methods=['POST'])
def add_streque():
    if flask.request.is_json:
        data = flask.request.get_json()
    else:
        form = forms.AddStrequeForm()
        data = {
            'user_id': form.user_id.data,
            'article_id': form.article_id.data
        }

    try:
        user = models.User.query.get(data['user_id'])
        article_id = int(data['article_id'])
    except (KeyError, ValueError, TypeError):
        flask.abort(400)

    article = models.Article.query.get(article_id)

    if not article:
        flask.abort(400)

    streque = user.strequa(article, current_user)

    if user != current_user:
        text = "{name} strequade en {article} på dig.".format(
            name=current_user.displayname,
            article=article.name
        )
        notification = models.Notification(
            text=text,
            user_id=user.id,
            type='streque',
            reference=str(streque.id)
        )
        models.db.session.add(notification)
        models.db.session.commit()
        util.emit_notification_event(notification)

    if flask.request.is_json:
        response = {
            'user_id': user.id,
            'value': streque.value,
        }

        if user == current_user:
            response['balance'] = user.balance

        return flask.jsonify(response)

    else:
        flask.flash(_("%(text)s-streque på %(name)s tillagt.",
                      text=streque.text, name=user.full_name),
                    'success')
        return flask.redirect(flask.url_for('strequelistan.index'))


@mod.route('/void', methods=['POST'])
def void_streque():
    if flask.request.is_json:
        data = flask.request.get_json()
    else:
        form = forms.VoidStrequeForm()
        data = {
            'streque_id': form.streque_id.data
        }

    try:
        streque_id = data['streque_id']
    except (KeyError, ValueError):
        flask.abort(400)

    streque = models.Streque.query.get(streque_id)

    if not streque or streque.too_old() or streque.voided:
        flask.abort(400)

    streque.void_and_refund()

    streque_notification = (
        models.Notification
        .query
        .filter_by(
            user_id=streque.user.id,
            type='streque',
            reference=str(streque.id),
            is_sent=False
        )
        .first()
    )
    if streque_notification:
        # Found a notification, and it has not been sent.
        # Remove it as if nothing happened! :O
        models.db.session.delete(streque_notification)
    elif streque.user_id != current_user.id:
        # The notification has been sent and potentially read, we must
        # send a new notification that the streque was voided.
        text = "{name} ångrade ett av dina {article}-streque.".format(
            name=current_user.displayname,
            article=streque.text
        )
        void_notification = models.Notification(
            text=text,
            user_id=streque.user_id,
            type='streque-void',
            reference=str(streque.id)
        )
        models.db.session.add(void_notification)
        models.db.session.commit()
        util.emit_notification_event(void_notification)

    models.db.session.commit()

    if flask.request.is_json:
        return flask.jsonify(
            streque_id=streque.id,
            user_id=streque.user.id,
            value=streque.value,
            balance=streque.user.balance
        )

    else:
        flask.flash(_("Ångrade %(text)s-streque på %(name)s.",
                      text=streque.text,
                      name=streque.user.full_name),
                    'success')
        return flask.redirect(flask.url_for('strequelistan.history'))


@mod.route('/articles')
def article_description():
    articles = (models.Article
                .query
                .filter(models.Article.is_active.is_(True))
                .order_by(models.Article.weight.desc())
                .all()
                )
    return flask.render_template('article_description.html', articles=articles)


@mod.route('/paperlist')
def paperlist():

    if flask.request.args.get("active", "false").lower() == "true":
        users = (models.User.query
                 .filter(models.User.active.is_(True))
                 .order_by(models.User.first_name))
    else:
        users = (models.User.query
                 .order_by(models.User.first_name))

    groups = models.Group.query.all()

    articles = (models.Article
                .query
                .order_by(models.Article.weight.desc())
                .all()
                )
    try:
        empty = int(flask.request.args.get("empty", "0"))
    except ValueError:
        empty = 0

    return flask.render_template('paperlist.html',
                                 users=users,
                                 groups=groups,
                                 articles=articles,
                                 empty=empty)


@mod.route('/history')
def history():
    streques = (models.Streque.query
                .filter(not_(models.Streque.too_old()),
                        models.Streque.voided.is_(False))
                .order_by(models.Streque.timestamp.desc())
                .all())

    return flask.render_template('history.html', streques=streques)
