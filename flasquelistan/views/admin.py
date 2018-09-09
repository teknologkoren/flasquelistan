import flask
import flask_login
from flasquelistan import models, forms
from flasquelistan.views import auth

mod = flask.Blueprint('admin', __name__)


@mod.before_request
@flask_login.login_required
@auth.admin_required
def before_request():
    """Make sure user is logged in before request.
    This function does nothing, but the decorators do.
    """
    pass


@mod.route('/admin/')
def index():
    return flask.render_template('admin.html')
