import sys
import requests
from requests_oauthlib import OAuth2Session
from flask import current_app
from flask_wtf import csrf
from flasquelistan import models
import pprint

pp = pprint.PrettyPrinter(indent=2)


class DiscordClient:

    def _create_client():
        client_id = current_app.config.get("DISCORD_CLIENT_ID")
        redirect_uri = current_app.config.get("DISCORD_REDIRECT_URI")
        scope = ["identify", "guilds.join"]
        return OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scope)

    def get_authorization_url():
        client = DiscordClient._create_client()
        authorization_url, state = client.authorization_url(
            "https://discord.com/oauth2/authorize",
            prompt="consent",
            state=csrf.generate_csrf(token_key="oauth_state"))
        return authorization_url

    def authenticate(self, authorization_response, state):
        csrf.validate_csrf(state, token_key="oauth_state")

        self.client = DiscordClient._create_client()
        self.token = self.client.fetch_token("https://discord.com/api/oauth2/token",
                                             authorization_response=authorization_response,
                                             client_secret=current_app.config.get("DISCORD_CLIENT_SECRET"))

    def get_user(self):
        return self.client.get("https://discord.com/api/users/@me").json()

    def add_to_server(self, user_id, nickname=None, roles=None):
        data = {"access_token": self.token["access_token"]}
        if nickname is not None:
            data["nick"] = nickname
        if roles is not None:
            data["roles"] = roles
        pp.pprint(data)
        bot_secret = current_app.config.get("DISCORD_BOT_SECRET")
        guild_id = current_app.config.get("DISCORD_GUILD_ID")

        r = requests.put(
            f"https://discord.com/api/guilds/{guild_id}/members/{user_id}",
            json=data,
            headers={"Authorization": f"Bot {bot_secret}"})

        print(f"Add to server response code: {r.status_code}", file=sys.stderr)
        print(r.text, file=sys.stderr)
        return r.status_code == requests.codes.ok

    def add_or_fetch_role(name):
        bot_secret = current_app.config.get("DISCORD_BOT_SECRET")
        guild_id = current_app.config.get("DISCORD_GUILD_ID")

        roles = requests.get(
            f"https://discord.com/api/guilds/{guild_id}/roles",
            headers={"Authorization": f"Bot {bot_secret}"}).json()

        for role in roles:
            if role['name'] == name:
                return role['id']

        role = requests.post(
            f"https://discord.com/api/guilds/{guild_id}/roles",
            json={
                "name": name,
                "hoist": True,
                "mentionable": True,
            },
            headers={"Authorization": f"Bot {bot_secret}"}).json()

        return role['id']

    def get_expected_roles(user):
        if user.discord_user_id is None:
            return []
        roles = []

        group_role_id = user.group.discord_role_id
        if group_role_id is None:
            roles.append(current_app.config.get("DISCORD_UNKNOWN_ROLE_ID"))
        else:
            roles.append(group_role_id)

        if user.group.active:
            roles.append(current_app.config.get("DISCORD_ACTIVE_ROLE_ID"))

        return roles

    def get_current_roles(user_id):
        bot_secret = current_app.config.get("DISCORD_BOT_SECRET")
        guild_id = current_app.config.get("DISCORD_GUILD_ID")

        user = requests.get(
            f"https://discord.com/api/guilds/{guild_id}/members/{user_id}",
            headers={"Authorization": f"Bot {bot_secret}"}).json()
        return user['roles']

    def sync_roles(user):
        if user.discord_user_id is None:
            return

        bot_secret = current_app.config.get("DISCORD_BOT_SECRET")
        guild_id = current_app.config.get("DISCORD_GUILD_ID")

        expected = set(DiscordClient.get_expected_roles(user))
        current = set(DiscordClient.get_current_roles(user.discord_user_id))
        managed = set(group.discord_role_id for group in models.Group
                      .query
                      # Only groups a Discord role id
                      .filter(models.Group.discord_role_id.is_not(None))
                      .order_by(models.Group.weight.desc())
                      .all())
        managed.add(current_app.config.get("DISCORD_ACTIVE_ROLE_ID"))
        managed.add(current_app.config.get("DISCORD_UNKNOWN_ROLE_ID"))

        # Roles that should be kept, because they are not managed by flasquelistan.
        current_non_managed = current.difference(managed)

        new_roles = expected.union(current_non_managed)
        print(f"New roles: {new_roles}", file=sys.stderr)

        if new_roles != current:
            requests.patch(
                f"https://discord.com/api/guilds/{guild_id}/members/{user.discord_user_id}",
                json={"roles": list(new_roles)},
                headers={"Authorization": f"Bot {bot_secret}"})
