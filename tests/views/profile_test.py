#!/usr/bin/env python3

import io
import os

import pytest
from PIL import Image

from flask import url_for

from flasquelistan import factory, models

from tests import helpers
from tests.conftest import BASE_TEST_CONFIG, fresh_database
from tests.helpers import logged_in
from tests.helpers import logged_in_admin
from tests.helpers import login
from tests.helpers import logout


@pytest.fixture(scope='module')
def _app(tmp_path_factory):
    """App with upload destinations pointed at a temp directory.

    Overrides the conftest.py app fixtures for this module only, so that
    profile picture uploads do not end up in the repository's static folder.
    """
    tmp_path = tmp_path_factory.mktemp('profile_test')
    config = {
        **BASE_TEST_CONFIG,
        # Store uploads in a temp dir instead of flasquelistan/static/uploads.
        'UPLOADS_DEFAULT_DEST': str(tmp_path / 'uploads'),
        'UPLOADED_IMAGES_DEST': str(tmp_path / 'uploads' / 'images'),
        'UPLOADED_PROFILEPICTURES_DEST': str(
            tmp_path / 'uploads' / 'profilepictures'
        ),
        # Needed to render pages with profile pictures (util.url_for_image).
        'IMAGE_SECRET': 'not-so-secret-test-secret',
        'IMAGE_EXPIRY': 3600,
    }

    return factory.create_app(config)


@pytest.fixture
def app(_app):
    with fresh_database(_app) as app:
        yield app


def make_user(**kwargs):
    """Create an additional user, distinct from the logged in Monty user."""
    kwargs.setdefault('email', 'brian@pfoj.tld')
    kwargs.setdefault('first_name', 'Brian')
    kwargs.setdefault('last_name', 'Cohen')
    return helpers.make_user(**kwargs)


class TestProfilePage:
    """Tests for the profile page"""
    def test_status(self, client):
        with logged_in(client):
            response = client.get(url_for('profile.show_profile', user_id=1))
            assert response.status_code == 200

    def test_edit_profile_link_correct_user(self, client):

        with logged_in(client):
            response = client.get(url_for('profile.show_profile', user_id=1))
            text = response.get_data(as_text=True)

            assert "Redigera profil" in text

    def test_edit_profile_link_admin(self, client):

        user = models.User(
                email='monty@python2.tld',
                first_name='Osquar',
                last_name='Teknolog'
        )

        models.db.session.add(user)
        models.db.session.commit()


        with logged_in_admin(client):

            response = client.get(url_for('profile.show_profile', user_id=user.id))
            text = response.get_data(as_text=True)

            assert "Redigera profil" in text

    def test_edit_profile_link_hidden(self, client):

        user = models.User(
                email='monty@python2.tld',
                first_name='Osquar',
                last_name='Teknolog'
        )

        models.db.session.add(user)
        models.db.session.commit()

        with logged_in(client):
            response = client.get(url_for('profile.show_profile', user_id=user.id))
            text = response.get_data(as_text=True)

            assert "Redigera profil" not in text


class TestProfilePages:
    def test_profile_pages_render(self, client):
        """Smoke test that the profile-owned pages render for the user."""
        with logged_in(client) as user:
            for url in (
                f'/profile/{user.id}/edit/',
                f'/profile/{user.id}/nicknames',
                f'/profile/{user.id}/history',
                f'/profile/{user.id}/api-keys',
                f'/profile/{user.id}/api-keys/new',
                f'/profile/{user.id}/edit/password',
            ):
                response = client.get(url)
                assert response.status_code == 200, url

            response = client.get(f'/profile/{user.id}/vcard')
            assert response.status_code == 200
            assert response.mimetype == 'text/vcard'

    def test_profile_requires_login(self, client):
        """Anonymous users are redirected to the login page."""
        response = client.get('/profile/1/')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']


def test_poke_ux_states(app, client):
    with app.test_request_context():
        # Setup users
        user_a = models.User(
            email='a@example.com',
            first_name='User',
            last_name='A',
            balance=0
        )
        user_b = models.User(
            email='b@example.com',
            first_name='User',
            last_name='B',
            balance=0
        )
        user_a.password = 'password'
        user_b.password = 'password'

        models.db.session.add(user_a)
        models.db.session.add(user_b)
        models.db.session.commit()

        # Login as User A
        login(client, 'a@example.com', 'password')

        # Scenario 1: No previous pokes
        response = client.get(f'/profile/{user_b.id}/')
        assert response.status_code == 200
        assert "👉 Puffa" in response.get_data(as_text=True)
        assert "Puffa tillbaka" not in response.get_data(as_text=True)
        assert "puffade dig" not in response.get_data(as_text=True)

        # Scenario 2: User B pokes User A
        poke = models.Poke(poker_id=user_b.id, pokee_id=user_a.id)
        models.db.session.add(poke)
        models.db.session.commit()

        response = client.get(f'/profile/{user_b.id}/')
        assert response.status_code == 200
        assert "👉 Puffa tillbaka" in response.get_data(as_text=True)
        assert "puffade dig" in response.get_data(as_text=True)

        # Scenario 3: User A pokes User B back
        poke_back = models.Poke(poker_id=user_a.id, pokee_id=user_b.id)
        models.db.session.add(poke_back)
        models.db.session.commit()

        response = client.get(f'/profile/{user_b.id}/')
        assert response.status_code == 200
        assert "👉 Puffa" not in response.get_data(as_text=True)
        assert "Du puffade" in response.get_data(as_text=True)


class TestEditProfile:
    def test_edit_own_profile_page_renders(self, client):
        with logged_in(client) as user:
            response = client.get(
                url_for('profile.edit_profile', user_id=user.id)
            )
            assert response.status_code == 200

    def test_edit_own_profile_normalizes_phone(self, client):
        with logged_in(client) as user:
            response = client.post(
                url_for('profile.edit_profile', user_id=user.id),
                data={
                    'nickname': 'Black Knight',
                    'phone': '0761234567',
                    'y_chromosome': 'n/a',
                }
            )

            assert response.status_code == 302
            # Swedish numbers are normalized to E.164.
            assert user.phone == '+46761234567'
            assert user.nickname == 'Black Knight'

    def test_non_admin_cannot_view_edit_page_of_other_user(self, client):
        other = make_user()

        with logged_in(client):
            response = client.get(
                url_for('profile.edit_profile', user_id=other.id)
            )
            assert response.status_code == 302
            assert response.headers['Location'] == url_for(
                'profile.show_profile', user_id=other.id)

    def test_non_admin_cannot_edit_other_user(self, client):
        other = make_user()

        with logged_in(client):
            response = client.post(
                url_for('profile.edit_profile', user_id=other.id),
                data={'nickname': 'Naughty', 'y_chromosome': 'n/a'}
            )

            assert response.status_code == 302
            assert other.nickname != 'Naughty'

    def test_admin_can_edit_other_user(self, client):
        other = make_user()

        with logged_in_admin(client):
            response = client.post(
                url_for('profile.edit_profile', user_id=other.id),
                data={
                    'first_name': 'Reg',
                    'last_name': 'Judean',
                    'nickname': 'Splitter',
                    'group_id': '-1',
                    'active': 'y',
                    'y_chromosome': 'n/a',
                }
            )

            assert response.status_code == 302
            assert other.first_name == 'Reg'
            assert other.last_name == 'Judean'
            assert other.nickname == 'Splitter'
            assert other.active is True
            assert other.is_admin is False

    def test_admin_only_fields_ignored_for_non_admin(self, client):
        """A regular user posting admin-only fields must not gain anything."""
        with logged_in(client) as user:
            response = client.post(
                url_for('profile.edit_profile', user_id=user.id),
                data={
                    'first_name': 'Hacker',
                    'is_admin': 'y',
                    'active': 'y',
                    'nickname': 'still fine',
                    'y_chromosome': 'n/a',
                }
            )

            assert response.status_code == 302
            # The regular EditUserForm has no admin fields, they are ignored.
            assert user.first_name == 'Monty'
            assert user.is_admin is False
            assert user.active is False
            # But the regular fields are saved.
            assert user.nickname == 'still fine'


class TestChangeEmailOrPassword:
    def test_wrong_password_does_not_change_email(self, client, monkeypatch):
        sent = []
        monkeypatch.setattr(
            'flasquelistan.util.send_email',
            lambda *args, **kwargs: sent.append(args)
        )

        with logged_in(client) as user:
            response = client.post(
                url_for('profile.change_email_or_password', user_id=user.id),
                data={
                    'email': 'new@python.tld',
                    'password': 'liquidsnake',  # wrong password
                }
            )

            # Form is re-rendered with an error, nothing changed.
            assert response.status_code == 200
            assert user.email == 'monty@python.tld'
            assert sent == []

    def test_correct_password_sends_verification_email(self, client,
                                                       monkeypatch):
        sent = []
        monkeypatch.setattr(
            'flasquelistan.util.send_email',
            lambda fromaddr, toaddr, subject, body:
                sent.append((toaddr, subject))
        )

        with logged_in(client) as user:
            response = client.post(
                url_for('profile.change_email_or_password', user_id=user.id),
                data={
                    'email': 'new@python.tld',
                    'password': 'solidsnake',
                }
            )

            assert response.status_code == 302

            # A verification email was sent to the *new* address...
            assert len(sent) == 1
            assert sent[0][0] == 'new@python.tld'

            # ...but the email is not changed until the address is verified.
            assert user.email == 'monty@python.tld'

    def test_change_password(self, client):
        with logged_in(client) as user:
            response = client.post(
                url_for('profile.change_email_or_password', user_id=user.id),
                data={
                    'email': 'monty@python.tld',
                    'password': 'solidsnake',
                    'new_password': 'liquidsnake',
                }
            )
            assert response.status_code == 302

        logout(client)

        # The old password no longer works...
        response = login(client, 'monty@python.tld', 'solidsnake')
        assert response.status_code == 200

        # ...but the new one does.
        response = login(client, 'monty@python.tld', 'liquidsnake')
        assert response.status_code == 302

    def test_non_admin_cannot_open_other_users_password_page(self, client):
        other = make_user()

        with logged_in(client):
            response = client.get(
                url_for('profile.change_email_or_password', user_id=other.id)
            )
            assert response.status_code == 302
            assert response.headers['Location'] == url_for(
                'profile.show_profile', user_id=other.id)

    def test_non_admin_cannot_open_admin_password_page(self, client):
        # The access check must look at the requester's admin bit, not the
        # target's. When the target is an admin, a non-admin requester must
        # still be redirected away and must not see the target's email.
        admin_target = make_user(email='admin@python.tld', is_admin=True)

        with logged_in(client):
            response = client.get(
                url_for('profile.change_email_or_password',
                        user_id=admin_target.id)
            )
            assert response.status_code == 302
            assert response.headers['Location'] == url_for(
                'profile.show_profile', user_id=admin_target.id)
            assert 'admin@python.tld' not in response.get_data(as_text=True)


class TestApiKeys:
    def test_create_api_key_shows_secret_once(self, client, monkeypatch):
        monkeypatch.setattr(
            models.ApiKey, 'generate_key',
            staticmethod(lambda: 'cafebabe' * 4)
        )

        with logged_in(client) as user:
            response = client.post(
                url_for('profile.edit_api_key', user_id=user.id),
                data={'name': 'Spanish inquisition', 'is_enabled': 'y'},
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            # The plaintext key is flashed once...
            assert response.status_code == 200
            assert 'cafebabe' * 4 in text

            api_key = models.ApiKey.query.one()
            assert api_key.name == 'Spanish inquisition'
            assert api_key.user_id == user.id
            # Only a hash of the key is stored.
            assert api_key.api_key != 'cafebabe' * 4

            # ...and is not visible on the api key page afterwards.
            response = client.get(
                url_for('profile.api_keys', user_id=user.id)
            )
            assert 'cafebabe' * 4 not in response.get_data(as_text=True)

    def test_no_admin_privileged_keys_on_non_admin_accounts(self, client):
        # Keys with the admin bit set may only belong to admin users, so
        # even an admin requester must be rejected when trying to attach an
        # admin-privileged key to a non-admin user's account.
        target = make_user(email='target@python.tld', is_admin=False)

        with logged_in_admin(client):
            response = client.post(
                url_for('profile.edit_api_key', user_id=target.id),
                data={
                    'name': 'Escalated key',
                    'has_admin_privileges': 'y',
                    'is_enabled': 'y',
                },
            )

            assert response.status_code == 400
            assert models.ApiKey.query.count() == 0

    def test_admin_can_create_admin_privileged_key_on_admin_account(
            self, client):
        with logged_in_admin(client) as admin:
            response = client.post(
                url_for('profile.edit_api_key', user_id=admin.id),
                data={
                    'name': 'Admin key',
                    'has_admin_privileges': 'y',
                    'is_enabled': 'y',
                },
            )

            assert response.status_code == 302

            api_key = models.ApiKey.query.one()
            assert api_key.user_id == admin.id
            assert api_key.has_admin_privileges is True

    def test_non_admin_cannot_grant_admin_privileges_on_own_key(self, client):
        # A non-admin requester must still be rejected when trying to set the
        # admin bit on their own key.
        with logged_in(client) as user:
            response = client.post(
                url_for('profile.edit_api_key', user_id=user.id),
                data={
                    'name': 'Sneaky key',
                    'has_admin_privileges': 'y',
                    'is_enabled': 'y',
                },
            )

            assert response.status_code == 400
            assert models.ApiKey.query.count() == 0

    def test_delete_api_key(self, client):
        with logged_in(client) as user:
            api_key = models.ApiKey(
                name='Dead parrot',
                api_key=models.ApiKey.generate_key(),
                user_id=user.id,
            )
            models.db.session.add(api_key)
            models.db.session.commit()

            response = client.post(
                url_for('profile.delete_api_key', user_id=user.id,
                        api_key_id=api_key.id),
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'borttagen' in text
            assert models.ApiKey.query.count() == 0

    def test_delete_api_key_with_transactions_blocked(self, client):
        with logged_in(client) as user:
            api_key = models.ApiKey(
                name='Norwegian blue',
                api_key=models.ApiKey.generate_key(),
                user_id=user.id,
            )
            models.db.session.add(api_key)
            models.db.session.commit()

            streque = models.Streque(
                value=-1000,
                text='Holy Grail',
                user_id=user.id,
                created_by_id=user.id,
                api_key_id=api_key.id,
            )
            models.db.session.add(streque)
            models.db.session.commit()

            assert api_key.can_be_deleted is False

            response = client.post(
                url_for('profile.delete_api_key', user_id=user.id,
                        api_key_id=api_key.id)
            )

            assert response.status_code == 400
            assert models.ApiKey.query.count() == 1

    def test_non_admin_cannot_view_other_users_api_keys(self, client):
        other = make_user()

        with logged_in(client):
            response = client.get(
                url_for('profile.api_keys', user_id=other.id)
            )
            assert response.status_code == 302
            assert response.headers['Location'] == url_for(
                'profile.show_profile', user_id=other.id)

    def test_non_admin_cannot_delete_other_users_api_key(self, client):
        victim = make_user()
        api_key = models.ApiKey(
            name='Victim key',
            api_key=models.ApiKey.generate_key(),
            user_id=victim.id,
        )
        models.db.session.add(api_key)
        models.db.session.commit()
        key_id = api_key.id

        with logged_in(client) as attacker:
            assert attacker.id != victim.id
            response = client.post(
                url_for('profile.delete_api_key', user_id=victim.id,
                        api_key_id=key_id)
            )

            # The attacker must be forbidden and the key must survive.
            assert response.status_code == 403
            assert models.db.session.get(models.ApiKey, key_id) is not None

    def test_owner_can_delete_own_api_key(self, client):
        with logged_in(client) as user:
            api_key = models.ApiKey(
                name='Own key',
                api_key=models.ApiKey.generate_key(),
                user_id=user.id,
            )
            models.db.session.add(api_key)
            models.db.session.commit()
            key_id = api_key.id

            response = client.post(
                url_for('profile.delete_api_key', user_id=user.id,
                        api_key_id=key_id),
                follow_redirects=True
            )

            assert response.status_code == 200
            assert 'borttagen' in response.get_data(as_text=True)
            assert models.db.session.get(models.ApiKey, key_id) is None

    def test_admin_can_delete_other_users_api_key(self, client):
        victim = make_user()
        api_key = models.ApiKey(
            name='Victim key',
            api_key=models.ApiKey.generate_key(),
            user_id=victim.id,
        )
        models.db.session.add(api_key)
        models.db.session.commit()
        key_id = api_key.id

        with logged_in_admin(client) as admin:
            assert admin.id != victim.id
            response = client.post(
                url_for('profile.delete_api_key', user_id=victim.id,
                        api_key_id=key_id),
                follow_redirects=True
            )

            assert response.status_code == 200
            assert 'borttagen' in response.get_data(as_text=True)
            assert models.db.session.get(models.ApiKey, key_id) is None


class TestPoke:
    def test_poke_creates_poke_and_notification(self, client):
        other = make_user()

        with logged_in(client) as user:
            response = client.post(
                url_for('profile.poke_user', user_id=other.id),
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Puffad!' in text

            poke = models.Poke.query.one()
            assert poke.poker_id == user.id
            assert poke.pokee_id == other.id

            notification = models.Notification.query.filter_by(
                user_id=other.id, type='poke').one()
            assert 'puffade dig' in notification.text

    def test_cannot_poke_again_before_poke_back(self, client):
        other = make_user()

        with logged_in(client):
            client.post(url_for('profile.poke_user', user_id=other.id))
            response = client.post(
                url_for('profile.poke_user', user_id=other.id),
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert 'redan puffat' in text
            assert models.Poke.query.count() == 1

    def test_cannot_poke_self(self, client):
        with logged_in(client) as user:
            response = client.post(
                url_for('profile.poke_user', user_id=user.id),
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert 'inte puffa dig själv' in text
            assert models.Poke.query.count() == 0

    def test_profile_page_shows_poke_state(self, client):
        other = make_user()

        with logged_in(client):
            response = client.get(
                url_for('profile.show_profile', user_id=other.id)
            )
            assert '👉 Puffa' in response.get_data(as_text=True)

            client.post(url_for('profile.poke_user', user_id=other.id))

            response = client.get(
                url_for('profile.show_profile', user_id=other.id)
            )
            assert 'Du puffade' in response.get_data(as_text=True)


class TestUserPages:
    def test_vcard(self, client):
        with logged_in(client) as user:
            user.phone = '0761234567'
            models.db.session.commit()

            response = client.get(
                url_for('profile.user_vcard', user_id=user.id)
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert response.mimetype == 'text/vcard'
            assert 'Monty Python' in text
            assert 'monty@python.tld' in text

    def test_user_history_page(self, client):
        with logged_in(client) as user:
            response = client.get(
                url_for('profile.user_history', user_id=user.id)
            )
            assert response.status_code == 200

    def test_user_nicknames_page(self, client):
        with logged_in(client) as user:
            response = client.get(
                url_for('profile.user_nicknames', user_id=user.id)
            )
            assert response.status_code == 200


def make_jpeg():
    """Create a small JPEG image in memory."""
    stream = io.BytesIO()
    image = Image.new('RGB', (8, 8), color=(255, 0, 0))
    image.save(stream, format='JPEG')
    stream.seek(0)
    return stream


def make_profile_picture(user, filename='shrubbery.jpg'):
    """Create a ProfilePicture row (no file on disk needed)."""
    picture = models.ProfilePicture(filename=filename, user_id=user.id)
    models.db.session.add(picture)
    models.db.session.commit()
    return picture


class TestProfilePictures:
    def test_upload_profile_picture(self, app, client):
        with logged_in(client) as user:
            response = client.post(
                url_for('profile.upload_profile_picture', user_id=user.id),
                data={'upload': (make_jpeg(), 'avatar.jpg')},
                content_type='multipart/form-data',
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Profilbilden har ändrats!' in text

            assert user.profile_picture is not None
            path = os.path.join(
                app.config['UPLOADED_PROFILEPICTURES_DEST'],
                user.profile_picture.filename
            )
            assert os.path.isfile(path)

    def test_upload_disallowed_file_rejected(self, client):
        with logged_in(client) as user:
            response = client.post(
                url_for('profile.upload_profile_picture', user_id=user.id),
                data={'upload': (io.BytesIO(b'#!/bin/sh'), 'evil.sh')},
                content_type='multipart/form-data',
                follow_redirects=True
            )

            assert response.status_code == 200
            assert user.profile_picture is None
            assert models.ProfilePicture.query.count() == 0

    def test_change_profile_picture(self, client):
        with logged_in(client) as user:
            first = make_profile_picture(user, 'first.jpg')
            second = make_profile_picture(user, 'second.jpg')

            user.profile_picture_id = first.id
            models.db.session.commit()

            response = client.post(
                url_for('profile.change_profile_picture', user_id=user.id),
                data={'profile_picture': str(second.id)},
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Din profilbild har ändrats!' in text
            assert user.profile_picture_id == second.id

    def test_delete_profile_picture(self, client):
        with logged_in(client) as user:
            picture = make_profile_picture(user)
            user.profile_picture_id = picture.id
            models.db.session.commit()

            response = client.post(
                url_for('profile.delete_profile_picture', user_id=user.id),
                data={'profile_picture': str(picture.id)},
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Profilbilden har tagits bort!' in text
            assert models.ProfilePicture.query.count() == 0

    def test_delete_none_profile_picture_rejected(self, client):
        with logged_in(client) as user:
            picture = make_profile_picture(user)

            response = client.post(
                url_for('profile.delete_profile_picture', user_id=user.id),
                data={'profile_picture': 'none'},
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert 'ingenting' in text
            assert models.ProfilePicture.query.count() == 1
            assert picture in models.db.session

    def test_other_user_can_upload_profile_picture(self, client):
        # Intentional: anyone may upload a new profile picture onto any
        # profile — a long-standing gag in the choir. Changing or deleting
        # someone else's existing picture is still restricted (below).
        other = make_user()

        with logged_in(client):
            response = client.post(
                url_for('profile.upload_profile_picture', user_id=other.id),
                data={'upload': (make_jpeg(), 'goofy.jpg')},
                content_type='multipart/form-data',
                follow_redirects=True
            )

            assert response.status_code == 200
            assert other.profile_picture is not None
            assert other.profile_picture.user_id == other.id

    def test_other_user_cannot_change_profile_picture(self, client):
        other = make_user()
        picture = make_profile_picture(other)

        with logged_in(client):
            response = client.post(
                url_for('profile.change_profile_picture', user_id=other.id),
                data={'profile_picture': str(picture.id)}
            )

            assert response.status_code == 302
            assert response.headers['Location'] == url_for(
                'profile.show_profile', user_id=other.id)
            assert other.profile_picture_id is None

    def test_other_user_cannot_delete_profile_picture(self, client):
        other = make_user()
        picture = make_profile_picture(other)

        with logged_in(client):
            response = client.post(
                url_for('profile.delete_profile_picture', user_id=other.id),
                data={'profile_picture': str(picture.id)}
            )

            assert response.status_code == 302
            assert models.ProfilePicture.query.count() == 1

    def test_admin_can_change_other_users_profile_picture(self, client):
        other = make_user()
        picture = make_profile_picture(other)

        with logged_in_admin(client):
            response = client.post(
                url_for('profile.change_profile_picture', user_id=other.id),
                data={'profile_picture': str(picture.id)},
                follow_redirects=True
            )

            assert response.status_code == 200
            assert other.profile_picture_id == picture.id
