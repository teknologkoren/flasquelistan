from unittest import mock

import pytest
import requests

from flasquelistan import models
from flasquelistan.discord import DiscordClient

DISCORD_CONFIG = {
    'DISCORD_BOT_SECRET': 'bot-secret',
    'DISCORD_GUILD_ID': 'guild1',
    'DISCORD_ACTIVE_ROLE_ID': 'role-active',
    'DISCORD_UNKNOWN_ROLE_ID': 'role-unknown',
}


def make_response(json_data, status_code=200):
    response = mock.Mock()
    response.json.return_value = json_data
    response.status_code = status_code
    return response


def assert_has_timeout(mocked):
    """All calls to the Discord API must have a timeout: with gunicorn
    running a single worker, one hanging request freezes the whole site."""
    for call in mocked.call_args_list:
        assert call.kwargs.get('timeout'), (
            f"requests call without timeout: {call}"
        )


@pytest.fixture
def discord_app(app):
    app.config.update(DISCORD_CONFIG)
    return app


@pytest.fixture
def discord_user(discord_app):
    group = models.Group(
        name='Sopranos',
        weight=1,
        active=True,
        discord_role_id='role-soprano',
    )
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
    )
    models.db.session.add_all([group, user])
    models.db.session.commit()
    user.group_id = group.id
    user.discord_user_id = 'discord-user-1'
    models.db.session.commit()
    return user


class TestAddOrFetchRole:
    def test_returns_existing_role(self, discord_app):
        with mock.patch('flasquelistan.discord.requests.get') as get, \
                mock.patch('flasquelistan.discord.requests.post') as post:
            get.return_value = make_response([
                {'name': 'Sopranos', 'id': 'role-soprano'},
            ])

            assert DiscordClient.add_or_fetch_role('Sopranos') == 'role-soprano'
            post.assert_not_called()
            assert_has_timeout(get)

    def test_creates_missing_role(self, discord_app):
        with mock.patch('flasquelistan.discord.requests.get') as get, \
                mock.patch('flasquelistan.discord.requests.post') as post:
            get.return_value = make_response([])
            post.return_value = make_response({'id': 'role-new'})

            assert DiscordClient.add_or_fetch_role('Tenors') == 'role-new'
            assert_has_timeout(get)
            assert_has_timeout(post)


class TestGetCurrentRoles:
    def test_returns_roles(self, discord_app):
        with mock.patch('flasquelistan.discord.requests.get') as get:
            get.return_value = make_response({'roles': ['a', 'b']})

            assert DiscordClient.get_current_roles('discord-user-1') == ['a', 'b']
            assert_has_timeout(get)


class TestSyncRoles:
    def test_patches_when_roles_differ(self, discord_user):
        with mock.patch('flasquelistan.discord.requests.get') as get, \
                mock.patch('flasquelistan.discord.requests.patch') as patch:
            get.return_value = make_response({'roles': ['role-unrelated']})

            DiscordClient.sync_roles(discord_user)

            patch.assert_called_once()
            sent_roles = set(patch.call_args.kwargs['json']['roles'])
            assert sent_roles == {
                'role-soprano', 'role-active', 'role-unrelated',
            }
            assert_has_timeout(get)
            assert_has_timeout(patch)

    def test_no_patch_when_roles_match(self, discord_user):
        with mock.patch('flasquelistan.discord.requests.get') as get, \
                mock.patch('flasquelistan.discord.requests.patch') as patch:
            get.return_value = make_response(
                {'roles': ['role-soprano', 'role-active']}
            )

            DiscordClient.sync_roles(discord_user)

            patch.assert_not_called()

    def test_noop_without_discord_id(self, discord_app):
        user = models.User(
            email='brian@pfoj.tld', first_name='Brian', last_name='Smith',
        )
        models.db.session.add(user)
        models.db.session.commit()

        with mock.patch('flasquelistan.discord.requests.get') as get:
            DiscordClient.sync_roles(user)
            get.assert_not_called()

    def test_disconnect_survives_api_error(self, discord_user):
        # Disconnecting should still strip roles locally even if Discord
        # can't tell us the user's current roles (e.g. they left the guild).
        with mock.patch('flasquelistan.discord.requests.get') as get, \
                mock.patch('flasquelistan.discord.requests.patch') as patch:
            get.side_effect = requests.ConnectionError('boom')

            DiscordClient.sync_roles(discord_user, disconnect=True)

            patch.assert_called_once()
            sent_roles = set(patch.call_args.kwargs['json']['roles'])
            assert sent_roles == {'role-unknown'}

    def test_disconnect_survives_unknown_member_response(self, discord_user):
        # Discord answers 404 with an error object (no 'roles' key) when the
        # user has already left the guild; disconnecting must still work.
        with mock.patch('flasquelistan.discord.requests.get') as get, \
                mock.patch('flasquelistan.discord.requests.patch') as patch:
            get.return_value = make_response(
                {'message': 'Unknown Member', 'code': 10007}, status_code=404
            )

            DiscordClient.sync_roles(discord_user, disconnect=True)

            patch.assert_called_once()
            sent_roles = set(patch.call_args.kwargs['json']['roles'])
            assert sent_roles == {'role-unknown'}

    def test_disconnect_does_not_hide_programming_errors(self, discord_user):
        # A bug in our own code must not be silently swallowed by the
        # network-error handling on the disconnect path.
        with mock.patch('flasquelistan.discord.requests.get') as get, \
                mock.patch('flasquelistan.discord.requests.patch'):
            get.side_effect = RuntimeError('bug in our code')

            with pytest.raises(RuntimeError):
                DiscordClient.sync_roles(discord_user, disconnect=True)
