import sys
import traceback

import flask
from flask import abort, current_app, request
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required

from config import ADMIN_EMAILADDR
from flasquelistan import forms, models
from flasquelistan.discord import DiscordClient

mod = flask.Blueprint('discord_oauth', __name__)
mod.before_request(login_required(lambda: None))


@mod.route('/discord')
def discord():
    return flask.render_template('discord.html',
        user=current_user,
        admin_email=ADMIN_EMAILADDR,
        form=forms.DisconnectDiscordForm())


@mod.route('/discord/connect')
def discord_redirect():
    # Redirect if the current user is in a group connected to Discord.
    if current_user.group and current_user.group.discord_role_id:
        return flask.redirect(DiscordClient.get_authorization_url())
    # Otherwise, the user is not allowed to join.
    else:
        abort(403)


@mod.route('/discord/disconnect', methods=['POST'])
def discord_disconnect():
    # Replace all managed roles by just the "Unknown" role.
    DiscordClient.sync_roles_on_disconnect(current_user)

    # Delete discord account information from the database.
    current_user.discord_user_id = None
    current_user.discord_username = None
    models.db.session.commit()

    flask.flash(
        _l("Ditt Discord-konto är inte längre kopplat till din Streque-profil."),
        'success')
    return flask.redirect(flask.url_for('profile.show_profile', user_id=current_user.id))


@mod.route('/discord/callback')
def discord_callback():
    # Only users in a group connected to Discord are allowed to join.
    if not (current_user.group and current_user.group.discord_role_id):
        abort(403)

    try:
        client = DiscordClient()
        client.authenticate(request.url, request.args.get("state"))
    except Exception:
        print(f"User {current_user.full_name} tried to connect with Discord but an "
            "exception was thrown:", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        flask.flash(_l('Något gick snett. Försök gärna en gång till, det löser vissa '
            'kända problem. Prata med webmaster om det inte hjälper.'),
            'error')
        return flask.redirect(flask.url_for('discord_oauth.discord'))

    discord_user = client.get_user()

    existing_users = models.User.query.filter_by(discord_user_id=discord_user['id']).all()
    if existing_users:
        for existing_user in existing_users:
            if existing_user == current_user:
                continue

            # This Discord account was already connected to another Streque user.
            # Remove the previous connection.
            DiscordClient.sync_roles_on_disconnect(existing_user)
            existing_user.discord_user_id = None
            existing_user.discord_username = None

            flask.flash(_l('Discord-kontot du loggade in med var redan kopplat till '
                '%s. Det är nu kopplat till dig (%s) istället.' %
                (existing_user.full_name, current_user.full_name)),
                'warning')

    if (current_user.discord_user_id is not None
        and current_user.discord_user_id != discord_user["id"]):

        # This Streque account was already connected to a different Discord account.
        # Remove any managed roles before adding the new account.
        DiscordClient.sync_roles_on_disconnect(current_user)

        flask.flash(
            _l('Du hade redan ett annat Discord-konto (%s) kopplat till ditt Streque-konto. '
               'Kontot du loggade in med nu (%s) har ersätt det gamla.') %
                (
                    current_user.discord_username,
                    f'{discord_user["username"]}#{discord_user["discriminator"]}'
                ),
            'warning')


    current_user.discord_user_id = discord_user["id"]
    if discord_user["discriminator"] == "0":
        # If the user is migrated to the new tag-less Discord username system, don't include the
        # 0 tag in the stored username. For more info see https://support-dev.discord.com/hc/en-us/articles/13667755828631.
        current_user.discord_username = f'{discord_user["username"]}'
    else:
        # If the user still has a legacy username with a tag, include it in the stored username.
        current_user.discord_username = f'{discord_user["username"]}#{discord_user["discriminator"]}'
    models.db.session.commit()

    client.add_to_server(
        discord_user['id'],
        current_user.full_name,
        DiscordClient.get_expected_roles(current_user))

    DiscordClient.sync_roles(current_user)

    guild_id = current_app.config.get("DISCORD_GUILD_ID")
    flask.flash(_l("Du är nu tillagd i vår Discord-server! %sKlicka här för att besöka den.%s") %
                (f'<a href="https://discord.com/channels/{guild_id}" target="_blank">', '</a>'), 'success')
    return flask.redirect(flask.url_for('profile.show_profile', user_id=current_user.id))
