import datetime
import os

import flask
from flask import abort
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required
from flask_uploads import UploadNotAllowed

from flasquelistan import forms, models, util
from flasquelistan.views import auth
from flasquelistan.discord import DiscordClient

mod = flask.Blueprint('profile', __name__)
mod.before_request(login_required(lambda: None))


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

    last_poke = None
    if current_user != user:
        last_poke = current_user.get_last_poke(user)

    return flask.render_template(
        'show_profile.html',
        user=user,
        transactions=transactions,
        change_nickname_form=change_nickname_form,
        profile_picture_form=upload_profile_picture_form,
        change_profile_picture_form=change_profile_picture_form,
        credit_transfer_form=credit_transfer_form,
        admin_transaction_form=admin_transaction_form,
        last_poke=last_poke
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
            flask.url_for('profile.user_nicknames', user_id=user_id)
        )

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.redirect(
        flask.url_for('profile.show_profile', user_id=user_id)
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
                flask.url_for('profile.show_profile', user_id=user_id)
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
        flask.url_for('profile.show_profile', user_id=user_id)
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
        flask.url_for('profile.show_profile', user_id=user_id)
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
        flask.url_for('profile.show_profile', user_id=user_id)
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


@mod.route('/profile/<int:user_id>/poke', methods=['POST'])
def poke_user(user_id):
    if current_user.id == user_id:
        flask.flash(_l("Du kan inte puffa dig själv, det är oanständigt."), 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    user = models.User.query.get_or_404(user_id)

    poke = user.poke(current_user)
    if not poke:
        flask.flash(
            _l("Du har redan puffat denna användare, du måste få en puff tillbaka först."),
            'error'
        )
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    poke.create_notification()
    flask.flash(_l("Puffad!"), 'success')
    return flask.redirect(flask.url_for('.show_profile', user_id=user_id))


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
        return flask.redirect(flask.url_for('profile.show_profile',
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
            if not current_user.is_admin:
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
        return flask.redirect(flask.url_for('profile.api_keys',
                                            user_id=user.id))

    return flask.render_template('edit_api_key.html',
                                 form=form,
                                 user=user,
                                 api_key=api_key,
                                 can_be_deleted=can_be_deleted)


@mod.route('/profile/<int:user_id>/edit/api-keys/delete/<int:api_key_id>', methods=['POST'])
def delete_api_key(user_id, api_key_id):
    api_key = models.ApiKey.query.get_or_404(api_key_id)

    if current_user.id != user_id and not current_user.is_admin:
        abort(403)

    if api_key.user.id != user_id:
        abort(404)

    if not api_key.can_be_deleted:
        abort(400)

    models.db.session.delete(api_key)
    models.db.session.commit()

    flask.flash(_l("Api-nyckeln \"%(name)s\" är borttagen.", name=api_key.name), 'success')
    return flask.redirect(flask.url_for('profile.api_keys', user_id=user_id))


@mod.route('/profile/<int:user_id>/edit/password', methods=['GET', 'POST'])
def change_email_or_password(user_id):
    user = models.User.query.get_or_404(user_id)

    if current_user.id != user.id and not current_user.is_admin:
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

        return flask.redirect(flask.url_for('profile.show_profile',
                                            user_id=user.id))

    return flask.render_template('change_email_or_password.html',
                                 form=form,
                                 user=user)

