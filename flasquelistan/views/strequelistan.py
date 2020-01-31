import os
import datetime
import flask
from flask_login import current_user, login_required
from sqlalchemy.sql.expression import func, not_
from flasquelistan import forms, models, util
from flasquelistan.views import auth
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
mod = flask.Blueprint('strequelistan', __name__)


@mod.before_request
@login_required
def before_request():
    """Make sure user is logged in before request.
    This function does nothing, but the decorators do.
    """
    pass


@mod.route('/')
def index():
    groups = (models.Group
              .query
              .filter(models.Group.users.any())  # Only groups with users
              .order_by(models.Group.weight.desc())
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

    random_quote = models.Quote.query.order_by(func.random()).first()

    articles = (models.Article
                .query
                .filter_by(is_active=True)
                .order_by(models.Article.weight.desc())
                .all()
                )

    if current_user.balance <= 0:
        flask.flash(_l("Det finns inga pengar på kontot. Dags att fylla på!"),
                    'error')
    elif current_user.balance < 10000:
        flask.flash(_l("Det är ont om pengar på kontot. Dags att fylla på?"),
                    'warning')


    return flask.render_template(
        'strequelistan.html',
        groups=groups,
        quote=random_quote,
        articles=articles,
        users_with_streques=users_with_streques
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
                _l("Du kan bara föra över pengar från dig själv! >:("), 'error'
            )
            return redir

        value = int(form.value.data*100)  # To ören

        message = form.message.data
        models.CreditTransfer.create(
            payer, payee, current_user, value, message
        )

        flask.flash(_("Förde över %(a)i pengar till %(name)s",
                      a=value/100, name=payee.full_name),
                    'success'
                    )

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
    image_query = (models.ProfilePicture
            .query
            .order_by(models.ProfilePicture.timestamp.desc())
            .paginate(
                page=page,
                per_page=20,
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

    image_query = (models.ProfilePicture
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
        profile_picture_form=upload_profile_picture_form,
        change_profile_picture_form=change_profile_picture_form,
        credit_transfer_form=credit_transfer_form,
        admin_transaction_form=admin_transaction_form
    )


@mod.route('/profile/<int:user_id>/admin-transaction', methods=['POST'])
def admin_transaction(user_id):
    if not current_user.is_admin:
        flask.flash(_l("Du måste vara admin för att göra det!"), 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    user = models.User.query.get_or_404(user_id)
    form = forms.UserTransactionForm()

    if form.validate_on_submit():
        user.admin_transaction(
            int(form.value.data*100),
            form.text.data,
            by_user=current_user
        )
        flask.flash(_l("Transaktion utförd!"), 'success')

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

        filename = util.profile_pictures.save(form.upload.data)

        if os.path.splitext(filename)[1].lower() in ('.jpg', '.jpeg'):
            util.rotate_jpeg(util.profile_pictures.path(filename))

        profile_picture = models.ProfilePicture(
            filename=filename,
            user_id=user.id
        )

        user.profile_picture = profile_picture

        models.db.session.add(profile_picture)
        models.db.session.commit()

        flask.flash(_l("Din profilbild har ändrats!"), 'success')

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
            # The "none" choice seems to work. Not sure why.
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
        if isinstance(form, forms.FullEditUserForm):
            user.first_name = form.first_name.data
            user.last_name = form.last_name.data
            user.active = form.active.data
            user.group_id = form.group_id.data if (form.group_id.data
                                                   != -1) else None

        user.nickname = form.nickname.data
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
