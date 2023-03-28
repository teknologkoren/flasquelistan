# Streque API
#
# To require login for an endpoint (should be required by most/all endpoints),
# decorate the function with:
#     @auth.login_required
#
# To require admin permissions to use an endpoint, decorate the function with:
#     @auth.login_required(role='admin')
#
# To authenticate, use the following HTTP header for your requests:
#     Authorization: Bearer <your_api_key>
#
# To perform a simple test of the API, make a GET request to:
#     <URL to flasquelistan>/api/v1/users/me
#

import flask
from flask import jsonify, request
from flask_babel import lazy_gettext as _l
from flask_httpauth import HTTPTokenAuth
from sqlalchemy import desc, func

from flasquelistan import forms, models, util
from flasquelistan.models import ApiKey, Article, Transaction, User, Quote

mod = flask.Blueprint('api', __name__, url_prefix='/api/v1')
auth = HTTPTokenAuth(scheme='Bearer')

# We are using the ApiKey as "user" for the authentication library, because
# we need information about which key was used to authenticate, not just which
# user owns it. Let's define some functions to make this less confusing.
current_api_key = lambda: auth.current_user()
current_user = lambda: current_api_key().user


@auth.verify_token
def verify_token(token):
    return ApiKey.authenticate(token)


@auth.get_user_roles
def get_api_key_roles(api_key):
    return ['admin'] if api_key.is_admin else []


@mod.route('/articles', methods=['GET'])
@auth.login_required
def get_active_articles():
    articles = (Article
                .query
                .filter_by(is_active=True)
                .order_by(Article.weight.desc())
                .all())
    response = []
    for article in articles:
        response.append(article.api_dict)
    return jsonify(response)


def filter_user_data(user_dict):
    """Return the entire user data dict if the api key has valid admin
    privileges, otherwise return a subset of keys they are allowed to see."""
    if current_api_key().is_admin:
        return user_dict
    else:
        allowed = ('id', 'email', 'first_name', 'last_name', 'full_name',
                  'nickname', 'birthday', 'active', 'lang', 'group', 'phone',
                  'profile_picture', 'discord_user_id', 'discord_username')
        return {k: v for (k, v) in user_dict.items() if k in allowed}


@mod.route('/users/me', methods=['GET'])
@auth.login_required
def get_user_me():
    return get_user(current_user().id)


@mod.route('/users/<int:user_id>', methods=['GET'])
@auth.login_required
def get_user(user_id):
    return filter_user_data(User.query.get_or_404(user_id).api_dict)


@mod.route('/users/by-phone/<string:phone_number>', methods=['GET'])
@auth.login_required
def get_user_by_phone(phone_number):
    user = User.query.filter_by(
        phone=util.format_phone_number(phone_number, e164=True)).first_or_404()
    return filter_user_data(user.api_dict)


@mod.route('/users/by-discord/<string:discord_user_id>', methods=['GET'])
@auth.login_required
def get_user_by_discord(discord_user_id):
    user = User.query.filter_by(
        discord_user_id=discord_user_id).first_or_404()
    return filter_user_data(user.api_dict)


@mod.route('/users/me/streque/<int:article_id>', methods=['POST'])
@auth.login_required
def add_streque_me(article_id):
    return add_streque(current_user().id, article_id)


@mod.route('/users/<int:user_id>/streque/<int:article_id>', methods=['POST'])
@auth.login_required
def add_streque(user_id, article_id):
    user = User.query.get_or_404(user_id)
    article = Article.query.get_or_404(article_id)
    return user.strequa(article, current_user(), current_api_key()).api_dict


@mod.route('/users/me/transactions', methods=['GET'])
@auth.login_required
def get_transactions_me():
    return get_transactions_user(current_user().id)


@mod.route('/users/<int:user_id>/transactions', methods=['GET'])
@auth.login_required
def get_transactions_user(user_id):
    if not current_api_key().is_admin and current_user().id != user_id:
        flask.abort(403) # HTTP 403 Forbidden

    user = User.query.get_or_404(user_id)
    min_id = request.args.get('min_id', 0)
    limit = request.args.get('limit', None)
    order = request.args.get('order', "asc")

    return query_transactions(user=user, min_id=min_id, limit=limit, order=order)


@mod.route('/transactions', methods=['GET'])
@auth.login_required
def get_transactions():
    min_id = request.args.get('min_id', 0)
    limit = request.args.get('limit', None)
    order = request.args.get('order', "asc")

    return query_transactions(min_id=min_id, limit=limit, order=order)


def query_transactions(user=None, min_id=0, limit=None, order="asc"):
    if not current_api_key().is_admin:
        flask.abort(403) # HTTP 403 Forbidden

    q = Transaction.query
    if user is not None:
        q = q.filter(Transaction.user_id == user.id)
    if min_id > 0:
        q = q.filter(Transaction.id >= min_id)
    if order == "desc":
        q = q.order_by(desc(Transaction.id))
    else:
        q = q.order_by(Transaction.id)
    if limit is not None:
        q = q.limit(limit)
    transactions = q.all()

    return jsonify([t.api_dict for t in transactions])


@mod.route('/quotes/random', methods=['GET'])
@auth.login_required
def get_random_quote():
    quote = models.Quote.query.order_by(func.random()).first()
    return jsonify(quote.api_dict)


@mod.route('/quotes/<int:quote_id>', methods=['GET'])
@auth.login_required
def get_quote(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    return jsonify(quote.api_dict)
