from flasquelistan import models

from tests.helpers import logged_in


class TestNotificationViews:
    def test_notifications_page_marks_as_sent(self, client):
        """The notifications page renders and marks notifications as sent."""
        with logged_in(client) as user:
            notification = models.Notification(
                text="Testnotis",
                user_id=user.id,
                type='streque',
                reference='1'
            )
            models.db.session.add(notification)
            models.db.session.commit()

            response = client.get('/notifications')
            assert response.status_code == 200
            assert 'Testnotis' in response.get_data(as_text=True)
            assert notification.is_sent

    def test_mark_notifications_read(self, client):
        """Sent notifications are acknowledged and user is redirected."""
        with logged_in(client) as user:
            notification = models.Notification(
                text="Testnotis",
                user_id=user.id,
                type='streque',
                reference='1',
                is_sent=True
            )
            models.db.session.add(notification)
            models.db.session.commit()

            response = client.get('/notifications/mark-read')
            assert response.status_code == 302
            assert notification.is_acknowledged

    def test_notifications_require_login(self, client):
        """Anonymous users are redirected to the login page."""
        response = client.get('/notifications')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']
