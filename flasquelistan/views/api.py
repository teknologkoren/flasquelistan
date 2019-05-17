from functools import wraps
import datetime
import flask
from flask import Response
from flask import request
from flask import jsonify
from flask_wtf.csrf import CSRFProtect
import sqlalchemy as sqla
from flasquelistan import models, forms, util
from flasquelistan.models import User
from flasquelistan.models import Transaction
from flasquelistan.models import Quote
from flasquelistan.views import auth
import json
from sqlalchemy.sql import exists
from sqlalchemy.sql.expression import func
from flask_login import login_user
from flask_login import current_user

from pprint import pprint

mod = flask.Blueprint('strequeapi', __name__)

def check_auth(email, secret):
    """This function is called to check if a username /
    password combination is valid.
    """
    user = User.query.filter(
            User.email == email
        ).filter(
            User.api_secret == secret
        ).first()
    if user:
        login_user(user)
        return True
    else:
        return False

def check_admin_auth(email, secret):
    """This function is called to check if a username /
    password combination is valid.
    """
    user = User.query.filter(
            User.email == email
        ).filter(
            User.api_secret == secret
        ).filter(
            User.is_admin == True
        ).first()
    if user:
        login_user(user)
        return True
    else:
        return False

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.is_authenticated:
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def requires_admin_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.is_authenticated:
            if current_user.is_admin:
                return f(*args, **kwargs)
        auth = request.authorization
        if not auth or not check_admin_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@mod.route('/api/latest_streque/', methods=['GET'])
@requires_auth
def latest_streque():
    then = datetime.datetime.utcnow() - datetime.timedelta(minutes=15)
    streque = Transaction.query.filter(
            Transaction.type == "streque",
        ).filter(
            Transaction.timestamp >= then
        ).filter(
            Transaction.voided == False
        )
    data = []
    for s in streque:
        data.append(s.json)
    return jsonify(data)

@mod.route('/api/transactions/', methods=['POST'])
@requires_admin_auth
def add_transaction():
    form = forms.AdminTransactionForm(request.form, csrf_enabled=False)
    if form.validate():
        user = User.query.get(form.user_id.data)
        transaction = user.admin_transaction(form.value.data, form.text.data)
        return jsonify(transaction.json)

    else:
        return jsonify({'success': 'False', 'error': form.errors})


@mod.route('/api/transactions/<int:transaction_id>', methods=['GET'])
@requires_auth
def single_transaction(transaction_id):
    transaction = models.Transaction.query.get(transaction_id)
    if transaction:
        if current_user.is_admin or current_user.id == transaction.user_id:
            return jsonify(transaction.json)
    return "not found" 

@mod.route('/api/return-transaction/', methods=['POST'])
@requires_admin_auth
def return_transaction():
    transaction = models.Transaction.query.get_or_404(request.form.transaction_id)
    transaction.void_and_refund()
    return jsonify(transaction.json)

@mod.route('/api/transactions/', methods=['GET'])
@requires_admin_auth
def list_transactions():
    page = request.args.get("page", "1")
    limit = request.args.get("limit", "50")
    try:
        page = int(page)
    except:
        return "invalid value for page '{}', needs to be an integer".format(request.args.get("page"))

    try:
        limit = int(limit)
    except:
        return "invalid value for limit '{}', needs to be an integer".format(request.args.get("page"))

    objects = models.Transaction.query.order_by(models.Transaction.timestamp.desc()).paginate(per_page=limit)
    data = {}

    data["current_page"] = page
    data["limit"] = limit

    if objects.has_next:
        data["next_page"] = objects.next_num

    if objects.has_prev:
        data["prev"] = objects.prev_num

    data["data"] = []
    for item in objects.items:
        data["data"].append(item.json)

    return jsonify(data)

@mod.route('/api/strequa', methods=['POST'])
@requires_auth
def add_streque():
    form = forms.StrequaForm(request.form, csrf_enabled=False)
    if form.validate():
        user = models.User.query.get(form.user_id.data)
        article = models.Article.query.get(form.article_id.data)
        streque = user.strequa(article)
        return jsonify(streque.json)
    else:
        return "Failed"

@mod.route('/api/quotes/', methods=['POST'])
@requires_auth
def add_quote():
    form = forms.QuoteForm(request.form, csrf_enabled=False)

    if form.validate():
        quote = models.Quote(text=form.text.data, who=form.who.data)
        models.db.session.add(quote)
        models.db.session.commit()
        return jsonify(quote.json)

    else:
        return jsonify({'success': 'False', 'error': form.errors})

@mod.route('/api/quotes/', methods=['GET'])
@requires_auth
def quotes():
    page = request.args.get("page", "1")
    limit = request.args.get("limit", "50")

    try:
        page = int(page)
    except:
        return "invalid value for page '{}', needs to be an integer".format(request.args.get("page"))

    try:
        limit = int(limit)
    except:
        return "invalid value for limit '{}', needs to be an integer".format(request.args.get("page"))

    quotes = models.Quote.query.order_by(models.Quote.timestamp.desc()).paginate(per_page=limit)
    data = {}

    data["current_page"] = page
    data["limit"] = limit

    if quotes.has_next:
        data["next_page"] = quotes.next_num

    if quotes.has_prev:
        data["prev"] = quotes.prev_num

    data["data"] = []
    for item in quotes.items:
        data["data"].append(item.json)

    return jsonify(data)

@mod.route('/api/quotes/<int:quote_id>', methods=['GET'])
@requires_auth
def single_quote(quote_id):
    quote = models.Quote.query.get_or_404(quote_id)
    return jsonify(quote.json)

@mod.route('/api/random-quote/', methods=['GET'])
@requires_auth
def random_quote():
    return jsonify(models.Quote.query.order_by(func.random()).first().json)


@mod.route('/api/quotes/<int:quote_id>', methods=['DELETE'])
@requires_admin_auth
def delete_qoute(quote_id):
    quote = models.Quote.query.get_or_404(quote_id)
    models.db.session.delete(quote)
    models.db.session.commit()
    return ""

@mod.route('/api/users/<int:user_id>', methods=['GET'])
@requires_auth
def single_user(user_id):
    user = models.User.query.get_or_404(user_id)
    if user.id == current_user.id or current_user.is_admin:
        data = user.json
    else: # Limit the available data for other users
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'nickname',
            'phone',
            'formatted_phone',
            'active',
            'group',
            'profile_picture',
            'bac'
        ]
        data = {}
        for field in fields:
            if field in current_user.json:
                data[field] = user.json[field]

    return jsonify(data)

@mod.route('/api/vcard/<int:user_id>', methods=['GET'])
@requires_auth
def get_vcard(user_id):
    user = models.User.query.get_or_404(user_id)
    return user.vcard

@mod.route('/api/groups/', methods=['POST'])
@requires_admin_auth
def add_group():
    form = forms.AddGroupForm(request.form, csrf_enabled=False)
    if form.validate():
        group = models.Group(name=form.name.data, weight=form.weight.data)
        models.db.session.add(group)
        models.db.session.commit()
        return jsonify(group.json)
    else:
        return jsonify({'success': 'False', 'error': form.errors})

@mod.route('/api/groups/', methods=['GET'])
@requires_auth
def groups():
    page = request.args.get("page", "1")
    limit = request.args.get("limit", "50")

    try:
        page = int(page)
    except:
        return "invalid value for page '{}', needs to be an integer".format(request.args.get("page"))

    try:
        limit = int(limit)
    except:
        return "invalid value for limit '{}', needs to be an integer".format(request.args.get("page"))

    groups = models.Group.query.paginate(per_page=limit)
    data = {}

    data["current_page"] = page
    data["limit"] = limit

    if groups.has_next:
        data["next_page"] = groups.next_num

    if groups.has_prev:
        data["prev"] = groups.prev_num

    data["data"] = []
    for item in groups.items:
        data["data"].append(item.json)

    return jsonify(data)

@mod.route('/api/groups/<int:group_id>', methods=['GET'])
@requires_auth
def single_group(group_id):
    group = models.Group.query.get_or_404(group_id)
    return jsonify(group.json)

@mod.route('/api/groups/<int:group_id>', methods=['DELETE'])
@requires_admin_auth
def delete_group(group_id):
    group = models.Group.query.get_or_404(group_id)
    models.db.session.delete(group)
    models.db.session.commit()
    return ""

@mod.route('/api/articles/', methods=['POST'])
@requires_admin_auth
def add_article():
    form = forms.AddArticleForm(request.form, csrf_enabled=False)
    if form.validate():
        article = models.Article(
            name=form.name.data,
            weight=form.weight.data,
            description=form.description.data,
            standardglas=form.standardglas.data,
            value=int(form.value.data*100) # Fix kronor till ören
        )
        models.db.session.add(article)
        models.db.session.commit()
        return jsonify(article.json)
    else:
        return jsonify({'success': 'False', 'error': form.errors})

@mod.route('/api/articles/', methods=['GET'])
@requires_auth
def articles():
    page = request.args.get("page", "1")
    limit = request.args.get("limit", "50")

    try:
        page = int(page)
    except:
        return "invalid value for page '{}', needs to be an integer".format(request.args.get("page"))

    try:
        limit = int(limit)
    except:
        return "invalid value for limit '{}', needs to be an integer".format(request.args.get("page"))

    articles = models.Article.query.paginate(per_page=limit)
    data = {}

    data["current_page"] = page
    data["limit"] = limit

    if articles.has_next:
        data["next_page"] = articles.next_num

    if articles.has_prev:
        data["prev"] = articles.prev_num

    data["data"] = []
    for item in articles.items:
        data["data"].append(item.json)

    return jsonify(data)

@mod.route('/api/articles/<int:article_id>', methods=['GET'])
@requires_auth
def single_article(article_id):
    article = models.Article.query.get_or_404(article_id)
    return jsonify(article.json)

@mod.route('/api/articles/<int:article_id>', methods=['DELETE'])
@requires_admin_auth
def delete_article(article_id):
    article = models.Article.query.get_or_404(article_id)
    models.db.session.delete(article)
    models.db.session.commit()
    return ""
