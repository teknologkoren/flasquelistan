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
from flasquelistan.views import auth
import json
from sqlalchemy.sql import exists


from pprint import pprint

mod = flask.Blueprint('strequeapi', __name__)

def check_auth(email, secret):
    """This function is called to check if a username /
    password combination is valid.
    """
    return User.query.filter(
            User.email == email
        ).filter(
            User.api_secret == secret
        ).count()

def check_admin_auth(email, secret):
    """This function is called to check if a username /
    password combination is valid.
    """
    return User.query.filter(
            User.email == email
        ).filter(
            User.api_secret == secret
        ).filter(
            User.is_admin == True
        ).count()

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def requires_admin_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_admin_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@mod.route('/api/transactions/', methods=['GET'])
@requires_auth
def transactions():
    return "asd"

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
    pprint(quotes)
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
