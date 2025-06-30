from flask import Blueprint, send_from_directory
from flask_login import login_required

songbook = Blueprint('songbook', __name__)

@songbook.route('/bok/')
@login_required
def index():
    return send_from_directory('songbook_dist', 'index.html')

@songbook.route('/bok/<path:path>')
@login_required
def assets(path):
    return send_from_directory('songbook_dist', path)
