"""Editing Discord roles from Streque's admin pages.

Admins pick a "view" (a saved set of roles, models.DiscordRoleView), edit
who has which role in the browser, preview the changes and apply them. The
browser sends changes as additions and removals rather than the desired end
state, so that role changes made in Discord in the meantime are kept.

Discord has no bulk endpoint for role changes. Each changed member gets one
PATCH with their complete new role list, so moving someone between two roles
costs one request instead of two.
"""
import dataclasses

import requests
from flask import current_app
from flask_babel import lazy_gettext as _l
from sqlalchemy.orm import joinedload

from flasquelistan import discord, models, util

# Roles with any of these permissions can't be handed out from Streque: being
# a Streque admin doesn't make someone a Discord admin.
DANGEROUS_PERMISSIONS = [
    (1 << 1, "Kick Members"),
    (1 << 2, "Ban Members"),
    (1 << 3, "Administrator"),
    (1 << 4, "Manage Channels"),
    (1 << 5, "Manage Server"),
    (1 << 13, "Manage Messages"),
    (1 << 27, "Manage Nicknames"),
    (1 << 28, "Manage Roles"),
    (1 << 29, "Manage Webhooks"),
    (1 << 30, "Manage Expressions"),
    (1 << 33, "Manage Events"),
    (1 << 34, "Manage Threads"),
    (1 << 40, "Moderate Members"),
]


class InvalidChange(ValueError):
    pass


def synced_role_ids():
    """Roles that DiscordClient.sync_roles sets from Streque groups. Editing
    them by hand would be undone at the next sync."""
    ids = {group.discord_role_id for group in models.Group.query.filter(
        models.Group.discord_role_id.is_not(None))}
    ids.add(current_app.config.get("DISCORD_ACTIVE_ROLE_ID"))
    ids.add(current_app.config.get("DISCORD_UNKNOWN_ROLE_ID"))
    return ids


def member_display_name(member):
    user = member.get("user", {})
    return member.get("nick") or user.get("global_name") or user.get("username", "?")


@dataclasses.dataclass
class Guild:
    """A snapshot of the guild's roles and members."""
    roles: dict  # role id -> Discord role object
    members: dict  # user id -> Discord guild member object
    # Position of the bot's highest role. The bot can only hand out roles
    # below it.
    bot_position: int

    @classmethod
    def fetch(cls):
        roles = {role["id"]: role for role in discord.get_guild_roles()}
        members = {member["user"]["id"]: member for member in discord.get_guild_members()}
        bot = members.get(discord.get_bot_user_id(), {"roles": []})
        bot_position = max((roles[r]["position"] for r in bot["roles"] if r in roles),
                           default=0)
        return cls(roles, members, bot_position)

    def role_problem(self, role_id, synced=None):
        """Why Streque may not edit the role, or None if it may."""
        if synced is None:
            synced = synced_role_ids()
        role = self.roles.get(role_id)
        if role is None:
            return _l("Rollen finns inte längre i Discord.")
        if role_id == current_app.config.get("DISCORD_GUILD_ID"):
            return _l("@everyone kan inte redigeras.")
        if role.get("managed"):
            return _l("Rollen hanteras av en integration.")
        if role_id in synced:
            return _l("Rollen synkas automatiskt med en Streque-grupp.")
        permissions = int(role.get("permissions") or 0)
        dangerous = [name for bit, name in DANGEROUS_PERMISSIONS if permissions & bit]
        if dangerous:
            return _l("Rollen har behörigheten %(permissions)s.",
                      permissions=", ".join(dangerous))
        if role["position"] >= self.bot_position:
            return _l("Rollen ligger inte under botens högsta roll.")
        return None

    def sorted_roles(self, role_ids):
        """The roles that still exist, in Discord's order (highest first)."""
        roles = [self.roles[r] for r in role_ids if r in self.roles]
        # Discord breaks position ties by id. Snowflakes are numeric strings,
        # so (length, string) sorts them numerically.
        return sorted(roles, key=lambda role: (-role["position"], len(role["id"]), role["id"]))

    def editable_role_ids(self, view):
        synced = synced_role_ids()
        return {r for r in view.role_ids if self.role_problem(r, synced) is None}


def _people(guild, role_ids):
    """Everyone the editor can show: all Streque users, plus Discord members
    without a Streque account who have one of the roles."""
    people = []
    linked = set()
    users = (models.User.query
             .options(joinedload(models.User.group))
             .order_by(models.User.first_name, models.User.last_name)
             .all())

    for user in users:
        key = user.discord_user_id
        member = None
        if key and key not in linked:
            linked.add(key)
            member = guild.members.get(key)
            status = "linked" if member else "not_in_guild"
        else:
            key = f"user-{user.id}"
            status = "unlinked"

        picture = None
        if user.profile_picture:
            picture = util.url_for_image(user.profile_picture.filename,
                                         "profilepicture", 200)

        people.append({
            "key": key,
            "user_id": user.id,
            "name": user.full_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "nickname": user.nickname or "",
            "active": bool(user.group and user.group.active),
            "discord": status,
            "roles": sorted(set(member["roles"]) & role_ids) if member else [],
            "picture": picture,
            "emoji": user.emoji,
        })

    for key, member in guild.members.items():
        roles = set(member["roles"]) & role_ids
        if key in linked or not roles:
            continue
        people.append({
            "key": key,
            "user_id": None,
            "name": member_display_name(member),
            "first_name": "",
            "last_name": "",
            "nickname": "",
            "active": False,
            "discord": "external",
            "roles": sorted(roles),
            "picture": None,
            "emoji": None,
        })

    return people


def view_state(view, guild):
    """Everything the editor needs, as JSON-serializable data."""
    synced = synced_role_ids()
    roles = guild.sorted_roles(view.role_ids)
    problems = {role["id"]: guild.role_problem(role["id"], synced) for role in roles}
    return {
        "view": {"id": view.id, "name": view.name, "exclusive": view.exclusive},
        "roles": [{
            "id": role["id"],
            "name": role["name"],
            "color": f"#{role['color']:06x}" if role.get("color") else None,
            "problem": str(problems[role["id"]]) if problems[role["id"]] else None,
        } for role in roles],
        "missing_roles": len(view.role_ids - guild.roles.keys()),
        "people": _people(guild, {role["id"] for role in roles}),
    }


def parse_changes(data):
    """Validate the changes posted by the editor:
    [{"key": discord user id, "add": [role id, ...], "remove": [role id, ...]}]
    """
    if not isinstance(data, list):
        raise InvalidChange("changes must be a list")
    changes = []
    seen = set()
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise InvalidChange("every change needs a key")
        add, remove = item.get("add", []), item.get("remove", [])
        if not all(isinstance(lst, list) and all(isinstance(r, str) for r in lst)
                   for lst in (add, remove)):
            raise InvalidChange("add and remove must be lists of role ids")
        add, remove = set(add), set(remove)
        if add & remove:
            raise InvalidChange("a role can't be both added and removed")
        if item["key"] in seen:
            raise InvalidChange("one change per person")
        seen.add(item["key"])
        changes.append({"key": item["key"], "add": add, "remove": remove})
    return changes


def plan_changes(view, guild, changes):
    """What applying the changes would do to each member, based on their
    current roles in the guild."""
    editable = guild.editable_role_ids(view)
    names = {user.discord_user_id: user.full_name for user in models.User.query.filter(
        models.User.discord_user_id.is_not(None))}

    plan = []
    for change in changes:
        if not (change["add"] | change["remove"]) <= editable:
            raise InvalidChange("a role is not editable in this view")

        key = change["key"]
        member = guild.members.get(key)
        if member is None:
            plan.append({"key": key, "name": names.get(key, key), "status": "not_in_guild",
                         "add": sorted(change["add"]), "remove": sorted(change["remove"])})
            continue

        current = set(member["roles"])
        add = change["add"] - current
        remove = change["remove"] & current
        plan.append({
            "key": key,
            "name": names.get(key) or member_display_name(member),
            "status": "change" if add or remove else "noop",
            "add": sorted(add),
            "remove": sorted(remove),
            "roles": sorted((current - remove) | add),
        })
    return plan


# How many members one apply request changes at most. The site runs a single
# gunicorn worker, so every request must finish quickly.
APPLY_BATCH_SIZE = 5


def apply_changes(view, changes, reason):
    """Apply up to APPLY_BATCH_SIZE of the changes.

    Instead of sleeping through a rate limit, this returns early with the
    members still to do and how many seconds to wait first. The browser waits
    and sends the rest.
    """
    def stop(results, remaining, retry_after):
        return {"results": results, "remaining": remaining, "retry_after": retry_after}

    try:
        guild = Guild.fetch()
    except discord.RateLimited as e:
        return stop([], [c["key"] for c in changes], e.retry_after)

    plan = plan_changes(view, guild, changes)
    results = []
    requests_made = 0
    for i, item in enumerate(plan):
        if item["status"] != "change":
            results.append({"key": item["key"], "status": item["status"]})
            continue
        if requests_made == APPLY_BATCH_SIZE:
            return stop(results, [p["key"] for p in plan[i:]], 0)
        requests_made += 1

        try:
            response = discord.set_member_roles(item["key"], item["roles"], reason)
        except discord.RateLimited as e:
            return stop(results, [p["key"] for p in plan[i:]], e.retry_after)
        except requests.RequestException as e:
            current_app.logger.warning("Failed to set Discord roles for %s: %s",
                                       item["key"], e)
            results.append({"key": item["key"], "status": "error", "message": str(e)})
            continue

        results.append({"key": item["key"], "status": "done"})
        wait = discord.rate_limit_wait(response)
        if wait and i + 1 < len(plan):
            return stop(results, [p["key"] for p in plan[i + 1:]], wait)

    return stop(results, [], 0)
