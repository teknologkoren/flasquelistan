import flask
import flask_login

mod = flask.Blueprint('more', __name__)


@mod.before_request
@flask_login.login_required
def before_request():
    """Make sure user is logged in before request.
    This function does nothing, but the decorators do.
    """
    pass


@mod.route('/more')
def index():
    return flask.render_template('more.html')
