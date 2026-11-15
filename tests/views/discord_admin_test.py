import json
from unittest import mock
from urllib.parse import unquote

import pytest

from flasquelistan import discord, discord_roles, models
from tests.helpers import logged_in, logged_in_admin, make_user

API = discord.DEFAULT_API_BASE_URL
DISCORD_CONFIG = {
    'DISCORD_BOT_SECRET': 'bot-secret',
    'DISCORD_GUILD_ID': 'guild1',
    'DISCORD_ACTIVE_ROLE_ID': 'role-active',
    'DISCORD_UNKNOWN_ROLE_ID': 'role-unknown',
}


def role(id, name, position, permissions=0, **kwargs):
    return {'id': id, 'name': name, 'position': position,
            'permissions': str(permissions), 'color': 0, **kwargs}


def member(id, roles, username=None, nick=None):
    return {'user': {'id': id, 'username': username or id, 'global_name': None},
            'nick': nick, 'roles': list(roles)}


class Response:
    def __init__(self, data=None, status_code=200, headers=None):
        self.data = data
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code} error")


class FakeDiscord:
    """Stands in for requests.request, answering like the Discord API."""

    def __init__(self):
        self.roles = [
            role('guild1', '@everyone', 0),
            role('role-sg3', 'SG3', 1, color=0xff0000),
            role('role-sg2', 'SG2', 2),
            role('role-sg1', 'SG1', 3),
            role('role-soprano', 'Sopranos', 4),
            role('role-active', 'Aktiv', 4),
            role('role-admin', 'Admins', 5, permissions=1 << 3),
            role('role-integration', 'Some bot', 6, managed=True),
            role('role-bot', 'Streque bot', 10, managed=True),
            role('role-high', 'Above the bot', 11),
        ]
        self.members = [
            member('900', ['role-bot']),
            member('101', ['role-sg1', 'role-active']),
            member('102', ['role-sg2']),
            member('103', ['role-sg3'], username='ext', nick='Old bass'),
            member('104', ['role-active']),
        ]
        self.patches = []
        # Responses for the next PATCH requests, used before the default.
        self.patch_responses = []
        self.fail_reads = False

    def __call__(self, method, url, headers=None, timeout=None, params=None, json=None):
        assert timeout, "every Discord request needs a timeout"
        assert headers['Authorization'] == 'Bot bot-secret'
        path = url[len(API):]
        if self.fail_reads and method == 'GET':
            return Response({'message': 'nope'}, 500)
        if method == 'GET' and path == '/guilds/guild1/roles':
            return Response(self.roles)
        if method == 'GET' and path == '/guilds/guild1/members':
            members = sorted(self.members, key=lambda m: int(m['user']['id']))
            members = [m for m in members if int(m['user']['id']) > int(params['after'])]
            return Response(members[:params['limit']])
        if method == 'GET' and path == '/users/@me':
            return Response({'id': '900'})
        if method == 'PATCH' and path.startswith('/guilds/guild1/members/'):
            self.patches.append({'user': path.rsplit('/', 1)[1], 'roles': json['roles'],
                                 'reason': headers.get('X-Audit-Log-Reason')})
            if self.patch_responses:
                return self.patch_responses.pop(0)
            return Response({})
        raise AssertionError(f"unexpected request {method} {url}")


@pytest.fixture
def fake_discord(app, monkeypatch):
    for key, value in DISCORD_CONFIG.items():
        monkeypatch.setitem(app.config, key, value)
    fake = FakeDiscord()
    with mock.patch('flasquelistan.discord.requests.request', side_effect=fake):
        yield fake


@pytest.fixture
def people(fake_discord):
    active = models.Group(name='Active', weight=2, active=True)
    old = models.Group(name='Old', weight=1, active=False)
    sopranos = models.Group(name='Sopranos', weight=3, active=True,
                            discord_role_id='role-soprano')
    models.db.session.add_all([active, old, sopranos])
    models.db.session.commit()
    users = {
        'anna': make_user(email='anna@x.tld', first_name='Anna', last_name='Andersson',
                          nickname='Majsan', group_id=active.id, discord_user_id='101'),
        'bertil': make_user(email='bertil@x.tld', first_name='Bertil', last_name='Berg',
                            group_id=old.id, discord_user_id='102'),
        'cecilia': make_user(email='cecilia@x.tld', first_name='Cecilia', last_name='Ek',
                             group_id=active.id),
        'david': make_user(email='david@x.tld', first_name='David', last_name='Dahl',
                           group_id=active.id, discord_user_id='105'),
    }
    return users


@pytest.fixture
def view(people):
    view = models.DiscordRoleView(name='Sånggrupper', exclusive=True, weight=1, roles=[
        models.DiscordRoleViewRole(role_id='role-sg1'),
        models.DiscordRoleViewRole(role_id='role-sg2'),
        models.DiscordRoleViewRole(role_id='role-sg3'),
    ])
    models.db.session.add(view)
    models.db.session.commit()
    return view


def post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type='application/json')


class TestRoleProblem:
    def problem(self, role_id):
        return discord_roles.Guild.fetch().role_problem(role_id)

    def test_plain_role_below_the_bot_is_editable(self, people):
        assert self.problem('role-sg1') is None

    @pytest.mark.parametrize('role_id', [
        'guild1',  # @everyone
        'role-integration',  # managed by an integration
        'role-soprano',  # synced from a Streque group
        'role-active',  # synced from Streque
        'role-admin',  # has the Administrator permission
        'role-high',  # above the bot's highest role
        'role-deleted',  # doesn't exist
    ])
    def test_blocked_roles(self, people, role_id):
        assert self.problem(role_id) is not None

    def test_dangerous_permission_is_named(self, app, people):
        # The reason is a lazy translation, which needs a request to render.
        with app.test_request_context():
            assert 'Administrator' in str(self.problem('role-admin'))


class TestState:
    def test_roles_people_and_statuses(self, client, view, people):
        with logged_in_admin(client):
            rv = client.get(f'/admin/discord/views/{view.id}/state')
        assert rv.status_code == 200
        data = rv.get_json()

        assert [r['name'] for r in data['roles']] == ['SG1', 'SG2', 'SG3']
        assert data['roles'][2]['color'] == '#ff0000'
        assert all(r['problem'] is None for r in data['roles'])

        by_name = {p['name']: p for p in data['people']}
        # Only the view's roles are included.
        assert by_name['Anna Andersson']['roles'] == ['role-sg1']
        assert by_name['Anna Andersson']['active'] is True
        assert by_name['Anna Andersson']['nickname'] == 'Majsan'
        assert by_name['Anna Andersson']['discord'] == 'linked'
        assert by_name['Bertil Berg']['active'] is False
        assert by_name['Cecilia Ek']['discord'] == 'unlinked'
        assert by_name['Cecilia Ek']['key'] == f"user-{people['cecilia'].id}"
        assert by_name['David Dahl']['discord'] == 'not_in_guild'
        # A Discord member without a Streque account, who has one of the roles.
        assert by_name['Old bass']['discord'] == 'external'
        assert by_name['Old bass']['roles'] == ['role-sg3']
        # Members without any of the view's roles and no account are left out.
        assert not any(p['key'] == '104' for p in data['people'])

    def test_blocked_role_in_view_has_problem(self, client, view, fake_discord):
        view.roles.append(models.DiscordRoleViewRole(role_id='role-admin'))
        view.roles.append(models.DiscordRoleViewRole(role_id='role-deleted'))
        models.db.session.commit()
        with logged_in_admin(client):
            data = client.get(f'/admin/discord/views/{view.id}/state').get_json()
        admin = [r for r in data['roles'] if r['id'] == 'role-admin'][0]
        assert 'Administrator' in admin['problem']
        assert data['missing_roles'] == 1

    def test_discord_failure(self, client, view, fake_discord):
        fake_discord.fail_reads = True
        with logged_in_admin(client):
            rv = client.get(f'/admin/discord/views/{view.id}/state')
        assert rv.status_code == 502
        assert 'error' in rv.get_json()

    def test_members_are_paginated(self, client, view, fake_discord, monkeypatch):
        monkeypatch.setattr(discord, 'MEMBERS_PAGE_SIZE', 2)
        with logged_in_admin(client):
            data = client.get(f'/admin/discord/views/{view.id}/state').get_json()
        assert any(p['key'] == '103' for p in data['people'])


class TestAccess:
    @pytest.mark.parametrize('url', [
        '/admin/discord/',
        '/admin/discord/views/new',
        '/admin/discord/views/{id}',
        '/admin/discord/views/{id}/state',
    ])
    def test_non_admins_are_turned_away(self, client, view, url):
        with logged_in(client):
            rv = client.get(url.format(id=view.id))
        assert rv.status_code in (302, 403)

    def test_non_admins_cannot_apply(self, client, view, fake_discord):
        with logged_in(client):
            rv = post_json(client, f'/admin/discord/views/{view.id}/apply', {'changes': [
                {'key': '101', 'add': ['role-sg2'], 'remove': []}]})
        assert rv.status_code in (302, 403)
        assert fake_discord.patches == []


class TestPreview:
    def test_plan(self, client, view, people):
        with logged_in_admin(client):
            rv = post_json(client, f'/admin/discord/views/{view.id}/preview', {'changes': [
                # A move: keeps the role outside the view.
                {'key': '101', 'add': ['role-sg2'], 'remove': ['role-sg1']},
                # Already the case.
                {'key': '102', 'add': ['role-sg2'], 'remove': ['role-sg3']},
                {'key': '105', 'add': ['role-sg1'], 'remove': []},
                {'key': '103', 'add': [], 'remove': ['role-sg3']},
            ]})
        assert rv.status_code == 200
        plan = {item['key']: item for item in rv.get_json()['plan']}

        assert plan['101']['status'] == 'change'
        assert plan['101']['name'] == 'Anna Andersson'
        assert plan['101']['add'] == ['role-sg2']
        assert plan['101']['remove'] == ['role-sg1']
        assert plan['101']['roles'] == ['role-active', 'role-sg2']
        assert plan['102']['status'] == 'noop'
        assert plan['105']['status'] == 'not_in_guild'
        assert plan['105']['name'] == 'David Dahl'
        assert plan['103']['name'] == 'Old bass'
        assert plan['103']['roles'] == []
        assert 'people' in rv.get_json()['state']

    @pytest.mark.parametrize('changes', [
        # Role outside the view.
        [{'key': '101', 'add': ['role-high'], 'remove': []}],
        # Synced role.
        [{'key': '101', 'add': [], 'remove': ['role-active']}],
        # Malformed.
        'nope',
        [{'add': ['role-sg1']}],
        [{'key': '101', 'add': 'role-sg1'}],
        [{'key': '101', 'add': ['role-sg1'], 'remove': ['role-sg1']}],
        [{'key': '101', 'add': ['role-sg1']}, {'key': '101', 'add': ['role-sg2']}],
    ])
    def test_invalid_changes(self, client, view, changes):
        with logged_in_admin(client):
            rv = post_json(client, f'/admin/discord/views/{view.id}/preview',
                           {'changes': changes})
        assert rv.status_code == 400

    def test_blocked_role_in_view_cannot_be_changed(self, client, view, fake_discord):
        view.roles.append(models.DiscordRoleViewRole(role_id='role-admin'))
        models.db.session.commit()
        with logged_in_admin(client):
            rv = post_json(client, f'/admin/discord/views/{view.id}/preview', {'changes': [
                {'key': '101', 'add': ['role-admin'], 'remove': []}]})
        assert rv.status_code == 400


class TestApply:
    def apply(self, client, view, changes):
        with logged_in_admin(client) as admin:
            admin.first_name = 'Åsa'
            models.db.session.commit()
            rv = post_json(client, f'/admin/discord/views/{view.id}/apply',
                           {'changes': changes})
        assert rv.status_code == 200
        return rv.get_json()

    def test_patches_full_role_list_with_audit_reason(self, client, view, fake_discord):
        result = self.apply(client, view, [
            {'key': '101', 'add': ['role-sg2'], 'remove': ['role-sg1']},
            {'key': '102', 'add': ['role-sg2'], 'remove': []},
        ])

        assert result == {'results': [{'key': '101', 'status': 'done'},
                                      {'key': '102', 'status': 'noop'}],
                          'remaining': [], 'retry_after': 0}
        assert len(fake_discord.patches) == 1
        patch = fake_discord.patches[0]
        assert patch['user'] == '101'
        assert patch['roles'] == ['role-active', 'role-sg2']
        assert unquote(patch['reason']) == 'Streque, av Åsa Python'

    def test_roles_changed_in_discord_meanwhile_are_kept(self, client, view, fake_discord):
        # Someone gave Anna SG3 in Discord after the page loaded.
        fake_discord.members[1]['roles'].append('role-sg3')
        self.apply(client, view, [{'key': '101', 'add': ['role-sg2'], 'remove': ['role-sg1']}])
        assert fake_discord.patches[0]['roles'] == ['role-active', 'role-sg2', 'role-sg3']

    def test_stops_when_rate_limited(self, client, view, fake_discord):
        fake_discord.patch_responses = [Response({'retry_after': 2.5}, 429)]
        result = self.apply(client, view, [
            {'key': '101', 'add': ['role-sg2'], 'remove': []},
            {'key': '103', 'add': [], 'remove': ['role-sg3']},
        ])
        assert result == {'results': [], 'remaining': ['101', '103'], 'retry_after': 2.5}
        assert len(fake_discord.patches) == 1

    def test_stops_when_bucket_is_empty(self, client, view, fake_discord):
        fake_discord.patch_responses = [Response({}, 200, {
            'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset-After': '1.5'})]
        result = self.apply(client, view, [
            {'key': '101', 'add': ['role-sg2'], 'remove': []},
            {'key': '103', 'add': [], 'remove': ['role-sg3']},
        ])
        assert result['results'] == [{'key': '101', 'status': 'done'}]
        assert result['remaining'] == ['103']
        assert result['retry_after'] == 1.5

    def test_batch_size(self, client, view, fake_discord, monkeypatch):
        monkeypatch.setattr(discord_roles, 'APPLY_BATCH_SIZE', 1)
        result = self.apply(client, view, [
            {'key': '101', 'add': ['role-sg2'], 'remove': []},
            {'key': '103', 'add': [], 'remove': ['role-sg3']},
        ])
        assert result['remaining'] == ['103']
        assert result['retry_after'] == 0
        assert len(fake_discord.patches) == 1

    def test_failure_for_one_member_continues(self, client, view, fake_discord):
        fake_discord.patch_responses = [Response({'message': 'Missing Permissions'}, 403)]
        result = self.apply(client, view, [
            {'key': '101', 'add': ['role-sg2'], 'remove': []},
            {'key': '103', 'add': [], 'remove': ['role-sg3']},
        ])
        assert result['results'][0]['status'] == 'error'
        assert result['results'][1] == {'key': '103', 'status': 'done'}
        assert result['remaining'] == []

    def test_discord_failure(self, client, view, fake_discord):
        fake_discord.fail_reads = True
        with logged_in_admin(client):
            rv = post_json(client, f'/admin/discord/views/{view.id}/apply', {'changes': [
                {'key': '101', 'add': ['role-sg2'], 'remove': []}]})
        assert rv.status_code == 502


class TestViewSettings:
    def test_index_lists_views(self, client, view):
        with logged_in_admin(client):
            rv = client.get('/admin/discord/')
        assert rv.status_code == 200
        assert 'Sånggrupper' in rv.get_data(as_text=True)

    def test_new_view_offers_only_editable_roles(self, client, fake_discord):
        with logged_in_admin(client):
            rv = client.get('/admin/discord/views/new')
        html = rv.get_data(as_text=True)
        assert rv.status_code == 200
        assert 'value="role-sg1"' in html
        assert 'value="role-admin"' not in html
        # Blocked roles are listed with the reason.
        assert 'Administrator' in html

    def test_create_view(self, client, fake_discord):
        with logged_in_admin(client):
            rv = client.post('/admin/discord/views/new', data={
                'name': 'Arbetsgrupper', 'weight': 3, 'roles': ['role-sg1', 'role-sg3']})
        assert rv.status_code == 302
        view = models.DiscordRoleView.query.one()
        assert view.name == 'Arbetsgrupper'
        assert view.exclusive is False
        assert view.role_ids == {'role-sg1', 'role-sg3'}

    def test_blocked_role_is_rejected(self, client, fake_discord):
        with logged_in_admin(client):
            rv = client.post('/admin/discord/views/new', data={
                'name': 'Sneaky', 'weight': 0, 'roles': ['role-admin']})
        assert rv.status_code == 200
        assert models.DiscordRoleView.query.count() == 0

    def test_edit_view(self, client, view):
        with logged_in_admin(client):
            rv = client.get(f'/admin/discord/views/{view.id}/settings')
            assert 'checked' in rv.get_data(as_text=True)
            rv = client.post(f'/admin/discord/views/{view.id}/settings', data={
                'name': 'SG', 'weight': 1, 'exclusive': 'y', 'roles': ['role-sg1', 'role-sg2']})
        assert rv.status_code == 302
        view = models.db.session.get(models.DiscordRoleView, view.id)
        assert view.name == 'SG'
        assert view.role_ids == {'role-sg1', 'role-sg2'}
        assert models.DiscordRoleViewRole.query.count() == 2

    def test_settings_when_discord_fails(self, client, view, fake_discord):
        fake_discord.fail_reads = True
        with logged_in_admin(client):
            rv = client.get(f'/admin/discord/views/{view.id}/settings')
        assert rv.status_code == 302

    def test_remove_view(self, client, view):
        with logged_in_admin(client):
            rv = client.post(f'/admin/discord/views/{view.id}/remove')
        assert rv.status_code == 302
        assert models.DiscordRoleView.query.count() == 0
        assert models.DiscordRoleViewRole.query.count() == 0

    def test_editor_page(self, client, view):
        with logged_in_admin(client):
            rv = client.get(f'/admin/discord/views/{view.id}')
        html = rv.get_data(as_text=True)
        assert rv.status_code == 200
        assert 'discord-roles-config' in html
        assert f'/admin/discord/views/{view.id}/apply' in html
