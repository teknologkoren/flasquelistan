import click
import sys

from flasquelistan import models
from flasquelistan.util import format_phone_number


def run():
    """Go through all users and update all phone numbers to be in the
    E.164 phone number format. Please make sure to backup the database
    before running this script."""

    if not click.confirm("Have you taken a backup of the database?"):
        click.echo("Please backup the database before running this script.")
        sys.exit(1)

    with models.db.session.begin():
        for user in models.User.query.all():
            current = user.phone

            if not current:
                click.echo(
                    f"'{user.first_name} {user.last_name}' has no phone number.")
                continue

            normalized = format_phone_number(current, e164=True)
            if not normalized:
                click.echo(
                    "Was not able to normalize the phone number of "
                    f"'{user.first_name} {user.last_name}': '{current}'")
            elif current == normalized:
                click.echo(
                    f"'{user.first_name} {user.last_name}' already has a "
                    f"normalized phone number: '{user.phone}'")
            else:
                click.echo(
                    f"Normalizing phone number of '{user.first_name} "
                    f"{user.last_name}': "
                    f"old: '{user.phone}', new: '{normalized}'.")
                user.phone = normalized

        if len(models.db.session.dirty) == 0:
            click.echo("No changes to the database were performed.")
        elif click.confirm("Do you want to commit the changes to the database?"):
            models.db.session.commit()
        else:
            models.db.session.rollback()
