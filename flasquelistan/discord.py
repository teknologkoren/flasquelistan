from urllib.parse import quote

import requests
from requests_oauthlib import OAuth2Session
from flask import current_app
from flask_wtf import csrf
from flasquelistan import models

# Timeout for calls to the Discord API. The site runs on a single gunicorn
# worker, so a hanging request here would freeze the whole site.
REQUEST_TIMEOUT = 10

# Base URL for the bot API calls below. Overridable so that a fake Discord can
# stand in during local development.
DEFAULT_API_BASE_URL = "https://discord.com/api/v10"

# Discord's maximum page size when listing guild members.
MEMBERS_PAGE_SIZE = 1000


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
                                             client_secret=current_app.config.get("DISCORD_CLIENT_SECRET"),
                                             timeout=REQUEST_TIMEOUT)

    def get_user(self):
        return self.client.get("https://discord.com/api/users/@me",
                               timeout=REQUEST_TIMEOUT).json()

    def add_to_server(self, user_id, nickname=None, roles=None):
        data = {"access_token": self.token["access_token"]}
        if nickname is not None:
            data["nick"] = nickname
        if roles is not None:
            data["roles"] = roles
        bot_secret = current_app.config.get("DISCORD_BOT_SECRET")
        guild_id = current_app.config.get("DISCORD_GUILD_ID")

        r = requests.put(
            f"https://discord.com/api/guilds/{guild_id}/members/{user_id}",
            json=data,
            headers={"Authorization": f"Bot {bot_secret}"},
            timeout=REQUEST_TIMEOUT)

        return r.status_code == requests.codes.ok

    def add_or_fetch_role(name):
        bot_secret = current_app.config.get("DISCORD_BOT_SECRET")
        guild_id = current_app.config.get("DISCORD_GUILD_ID")

        roles = requests.get(
            f"https://discord.com/api/guilds/{guild_id}/roles",
            headers={"Authorization": f"Bot {bot_secret}"},
            timeout=REQUEST_TIMEOUT).json()

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
            headers={"Authorization": f"Bot {bot_secret}"},
            timeout=REQUEST_TIMEOUT).json()

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
            headers={"Authorization": f"Bot {bot_secret}"},
            timeout=REQUEST_TIMEOUT).json()
        return user['roles']

    # Set and remove Discord roles based on the user's group on Strequelistan.
    # If disconnect is True, replace all managed roles with the Unknown role.
    def sync_roles(user, disconnect=False):
        if user.discord_user_id is None:
            return

        bot_secret = current_app.config.get("DISCORD_BOT_SECRET")
        guild_id = current_app.config.get("DISCORD_GUILD_ID")
        active_role_id = current_app.config.get("DISCORD_ACTIVE_ROLE_ID")
        unknown_role_id = current_app.config.get("DISCORD_UNKNOWN_ROLE_ID")

        if disconnect:
            expected = set((unknown_role_id,))
            try:
                current = set(DiscordClient.get_current_roles(user.discord_user_id))
            except (requests.RequestException, KeyError):
                # The API call failed or the user is no longer in the guild
                # (error responses have no 'roles' key). Still strip the
                # managed roles so the disconnect completes.
                current = set()
        else:
            expected = set(DiscordClient.get_expected_roles(user))
            current = set(DiscordClient.get_current_roles(user.discord_user_id))

        managed = set(group.discord_role_id for group in models.Group
                      .query
                      # Only groups a Discord role id
                      .filter(models.Group.discord_role_id.is_not(None))
                      .order_by(models.Group.weight.desc())
                      .all())
        managed.add(active_role_id)
        managed.add(unknown_role_id)

        # Roles that should be kept, because they are not managed by flasquelistan.
        current_non_managed = current.difference(managed)

        new_roles = expected.union(current_non_managed)

        if new_roles != current:
            requests.patch(
                f"https://discord.com/api/guilds/{guild_id}/members/{user.discord_user_id}",
                json={"roles": list(new_roles)},
                headers={
                    "Authorization": f"Bot {bot_secret}",
                    "X-Audit-Log-Reason": f"Syncing roles with Streque user #{user.id}: {user.full_name}",
                },
                timeout=REQUEST_TIMEOUT)

    def sync_roles_on_disconnect(user):
        DiscordClient.sync_roles(user, True)


class RateLimited(Exception):
    """Discord answered 429 Too Many Requests.

    retry_after is the number of seconds to wait before trying again.
    """

    def __init__(self, retry_after):
        super().__init__(f"Rate limited by Discord, retry after {retry_after} s")
        self.retry_after = retry_after


def bot_request(method, path, reason=None, **kwargs):
    """Make a request to the Discord API as the bot.

    Raises RateLimited on 429, and requests.HTTPError on other errors.
    reason is shown in the guild's audit log.
    """
    base_url = current_app.config.get("DISCORD_API_BASE_URL", DEFAULT_API_BASE_URL)
    headers = {"Authorization": f"Bot {current_app.config.get('DISCORD_BOT_SECRET')}"}
    if reason:
        # The header must be URL-encoded UTF-8, at most 512 characters.
        headers["X-Audit-Log-Reason"] = quote(reason)[:512]

    r = requests.request(method, base_url + path, headers=headers,
                         timeout=REQUEST_TIMEOUT, **kwargs)
    if r.status_code == 429:
        try:
            retry_after = float(r.json()["retry_after"])
        except (ValueError, KeyError, TypeError):
            retry_after = 1.0
        raise RateLimited(retry_after)
    r.raise_for_status()
    return r


def rate_limit_wait(response):
    """Seconds to wait before the next request in the same rate limit bucket,
    or 0 if the bucket still has requests left."""
    if response.headers.get("X-RateLimit-Remaining") != "0":
        return 0
    try:
        return float(response.headers.get("X-RateLimit-Reset-After", 0))
    except ValueError:
        return 0


def _guild_path(path=""):
    return f"/guilds/{current_app.config.get('DISCORD_GUILD_ID')}{path}"


def get_guild_roles():
    return bot_request("GET", _guild_path("/roles")).json()


def get_guild_members():
    """All members of the guild. Needs the Server Members privileged intent."""
    members = []
    after = "0"
    while True:
        page = bot_request("GET", _guild_path("/members"),
                           params={"limit": MEMBERS_PAGE_SIZE, "after": after}).json()
        members.extend(page)
        if len(page) < MEMBERS_PAGE_SIZE:
            return members
        after = max((m["user"]["id"] for m in page), key=int)


def get_bot_user_id():
    return bot_request("GET", "/users/@me").json()["id"]


def set_member_roles(user_id, role_ids, reason):
    """Replace a member's roles with role_ids. Returns the response, whose
    headers tell how much of the rate limit is left."""
    return bot_request("PATCH", _guild_path(f"/members/{user_id}"),
                       json={"roles": sorted(role_ids)}, reason=reason)
