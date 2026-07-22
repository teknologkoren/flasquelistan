import click
from flask import Blueprint

from . import import_nickname_changes, normalize_phone_numbers

mod = Blueprint('scripts', __name__)


@mod.cli.command('normalize_phone_numbers')
def normalize_phone_numbers_command():
    normalize_phone_numbers.run()


@mod.cli.command('import_nickname_changes')
@click.argument('path')
def import_nickname_changes_command(path):
    import_nickname_changes.run(path)
