import flask
from sqlalchemy.sql.expression import not_
from flasquelistan import models, forms

mod = flask.Blueprint('strequelistan', __name__)


@mod.route('/')
def index():
    users = models.User.query.all()
    return flask.render_template('strequelistan.html', users=users)


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


@mod.route('/historik')
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


@mod.route('/profil/<int:user_id>')
def show_profile(user_id):
    user = models.User.query.get_or_404(user_id)

    return flask.render_template('show_profile.html', user=user)
