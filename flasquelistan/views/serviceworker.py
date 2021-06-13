import flask

mod = flask.Blueprint('serviceworker', __name__)

@mod.route('/sw.js')
def serviceworker():
    response = flask.send_from_directory('static', path='js/serviceworker.js')
    response.headers['Cache-Control'] = 'no-cache'
    return response
