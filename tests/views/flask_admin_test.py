from tests.helpers import logged_in, logged_in_admin


class TestFlaskAdminAccess:
    """Smoke tests for the Flask-Admin database admin at /flask-admin/."""

    def test_admin_sees_index(self, client):
        with logged_in_admin(client):
            response = client.get('/flask-admin/')
            assert response.status_code == 200

    def test_admin_sees_user_list(self, client):
        with logged_in_admin(client):
            response = client.get('/flask-admin/user/')
            assert response.status_code == 200
            assert 'monty@python.tld' in response.get_data(as_text=True)

    def test_admin_sees_user_edit_form(self, client):
        with logged_in_admin(client) as user:
            response = client.get(f'/flask-admin/user/edit/?id={user.id}')
            assert response.status_code == 200

    def test_regular_user_is_redirected(self, client):
        with logged_in(client):
            response = client.get('/flask-admin/')
            assert response.status_code == 302

    def test_regular_user_cannot_list_users(self, client):
        with logged_in(client):
            response = client.get('/flask-admin/user/')
            assert response.status_code == 302

    def test_anonymous_is_redirected_to_login(self, client):
        response = client.get('/flask-admin/')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']
