import flask_admin.contrib.sqla
import sqlalchemy as sa

from tests.helpers import logged_in, logged_in_admin


def model_views(app):
    """Every Flask-Admin view that edits a database model."""
    return [view for admin in app.extensions['admin'] for view in admin._views
            if isinstance(view, flask_admin.contrib.sqla.ModelView)]


class TestFlaskAdminForms:
    """Guard the scaffolded create forms against dependency upgrades that
    change them without failing any request."""

    def test_float_columns_get_a_form_field(self, app, client):
        # Flask-Admin finds a converter by walking the column type's MRO.
        # SQLAlchemy 2.1 took Numeric out of Float's MRO, so Float columns
        # (e.g. Article.standardglas) were silently left out of the form.
        with logged_in_admin(client):
            checked = 0
            for view in model_views(app):
                # Mapped columns, not __table__: with single-table inheritance
                # the table also has the subclasses' columns.
                float_columns = [attr.key for attr in sa.inspect(view.model).column_attrs
                                 if isinstance(attr.columns[0].type, sa.Float)]
                if not float_columns:
                    continue
                html = client.get(f'{view.url}/new/').get_data(as_text=True)
                for name in float_columns:
                    assert f'name="{name}"' in html, f'{view.url}: {name} missing'
                    checked += 1
            assert checked > 0

    def test_blank_relationship_choice_has_no_label(self, app, client):
        # WTForms 3.3 renders an empty choice label as the choice's value,
        # which made Flask-Admin's blank option read "__None".
        with logged_in_admin(client):
            for view in model_views(app):
                response = client.get(f'{view.url}/new/')
                assert response.status_code == 200, view.url
                assert '>__None</option>' not in response.get_data(as_text=True), view.url


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
