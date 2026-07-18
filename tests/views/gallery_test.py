from tests.helpers import logged_in


class TestGalleryViews:
    def test_gallery_page(self, client):
        """The gallery renders for a logged in user."""
        with logged_in(client):
            response = client.get('/gallery/')
            assert response.status_code == 200

    def test_user_gallery_page(self, client):
        """The user gallery renders for a logged in user."""
        with logged_in(client) as user:
            response = client.get(f'/gallery/user/{user.id}/')
            assert response.status_code == 200

    def test_gallery_requires_login(self, client):
        """Anonymous users are redirected to the login page."""
        response = client.get('/gallery/')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']
