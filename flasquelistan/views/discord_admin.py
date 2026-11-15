"""Admin pages for editing Discord roles. The logic lives in
flasquelistan.discord_roles; the editor itself is static/js/discordRoles.js."""
import flask
import flask_login
import requests
from flask import current_app
from flask_babel import gettext as _
from flask_login import current_user
from wtforms.fields import SelectChoice

from flasquelistan import discord, discord_roles, forms, models
from flasquelistan.views import auth

mod = flask.Blueprint('discordadmin', __name__)
mod.before_request(
    flask_login.login_required(
        auth.admin_required(lambda: None)
    )
)


def fetch_guild():
    """The guild from Discord, or (None, error message) if that fails."""
    try:
        return discord_roles.Guild.fetch(), None
    except discord.RateLimited as e:
        return None, _("Discord ber oss vänta %(seconds)s s. Försök igen strax.",
                       seconds=round(e.retry_after, 1))
    except (requests.RequestException, KeyError, ValueError) as e:
        current_app.logger.warning("Failed to fetch the Discord guild: %s", e)
        return None, _("Kunde inte hämta servern från Discord: %(error)s", error=e)


def json_error(message, status):
    return flask.jsonify({"error": message}), status


@mod.route('/admin/discord/')
def index():
    views = models.DiscordRoleView.query.order_by(
        models.DiscordRoleView.weight.desc(), models.DiscordRoleView.name).all()
    return flask.render_template('discordadmin/index.html', views=views)


@mod.route('/admin/discord/views/new', methods=['GET', 'POST'])
@mod.route('/admin/discord/views/<int:view_id>/settings', methods=['GET', 'POST'])
def edit_view(view_id=None):
    view = models.db.get_or_404(models.DiscordRoleView, view_id) if view_id else None

    guild, error = fetch_guild()
    if guild is None:
        flask.flash(error, 'error')
        return flask.redirect(flask.url_for('discordadmin.index'))

    synced = discord_roles.synced_role_ids()
    roles = [role for role in guild.sorted_roles(guild.roles)
             if role["id"] != current_app.config.get("DISCORD_GUILD_ID")]
    problems = {role["id"]: guild.role_problem(role["id"], synced) for role in roles}

    data = None
    if view:
        data = {"name": view.name, "exclusive": view.exclusive, "weight": view.weight,
                "roles": sorted(view.role_ids)}
    form = forms.DiscordRoleViewForm(data=data)
    form.roles.choices = [SelectChoice(role["id"], role["name"])
                          for role in roles if problems[role["id"]] is None]

    if form.validate_on_submit():
        if not view:
            view = models.DiscordRoleView()
            models.db.session.add(view)
        view.name = form.name.data
        view.exclusive = form.exclusive.data
        view.weight = form.weight.data

        selected = set(form.roles.data)
        kept = [role for role in view.roles if role.role_id in selected]
        new = selected - {role.role_id for role in kept}
        view.roles = kept + [models.DiscordRoleViewRole(role_id=r) for r in sorted(new)]
        models.db.session.commit()

        flask.flash(_("Vyn \"%(name)s\" sparades.", name=view.name), 'success')
        return flask.redirect(flask.url_for('discordadmin.index'))

    blocked = [(role, problems[role["id"]]) for role in roles if problems[role["id"]]]
    # Roles in the view that can no longer be edited are dropped on save.
    dropped = [role for role, _problem in blocked if view and role["id"] in view.role_ids]
    missing = len(view.role_ids - guild.roles.keys()) if view else 0
    return flask.render_template('discordadmin/edit_view.html', form=form, view=view,
                                 blocked=blocked, dropped=dropped, missing=missing)


@mod.route('/admin/discord/views/<int:view_id>/remove', methods=['POST'])
def remove_view(view_id):
    view = models.db.get_or_404(models.DiscordRoleView, view_id)
    models.db.session.delete(view)
    models.db.session.commit()
    flask.flash(_("Vyn \"%(name)s\" togs bort.", name=view.name), 'success')
    return flask.redirect(flask.url_for('discordadmin.index'))


@mod.route('/admin/discord/views/<int:view_id>')
def editor(view_id):
    view = models.db.get_or_404(models.DiscordRoleView, view_id)
    config = {
        "viewId": view.id,
        "urls": {
            "state": flask.url_for('discordadmin.state', view_id=view.id),
            "preview": flask.url_for('discordadmin.preview', view_id=view.id),
            "apply": flask.url_for('discordadmin.apply', view_id=view.id),
        },
        "strings": editor_strings(),
    }
    return flask.render_template('discordadmin/editor.html', view=view, config=config)


@mod.route('/admin/discord/views/<int:view_id>/state')
def state(view_id):
    view = models.db.get_or_404(models.DiscordRoleView, view_id)
    guild, error = fetch_guild()
    if guild is None:
        return json_error(error, 502)
    return flask.jsonify(discord_roles.view_state(view, guild))


def _posted_changes():
    data = flask.request.get_json(silent=True) or {}
    return discord_roles.parse_changes(data.get("changes"))


@mod.route('/admin/discord/views/<int:view_id>/preview', methods=['POST'])
def preview(view_id):
    """What the changes would do, computed against fresh data from Discord.
    Also returns the fresh state, so the editor can show what changed in
    Discord since the page was loaded."""
    view = models.db.get_or_404(models.DiscordRoleView, view_id)
    try:
        changes = _posted_changes()
    except discord_roles.InvalidChange as e:
        return json_error(str(e), 400)

    guild, error = fetch_guild()
    if guild is None:
        return json_error(error, 502)
    try:
        plan = discord_roles.plan_changes(view, guild, changes)
    except discord_roles.InvalidChange as e:
        return json_error(str(e), 400)
    return flask.jsonify({"plan": plan, "state": discord_roles.view_state(view, guild)})


@mod.route('/admin/discord/views/<int:view_id>/apply', methods=['POST'])
def apply(view_id):
    view = models.db.get_or_404(models.DiscordRoleView, view_id)
    try:
        changes = _posted_changes()
        result = discord_roles.apply_changes(
            view, changes, reason=f"Streque, av {current_user.full_name}")
    except discord_roles.InvalidChange as e:
        return json_error(str(e), 400)
    except (requests.RequestException, KeyError, ValueError) as e:
        current_app.logger.warning("Failed to apply Discord role changes: %s", e)
        return json_error(_("Kunde inte hämta servern från Discord: %(error)s", error=e), 502)
    return flask.jsonify(result)


def editor_strings():
    """The editor's user-facing strings, translated."""
    return {
        "exclusive": _("Ömsesidigt uteslutande"),
        "exclusiveHelp": _("Den som läggs till i en roll tas bort från vyns övriga roller."),
        "users": _("Användare:"),
        "onlyActive": _("Endast aktiva"),
        "allUsers": _("Alla"),
        "filter": _("Sök person…"),
        "pasteList": _("Klistra in lista…"),
        "clearAll": _("Töm alla"),
        "pool": _("Utan roll i vyn"),
        "poolEmpty": _("Alla har minst en roll i vyn."),
        "dragHint": _("Dra personer mellan rollerna. Håll ned Ctrl eller Alt för att "
                      "kopiera i stället för att flytta."),
        "addPlaceholder": _("Lägg till…"),
        "clear": _("Töm"),
        "removed": _("Tas bort (%(count)s)"),
        "remove": _("Ta bort"),
        "undo": _("Ångra"),
        "moveTo": _("Flytta till %(role)s"),
        "alsoAdd": _("Lägg även i %(role)s"),
        "addTo": _("Lägg i %(role)s"),
        "menu": _("Fler val"),
        "unlinked": _("ej kopplad till Discord"),
        "notInGuild": _("inte med på servern"),
        "external": _("Discord-medlem utan Streque-konto"),
        "notActive": _("inte aktiv"),
        "movesFrom": _("i %(roles)s, flyttas"),
        "noMatches": _("Inga träffar"),
        "summary": _("%(changes)s ändringar för %(people)s personer"),
        "noChanges": _("Inga ändringar"),
        "savedLocally": _("sparat i webbläsaren"),
        "discard": _("Ångra alla"),
        "review": _("Granska…"),
        "confirmDiscard": _("Ångra alla ändringar?"),
        "confirmClear": _("Ta bort alla från %(role)s?"),
        "confirmClearAll": _("Ta bort alla från alla roller i vyn?"),
        "locked": _("Kan inte redigeras här: %(reason)s"),
        "missingRoles": _("%(count)s av vyns roller finns inte längre i Discord."),
        "noRoles": _("Vyn har inga roller. Välj roller under vyns inställningar."),
        "loading": _("Hämtar från Discord…"),
        "error": _("Något gick fel: %(error)s"),
        "reviewTitle": _("Granska ändringar"),
        "fetchedAt": _("Hämtat från Discord %(time)s. En begäran per person som ändras."),
        "nothingToDo": _("Inget att göra: Discord stämmer redan."),
        "drift": _("Ändrat i Discord sedan sidan laddades (din vy är uppdaterad):"),
        "member": _("Medlem"),
        "change": _("Ändring"),
        "alreadyDone": _("redan gjort"),
        "back": _("Tillbaka"),
        "confirm": _("Bekräfta"),
        "close": _("Stäng"),
        "retry": _("Försök igen"),
        "applying": _("Tillämpar… %(done)s av %(total)s klara"),
        "waiting": _("väntar %(seconds)s s på Discords rate limit"),
        "applied": _("Klart: %(done)s av %(total)s ändrade."),
        "failed": _("Misslyckades:"),
        "pasteTitle": _("Klistra in lista"),
        "target": _("Mål:"),
        "wholeView": _("Hela vyn (rubriker = roller)"),
        "replace": _("Ersätt medlemmar"),
        "addOnly": _("Lägg bara till"),
        "pasteHelp": _("En person per rad eller cell (t.ex. kopierat från ett kalkylark), "
                       "eller kommaseparerat. Punkter, numrering och text inom parenteser "
                       "eller hakparenteser ignoreras. En rad med en rolls namn blir en "
                       "rubrik för raderna under."),
        "skipUnmatched": _("Hoppa över rader utan säker träff"),
        "uncertain": _("Osäker träff, välj…"),
        "line": _("Rad"),
        "interpretation": _("Tolkning"),
        "sectionSummary": _("%(added)s läggs till, %(removed)s tas bort"),
        "noSection": _("Ingen roll: lägg en rubrik med rollens namn ovanför"),
        "unknownRole": _("Okänd roll, raderna under hoppas över"),
        "choose": _("Välj… (%(count)s träffar)"),
        "skip": _("Hoppa över"),
        "skipped": _("Hoppas över"),
        "search": _("Ingen träff, sök…"),
        "edit": _("ändra"),
        "duplicate": _("%(name)s igen, ignoreras"),
        "onlyActiveMatch": _("enda aktiva träffen"),
        "alreadyIn": _("redan med"),
        "needsChoice": _("%(count)s rader behöver ett val"),
        "cancel": _("Avbryt"),
        "pasteApply": _("Lägg in i vyn"),
    }
