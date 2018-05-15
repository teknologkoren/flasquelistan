import flask
import flask_login
from sqlalchemy.sql.expression import func, not_
from flasquelistan import forms, models
from flasquelistan.views import auth

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
    groups = models.Group.query.filter(models.Group.users.any())\
                .order_by(models.Group.weight).all()  # Only groups with users

    random_quote = models.Quote.query.order_by(func.random()).first()

    return flask.render_template('strequelistan.html', groups=groups,
                                 quote=random_quote)


@mod.route('/strequa', methods=['POST'])
def add_streque():
    data = flask.request.get_json()
    try:
        user = models.User.query.get(data['user_id'])
        amount = int(data['amount'])
    except (KeyError, ValueError):
        flask.abort(400)

    if user and 1 <= amount <= 4:
        transaction = user.strequa(amount)
    else:
        flask.abort(400)

    return flask.jsonify(
        user_id=user.id,
        amount=amount,
        sum=transaction.sum,
        balance=user.balance
    )


@mod.route('/history')
def history():
    transactions = models.Transaction.query\
        .filter(not_(models.Transaction.too_old()))\
        .order_by(models.Transaction.timestamp.desc())\
        .all()

    return flask.render_template('history.html', transactions=transactions)


@mod.route('/void', methods=['POST'])
def void_transaction():
    data = flask.request.get_json()
    try:
        transaction_id = data['transaction_id']
    except (KeyError, ValueError):
        flask.abort(400)

    transaction = models.Transaction.query.get(transaction_id)

    if not transaction:
        flask.abort(400)

    if transaction.too_old():
        flask.abort(400)

    user = transaction.user
    amount = transaction.amount
    sum = transaction.void_and_refund()

    return flask.jsonify(
        transaction_id=transaction_id,
        user_id=user.id,
        amount=amount,
        sum=sum,
        balance=user.balance
    )


@mod.route('/profile/<int:user_id>/')
def show_profile(user_id):
    user = models.User.query.get_or_404(user_id)

    return flask.render_template('show_profile.html', user=user)


@mod.route('/profile/<int:user_id>/edit/', methods=['GET', 'POST'])
def edit_profile(user_id):
    user = models.User.query.get_or_404(user_id)
    current_user = flask_login.current_user

    if current_user.id != user.id and not current_user.is_admin:
        flask.flash("Du får bara redigera din egen profil! ಠ_ಠ", 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

    if current_user.is_admin:
        form = forms.FullEditUserForm(obj=user, user=user)
    else:
        form = forms.EditUserForm(obj=user, user=user)

    if form.validate_on_submit():
        if isinstance(form, forms.FullEditUserForm):
            user.first_name = form.first_name.data
            user.last_name = form.last_name.data

        user.nickname = form.nickname.data
        user.phone = form.phone.data

        models.db.session.commit()

        flask.flash("Ändringarna har sparats!", 'success')
        return flask.redirect(flask.url_for('strequelistan.show_profile',
                                            user_id=user.id))
    else:
        forms.flash_errors(form)

    return flask.render_template('edit_profile.html', form=form, user=user)


@mod.route('/profile/<int:user_id>/edit/password', methods=['GET', 'POST'])
def change_email_or_password(user_id):
    user = models.User.query.get_or_404(user_id)
    current_user = flask_login.current_user

    if current_user.id != user.id and not current_user.is_admin:
        flask.flash("Du får bara redigera din egen profil! ಠ_ಠ", 'error')
        return flask.redirect(flask.url_for('.show_profile', user_id=user_id))

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
