#!/usr/bin/env python3


from flask import url_for

from flasquelistan import models

from tests.helpers import logged_in
from tests.helpers import logged_in_admin
from tests.helpers import login


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
