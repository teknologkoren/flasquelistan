import datetime
import hashlib
import os
import secrets
from attr import has

import flask
import flask_babel
from flask import current_app, abort, request
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required
from flask_uploads import UploadNotAllowed
from sqlalchemy.sql.expression import extract, func, not_

from flasquelistan import forms, models, util
from flasquelistan.views import auth
from flasquelistan.discord import DiscordClient

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
        lambda l: [i for i in l if i.active]

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


@mod.route('/transfer', methods=['POST'])
def credit_transfer():
    form = forms.CreditTransferForm()

    payer = (models.User
             .query
             .filter_by(id=form.payer_id.data)
             .first()
             )

    payee = (models.User
             .query
             .filter_by(id=form.payee_id.data)
             .first()
             )

    if not (payer and payee):
        flask.abort(400)

    redir = flask.redirect(
        flask.url_for('strequelistan.show_profile', user_id=payee.id)
    )

    if form.validate_on_submit():
        if payer != current_user:
            flask.flash(
                _l("Du kan bara föra över pengar från dig själv! >:("),
                'error'
            )
            return redir

        value = int(form.value.data * 100)  # To ören

        message = form.message.data.strip()
        if not message:
            message = None

        credit_transfer = models.CreditTransfer.create(
            payer, payee, current_user, value, message
        )

        flask.flash(
            _("Förde över %(a)i pengar till %(name)s",
              a=value/100, name=payee.full_name),
            'success'
        )

        with flask_babel.force_locale('sv_SE'):
            notification_text = (
                "Streque Pay!\n{money} från {name}".format(
                    money=flask_babel.format_currency(value / 100, 'SEK'),
                    name=payer.displayname,
                )
            )
            if message:
                notification_text += ": {}".format(message)
        payee_notification = models.Notification(
            text=notification_text,
            user_id=payee.id,
            type='streque-pay',
            reference=str(credit_transfer.id)
        )
        models.db.session.add(payee_notification)
        models.db.session.commit()

    elif form.is_submitted():
        forms.flash_errors(form)

    return redir


@mod.route('/articles')
def article_description():
    articles = (models.Article
                .query
                .filter(models.Article.is_active.is_(True))
                .order_by(models.Article.weight.desc())
                .all()
                )
    return flask.render_template('article_description.html', articles=articles)


@mod.route('/payments')
def payments():
    return flask.render_template('payments.html')


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


def gallery_page_for_image(image, user=None):
    images = (
        models.ProfilePicture
        .query
        .order_by(models.ProfilePicture.timestamp.desc())
    )

    if user:
        images = images.filter(models.ProfilePicture.user_id.is_(user.id))

    pagination = images.paginate(per_page=20)

    if not pagination.has_next:
        return pagination.page

    while pagination.has_next:
        pagination = pagination.next()
        if image in pagination.items:
            return pagination.page

    return None


@mod.route('/gallery/')
@mod.route('/gallery/<int:page>/')
def gallery(page=1):
    image_query = (
        models.ProfilePicture
        .query
        .order_by(models.ProfilePicture.timestamp.desc())
        .paginate(
            page=page,
            per_page=20
        )
    )

    return flask.render_template(
        'gallery.html',
        images=image_query.items,
        page=page,
        has_prev=image_query.has_prev,
        has_next=image_query.has_next,
        last_page=image_query.pages,
    )


@mod.route('/gallery/user/<int:user_id>/')
@mod.route('/gallery/user/<int:user_id>/<int:page>')
def user_gallery(user_id, page=1):
    user = models.User.query.get_or_404(user_id)

    image_query = (
        models.ProfilePicture
        .query
        .filter(
            models.ProfilePicture.user_id.is_(user.id)
        )
        .order_by(models.ProfilePicture.timestamp.desc())
        .paginate(
            page=page,
            per_page=20,
        )
    )

    return flask.render_template(
        'user_gallery.html',
        user=user,
        images=image_query.items,
        page=page,
        has_prev=image_query.has_prev,
        has_next=image_query.has_next,
        last_page=image_query.pages,
    )


@mod.route('/profile/<int:user_id>/')
def show_profile(user_id):
    user = models.User.query.get_or_404(user_id)

    transactions = (user.transactions
                    .filter(models.Streque.voided.is_(False))
                    .order_by(models.Transaction.timestamp.desc())
                    .limit(5))

    change_nickname_form = forms.ChangeNicknameForm()
    upload_profile_picture_form = forms.UploadProfilePictureForm()
    change_profile_picture_form = forms.ChangeProfilePictureFormFactory(user)
    credit_transfer_form = forms.CreditTransferForm()
    credit_transfer_form.payer_id.data = current_user.id
    credit_transfer_form.payee_id.data = user.id

    if current_user.is_admin:
        admin_transaction_form = forms.UserTransactionForm()
    else:
        admin_transaction_form = None

    return flask.render_template(
        'show_profile.html',
        user=user,
        transactions=transactions,
        change_nickname_form=change_nickname_form,
        profile_picture_form=upload_profile_picture_form,
        change_profile_picture_form=change_profile_picture_form,
        credit_transfer_form=credit_transfer_form,
        admin_transaction_form=admin_transaction_form,
    )


@mod.route('/profile/<int:user_id>/admin-transaction', methods=['POST'])
def admin_transaction(user_id):
    if not current_user.is_admin:
        flask.flash(_l("Du måste vara admin för att göra det!"), 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    user = models.User.query.get_or_404(user_id)
    form = forms.UserTransactionForm()

    if form.validate_on_submit():
        transaction = user.admin_transaction(
            int(form.value.data * 100),
            form.text.data,
            by_user=current_user
        )
        transaction.create_notification()
        flask.flash(_l("Transaktion utförd!"), 'success')

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.redirect(
        flask.url_for('strequelistan.show_profile', user_id=user_id)
    )


@mod.route('/profile/<int:user_id>/change_nickname', methods=['POST'])
def change_nickname(user_id):
    user = models.User.query.get_or_404(user_id)
    form = forms.ChangeNicknameForm()

    if form.validate_on_submit():
        nickname_change = models.NicknameChange(
            user_id=user.id,
            nickname=form.nickname.data,
            status=models.NicknameChangeStatus.PENDING,
            created_timestamp=datetime.datetime.utcnow(),
            suggester=current_user
        )

        # A user should be able to change their own nickname without approval,
        # and admins should also not need approval to change nicknames.
        needs_approval = (current_user != user) and (not current_user.is_admin)

        if not needs_approval:
            user.nickname = nickname_change.nickname
            nickname_change.status = models.NicknameChangeStatus.APPROVED
            nickname_change.reviewed_timestamp = datetime.datetime.utcnow()

        user.nickname_changes.append(nickname_change)
        models.db.session.commit()

        if needs_approval:
            flask.flash(
                _l("Din smeknamnsändring är sparad och väntar på att bli godkänd."), 'success')
        else:
            flask.flash(_l("Din smeknamnsändring är sparad."), 'success')

        return flask.redirect(
            flask.url_for('strequelistan.user_nicknames', user_id=user_id)
        )

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.redirect(
        flask.url_for('strequelistan.show_profile', user_id=user_id)
    )


@mod.route('/profile/<int:user_id>/upload-profile-picture', methods=['POST'])
def upload_profile_picture(user_id):
    form = forms.UploadProfilePictureForm()

    if form.validate_on_submit() and form.upload.data:
        user = models.User.query.get_or_404(user_id)

        try:
            filename = util.profile_pictures.save(form.upload.data)
        except UploadNotAllowed:
            flask.flash(
                _l("Kunde inte ladda upp bilden, försök med ett annat "
                   "filnamn eller filformat."),
                'error'
            )
            return flask.redirect(
                flask.url_for('strequelistan.show_profile', user_id=user_id)
            )

        if os.path.splitext(filename)[1].lower() in ('.jpg', '.jpeg'):
            util.rotate_jpeg(util.profile_pictures.path(filename))

        profile_picture = models.ProfilePicture(
            filename=filename,
            user_id=user.id
        )

        user.profile_picture = profile_picture

        models.db.session.add(profile_picture)
        models.db.session.commit()

        flask.flash(_l("Profilbilden har ändrats!"), 'success')

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.redirect(
        flask.url_for('strequelistan.show_profile', user_id=user_id)
    )


@mod.route('/profile/<int:user_id>/change-profile-picture', methods=['POST'])
def change_profile_picture(user_id):
    user = models.User.query.get_or_404(user_id)

    if current_user.id != user.id and not current_user.is_admin:
        flask.flash(_l("Du får bara redigera din egen profil! ಠ_ಠ"), 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    form = forms.ChangeProfilePictureFormFactory(user)

    if form.validate_on_submit():
        # The "none" choice seems to work. Not sure why.
        user.profile_picture_id = form.profile_picture.data
        models.db.session.commit()

        flask.flash(_l("Din profilbild har ändrats!"), 'success')

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.redirect(
        flask.url_for('strequelistan.show_profile', user_id=user_id)
    )


@mod.route('/profile/<int:user_id>/delete-profile-picture', methods=['POST'])
def delete_profile_picture(user_id):
    user = models.User.query.get_or_404(user_id)

    if current_user.id != user.id and not current_user.is_admin:
        flask.flash(_l("Du får bara redigera din egen profil! ಠ_ಠ"), 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    form = forms.ChangeProfilePictureFormFactory(user)

    if form.validate_on_submit():
        if form.profile_picture.data == 'none':
            flask.flash(_l(
                "Du kan inte ta bort "
                "<a href="
                "\"https://phys.org/news/2014-08-what-is-nothing.html\">"
                "ingenting"
                "</a>!"), 'error'
            )

        elif form.profile_picture.data:
            profile_picture = (models.ProfilePicture
                               .query
                               .get_or_404(form.profile_picture.data)
                               )

            models.db.session.delete(profile_picture)
            models.db.session.commit()

            flask.flash(_l("Profilbilden har tagits bort!"), 'success')

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.redirect(
        flask.url_for('strequelistan.show_profile', user_id=user_id)
    )


@mod.route('/profile/<int:user_id>/history')
def user_history(user_id):
    user = models.User.query.get_or_404(user_id)

    if current_user.id != user.id and not current_user.is_admin:
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    transactions = (user.transactions
                    .filter(models.Streque.voided.is_(False))
                    .order_by(models.Transaction.timestamp.desc())
                    .all())

    return flask.render_template('user_history.html', user=user,
                                 transactions=transactions)


@mod.route('/profile/<int:user_id>/nicknames')
def user_nicknames(user_id):
    user = models.User.query.get_or_404(user_id)

    pending_changes = (user.nickname_changes
                       .filter(models.NicknameChange.status.is_(models.NicknameChangeStatus.PENDING))
                       .order_by(models.NicknameChange.created_timestamp.desc())
                       .all())

    changes = (user.nickname_changes
               .filter(models.NicknameChange.status.is_(models.NicknameChangeStatus.APPROVED))
               .order_by(models.NicknameChange.reviewed_timestamp.desc())
               .all())

    if not current_user.is_admin:
        pending_changes = list(filter(
            # For non-admins, only show suggestions that the user made themselves.
            lambda change: change.suggester == current_user,
            pending_changes
        ))

    return flask.render_template('user_nicknames.html', user=user,
                                 pending_changes=pending_changes, changes=changes)


@mod.route('/profile/<int:user_id>/vcard')
def user_vcard(user_id):
    user = models.User.query.get_or_404(user_id)
    response = flask.make_response(user.vcard)
    response.mimetype = 'text/vcard'
    response.headers['Content-Disposition'] = (
        'attachment; filename="{}_{}.vcf"'
        .format(user.first_name, user.last_name)
    )
    return response


@mod.route('/profile/<int:user_id>/edit/', methods=['GET', 'POST'])
def edit_profile(user_id):
    user = models.User.query.get_or_404(user_id)

    if current_user.id != user.id and not current_user.is_admin:
        flask.flash(_l("Du får bara redigera din egen profil! ಠ_ಠ"), 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    if current_user.is_admin:
        form = forms.FullEditUserForm(obj=user)
        form.group_id.choices = [(g.id, g.name) for g in models.Group.query]
        form.group_id.choices.insert(0, (-1, 'Ingen'))
    else:
        form = forms.EditUserForm(obj=user)

    if form.validate_on_submit():
        if current_user.is_admin:
            user.first_name = form.first_name.data
            user.last_name = form.last_name.data
            user.active = form.active.data
            user.is_admin = form.is_admin.data
            if form.group_id.data != -1:
                user.group_id = form.group_id.data
            else:
                user.group_id = None

        if user.nickname != form.nickname.data:
            nickname_change = models.NicknameChange(
                user_id=user.id,
                nickname=form.nickname.data,
                status=models.NicknameChangeStatus.APPROVED,
                created_timestamp=datetime.datetime.utcnow(),
                reviewed_timestamp=datetime.datetime.utcnow(),
                suggester=current_user
            )
            user.nickname_changes.append(nickname_change)

        user.nickname = form.nickname.data
        user.birthday = form.birthday.data
        user.phone = form.phone.data
        user.body_mass = form.body_mass.data

        y_chromosome = form.y_chromosome.data
        if y_chromosome == 'yes':
            user.y_chromosome = True
        elif y_chromosome == 'no':
            user.y_chromosome = False
        else:
            user.y_chromosome = None

        models.db.session.commit()

        if user.discord_user_id is not None:
            DiscordClient.sync_roles(user)

        flask.flash(_l("Ändringarna har sparats!"), 'success')
        return flask.redirect(flask.url_for('strequelistan.show_profile',
                                            user_id=user.id))

    else:
        if user.y_chromosome is True:
            form.y_chromosome.data = 'yes'
        elif user.y_chromosome is False:
            form.y_chromosome.data = 'no'
        else:
            form.y_chromosome.data = 'n/a'

    return flask.render_template('edit_profile.html', form=form, user=user)


@mod.route('/profile/<int:user_id>/api-keys', methods=['GET'])
def api_keys(user_id):
    user = models.User.query.get_or_404(user_id)

    if current_user.id != user.id and not current_user.is_admin:
        flask.flash(
            _l("Du får bara hantera din egna API-nycklar! ಠ_ಠ"), 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    return flask.render_template('api_keys.html', user=user)


@mod.route('/profile/<int:user_id>/api-keys/new', methods=['GET', 'POST'])
@mod.route('/profile/<int:user_id>/api-keys/edit/<int:api_key_id>', methods=['GET', 'POST'])
def edit_api_key(user_id, api_key_id=None):
    user = models.User.query.get_or_404(user_id)

    if current_user.id != user.id and not current_user.is_admin:
        flask.flash(
            _l("Du får bara hantera din egna API-nycklar! ಠ_ಠ"), 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    if api_key_id:
        api_key = models.ApiKey.query.get_or_404(api_key_id)
        can_be_deleted = api_key.can_be_deleted
        form = forms.EditApiKeyForm(obj=api_key)
    else:
        api_key = None
        can_be_deleted = False
        form = forms.EditApiKeyForm()

    if form.validate_on_submit():
        if not api_key:
            api_key = models.ApiKey()

        # Only admins are allowed to create keys with the admin bit set.
        if form.has_admin_privileges.data:
            if not user.is_admin:
                abort(400)
        api_key.has_admin_privileges = form.has_admin_privileges.data

        # If it's a new api key or if the user opted to reset the key,
        # generate a new key.
        if form.reset_key.data or not api_key_id:
            secret = models.ApiKey.generate_key()
            api_key.api_key = secret
        else:
            secret = None

        api_key.name = form.name.data
        api_key.short_name = form.short_name.data if form.short_name.data else None
        api_key.is_enabled = form.is_enabled.data

        if not api_key_id:
            user.api_keys.append(api_key)

        models.db.session.commit()

        if secret:
            flask.flash(
                _l(
                    "Din API-nyckel med namnet \"%(name)s\" är: \"%(secret)s\"."
                    " Du kommer inte kunna se den igen, så se till att spara den nu.",
                    secret=secret,
                    name=form.name.data
                ),
                'success')
        return flask.redirect(flask.url_for('strequelistan.api_keys',
                                            user_id=user.id))

    return flask.render_template('edit_api_key.html',
                                 form=form,
                                 user=user,
                                 api_key=api_key,
                                 can_be_deleted=can_be_deleted)


@mod.route('/profile/<int:user_id>/edit/api-keys/delete/<int:api_key_id>', methods=['POST'])
def delete_api_key(user_id, api_key_id):
    api_key = models.ApiKey.query.get_or_404(api_key_id)
    if api_key.user.id != user_id:
        abort(404)

    if not api_key.can_be_deleted:
        abort(400)

    models.db.session.delete(api_key)
    models.db.session.commit()

    flask.flash(_l("Api-nyckeln \"%(name)s\" är borttagen.", name=api_key.name), 'success')
    return flask.redirect(flask.url_for('strequelistan.api_keys', user_id=user_id))


@mod.route('/profile/<int:user_id>/edit/password', methods=['GET', 'POST'])
def change_email_or_password(user_id):
    user = models.User.query.get_or_404(user_id)

    if current_user.id != user.id and not user.is_admin:
        if current_user.is_admin:
            form = forms.ChangeEmailOrPasswordForm(obj=user, user=user,
                                                   nopasswordvalidation=True)

        else:
            flask.flash(_l("Du får bara redigera din egen profil! ಠ_ಠ"),
                        'error')
            return flask.redirect(flask.url_for('.show_profile',
                                                user_id=user_id))

    else:
        form = forms.ChangeEmailOrPasswordForm(obj=user, user=user)

    if form.validate_on_submit():
        if form.email.data != user.email:
            auth.verify_email(user, form.email.data)
            flask.flash(_l("En länk för att verifiera e-postadressen har "
                           "skickats till %(email)s.",
                           email=form.email.data),
                        'info')

        if form.new_password.data:
            user.password = form.new_password.data
            flask.flash(_l("Lösenordet har ändrats!"), 'success')

        models.db.session.commit()

        return flask.redirect(flask.url_for('strequelistan.show_profile',
                                            user_id=user.id))

    return flask.render_template('change_email_or_password.html',
                                 form=form,
                                 user=user)


@mod.route('/discord/connect')
def discord_redirect():
    return flask.redirect(DiscordClient.get_authorization_url())


@mod.route('/discord/callback')
def discord_callback():
    client = DiscordClient()
    client.authenticate(request.url, request.args.get("state"))

    discord_user = client.get_user()
    client.add_to_server(
        discord_user['id'],
        current_user.displayname,
        DiscordClient.get_expected_roles(current_user))

    current_user.discord_user_id = discord_user["id"]
    current_user.discord_username = f'{discord_user["username"]}#{discord_user["discriminator"]}'
    models.db.session.commit()

    guild_id = current_app.config.get("DISCORD_GUILD_ID")
    flask.flash(_l("Du är nu tillagd i vår Discord-server! %sKlicka här för att besöka den.%s") %
                (f'<a href="https://discord.com/channels/{guild_id}" target="_blank">', '</a>'), 'success')
    return flask.redirect(flask.url_for('strequelistan.show_profile', user_id=current_user.id))
