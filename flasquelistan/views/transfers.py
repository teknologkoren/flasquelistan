import flask
import flask_babel
from flask import request
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required

from flasquelistan import forms, models, util

mod = flask.Blueprint('transfers', __name__)
mod.before_request(login_required(lambda: None))


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
        flask.url_for('profile.show_profile', user_id=payee.id)
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
        util.emit_notification_event(payee_notification)

    elif form.is_submitted():
        forms.flash_errors(form)

    return redir


@mod.route('/transfer-generate-link', methods=['POST'])
def credit_transfer_generate_link():
    form = forms.CreditTransferForm()

    payee = (models.User
             .query
             .filter_by(id=form.payee_id.data)
             .first()
             )

    if not (payee):
        flask.abort(400)

    redir = flask.redirect(
        flask.url_for('profile.show_profile', user_id=payee.id)
    )

    if form.validate_on_submit():
        args = {'value': form.value.data}
        if form.value.data:
            args['value'] = form.value.data
        message = form.message.data.strip()
        if message:
            args['message'] = message
        generated_url = flask.url_for('transfers.transfer_standalone', user_id=payee.id, _external=True, **args)

        flask.flash(
            _('Streque Pay-länk skapad: <a href="%(href)s">%(href)s',
              href=generated_url),
            'success'
        )
    elif form.is_submitted():
        forms.flash_errors(form)

    return redir


@mod.route('/profile/<int:user_id>/pay')
def transfer_standalone(user_id):
    user = models.User.query.get_or_404(user_id)

    credit_transfer_form = forms.CreditTransferForm()
    credit_transfer_form.payer_id.data = current_user.id
    credit_transfer_form.payee_id.data = user.id

    # Pre-fill credit transfer form if query parameters are set
    try:
        credit_transfer_form.value.data = request.args.get("value", None, float)
    except ValueError:
        # If the value param was not a valid float, ignore it.
        pass
    credit_transfer_form.message.data = request.args.get("message", None)

    return flask.render_template(
        'transfer_standalone.html',
        user=user,
        credit_transfer_form=credit_transfer_form,
    )


@mod.route('/profile/<int:user_id>/admin-transaction', methods=['POST'])
def admin_transaction(user_id):
    if not current_user.is_admin:
        flask.flash(_l("Du måste vara admin för att göra det!"), 'error')
        return flask.redirect(flask.url_for('profile.show_profile', user_id=user_id))

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
        flask.url_for('profile.show_profile', user_id=user_id)
    )
