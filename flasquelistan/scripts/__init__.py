from flask import Blueprint

from . import normalize_phone_numbers

mod = Blueprint('scripts', __name__)


@mod.cli.command('normalize_phone_numbers')
def normalize_phone_numbers_command():
    normalize_phone_numbers.run()
