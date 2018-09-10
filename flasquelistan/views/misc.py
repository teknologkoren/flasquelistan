import flask
import flask_login
from flasquelistan.views import auth

mod = flask.Blueprint('misc', __name__)


@mod.before_request
@flask_login.login_required
def before_request():
    """Make sure user is logged in before request.
    This function does nothing, but the decorators do.
    """
    pass


@mod.route('/mer/')
def index():
    return flask.render_template('misc.html')
