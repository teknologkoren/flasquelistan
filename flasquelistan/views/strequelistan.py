import flask
import flask_login
from sqlalchemy.sql.expression import func, not_
from flasquelistan import forms, models, util
from flasquelistan.views import auth
from flask import request
mod = flask.Blueprint('strequelistan', __name__)


@mod.before_request
@flask_login.login_required
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
              .all())

    random_quote = models.Quote.query.order_by(func.random()).first()

    current_user = flask_login.current_user

    articles = (models.Article
                .query
                .order_by(models.Article.weight.desc())
                .all()
                )

    if current_user.balance <= 0:
        flask.flash("Det finns inga pengar på kontot. Dags att fylla på!",
                    'error')
    elif current_user.balance < 10000:
        flask.flash("Det är ont om pengar på kontot. Dags att fylla på?",
                    'warning')

    return flask.render_template('strequelistan.html', groups=groups,
                                 quote=random_quote, articles=articles)


@mod.route('/strequa', methods=['POST'])
def add_streque():
   if request.is_json:
        form = forms.StrequaForm()

    form = forms.StrequaForm()
    if form.validate_on_submit():
        user = models.User.query.get(form.user_id.data)
        article = models.Article.query.get(form.article_id.data)
        streque = user.strequa(article)

        flask.flash("{}-streque på {} tillagt.".format(
            streque.text,
            user.full_name
        ), 'success')
    else:
        forms.flash_errors(form)


    return flask.redirect(flask.url_for('strequelistan.index'))

    #if flask.request.is_json:
    #    data = flask.request.get_json()
    #else:
    #    data = flask.request.args


    #if flask.request.is_json:
    #    return flask.jsonify(
    #        user_id=user.id,
    #        value=streque.value,
    #        balance=user.balance
    #    )

    #else:
    #    flask.flash("{}-streque på {} tillagt.".format(streque.text,
    #                                                   user.full_name),
    #                'success')
    #    return flask.redirect(flask.url_for('strequelistan.index'))


@mod.route('/void', methods=['POST'])
def void_streque():
    if flask.request.is_json:
        data = flask.request.get_json()
    else:
        data = flask.request.args

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
        flask.flash("Ångrade {}-streque på {}.".format(streque.text,
                                                       streque.user.full_name),
                    'success')
        return flask.redirect(flask.url_for('strequelistan.history'))


@mod.route('/articles')
def article_description():
    articles = (models.Article
                .query
                .order_by(models.Article.weight.desc())
                .all()
                )
    return flask.render_template('article_description.html', articles=articles)


@mod.route('/paperlist')
def paperlist():
    users = (models.User.query
             .order_by(models.User.first_name))

    groups = models.Group.query.all()

    articles = (models.Article
                .query
                .order_by(models.Article.weight.desc())
                .all()
                )

    return flask.render_template('paperlist.html',
                                 users=users,
                                 groups=groups,
                                 articles=articles)


@mod.route('/history')
def history():
    streques = (models.Streque.query
                .filter(not_(models.Streque.too_old()),
                        models.Streque.voided.is_(False))
                .order_by(models.Streque.timestamp.desc())
                .all())

    return flask.render_template('history.html', streques=streques)


@mod.route('/profile/<int:user_id>/', methods=['GET', 'POST'])
def show_profile(user_id):
    user = models.User.query.get_or_404(user_id)

    transactions = (user.transactions
                    .filter(models.Streque.voided.is_(False))
                    .order_by(models.Transaction.timestamp.desc())
                    .limit(10))

    profile_picture_form = forms.UploadProfilePictureForm()

    if profile_picture_form.validate_on_submit():
        if profile_picture_form.upload.data:
            filename = util.profile_pictures.save(
                profile_picture_form.upload.data
            )
            profile_picture = models.ProfilePicture(
                filename=filename,
                user_id=user.id
            )

            user.profile_picture = profile_picture

            models.db.session.add(profile_picture)
            models.db.session.commit()

            flask.flash("Profilbilden har ändrats!", 'success')

    elif profile_picture_form.is_submitted():
        forms.flash_errors(profile_picture_form)

    return flask.render_template('show_profile.html',
                                 user=user,
                                 transactions=transactions,
                                 profile_picture_form=profile_picture_form)


@mod.route('/profile/<int:user_id>/history')
def user_history(user_id):
    user = models.User.query.get_or_404(user_id)
    current_user = flask_login.current_user

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
    current_user = flask_login.current_user

    if current_user.id != user.id and not current_user.is_admin:
        flask.flash("Du får bara redigera din egen profil! ಠ_ಠ", 'error')
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

        flask.flash("Ändringarna har sparats!", 'success')
        return flask.redirect(flask.url_for('strequelistan.show_profile',
                                            user_id=user.id))
    elif form.is_submitted():
        forms.flash_errors(form)

    else:
        if user.y_chromosome is True:
            form.y_chromosome.data = 'yes'
        elif user.y_chromosome is False:
            form.y_chromosome.data = 'no'
        else:
            form.y_chromosome.data = 'n/a'

    return flask.render_template('edit_profile.html', form=form, user=user)


@mod.route('/profile/<int:user_id>/edit/profile-picture',
           methods=['GET', 'POST'])
def change_profile_picture(user_id):
    user = models.User.query.get_or_404(user_id)
    current_user = flask_login.current_user

    if current_user.id != user.id and not current_user.is_admin:
        flask.flash("Du får bara redigera din egen profil! ಠ_ಠ", 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    form = forms.ChangeProfilePictureFormFactory(user)

    if form.validate_on_submit():
        # The "none" choice seems to work. Not sure why.
        user.profile_picture_id = form.profile_picture.data
        models.db.session.commit()

        flask.flash("Din profilbild har ändrats!", 'success')

        return flask.redirect(flask.url_for('strequelistan.edit_profile',
                                            user_id=user.id))

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.render_template('change_profile_picture.html', form=form,
                                 user=user)


@mod.route('/profile/<int:user_id>/edit/profile-picture/upload',
           methods=['GET', 'POST'])
def upload_profile_picture(user_id):
    user = models.User.query.get_or_404(user_id)
    current_user = flask_login.current_user

    if current_user.id != user.id and not current_user.is_admin:
        flask.flash("Du får bara redigera din egen profil! ಠ_ಠ", 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    form = forms.UploadProfilePictureForm()

    if form.validate_on_submit():
        if form.upload.data:
            filename = util.profile_pictures.save(form.upload.data)
            profile_picture = models.ProfilePicture(filename=filename,
                                                    user_id=user.id)
            models.db.session.add(profile_picture)
            models.db.session.commit()

            flask.flash("Din nya profilbild har laddats upp!", 'success')

        return flask.redirect(
            flask.url_for('strequelistan.change_profile_picture',
                          user_id=user.id)
        )

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.render_template('upload_profile_picture.html', form=form,
                                 user=user)


@mod.route('/profile/<int:user_id>/edit/password', methods=['GET', 'POST'])
def change_email_or_password(user_id):
    user = models.User.query.get_or_404(user_id)
    current_user = flask_login.current_user

    if current_user.id != user.id:
        if current_user.is_admin:
            form = forms.ChangeEmailOrPasswordForm(obj=user, user=user,
                                                   nopasswordvalidation=True)

        else:
            flask.flash("Du får bara redigera din egen profil! ಠ_ಠ", 'error')
            return flask.redirect(flask.url_for('.show_profile',
                                                user_id=user_id))

    else:
        form = forms.ChangeEmailOrPasswordForm(obj=user, user=user)

    if form.validate_on_submit():
        if form.email.data != user.email:
            auth.verify_email(user, form.email.data)
            flask.flash(("En länk för att verifiera e-postadressen har "
                         "skickats till {}.").format(form.email.data), 'info')

        if form.new_password.data:
            user.password = form.new_password.data
            flask.flash("Lösenordet har ändrats!", 'success')

        models.db.session.commit()

        return flask.redirect(flask.url_for('strequelistan.show_profile',
                                            user_id=user.id))
    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.render_template('change_email_or_password.html',
                                 form=form, user=user)
