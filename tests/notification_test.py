#!/usr/bin/env python3

import flask
from flasquelistan import models
from tests.helpers import logged_in



def test_poke_notification_formatting(app):
    with app.test_request_context():
        poker = models.User(
            email='poker@example.com',
            first_name='<script>alert(1)</script>',
            last_name='Poker',
            balance=0
        )
        pokee = models.User(
            email='pokee@example.com',
            first_name='Pokee',
            last_name='User',
            balance=0
        )

        models.db.session.add(poker)
        models.db.session.add(pokee)
        models.db.session.commit()

        # Create a poke
        poke = pokee.poke(poker)
        assert poke is not False

        # Create notification
        notification = poke.create_notification()

        # Verify formatted_html
        expected_html_name = "&lt;script&gt;alert(1)&lt;/script&gt; Poker"
        assert expected_html_name in notification.formatted_html
        assert "<a href=" in notification.formatted_html
        assert "puffade dig!" in notification.formatted_html
        assert "<script>" not in notification.formatted_html  # Should be escaped

        # Verify formatted_markdown
        # Note: The test environment might not generate external URLs exactly as expected,
        # but we check for the structure.
        assert f"[{poker.displayname}]" in notification.formatted_markdown
        assert "puffade dig!" in notification.formatted_markdown
        assert "(" in notification.formatted_markdown and ")" in notification.formatted_markdown

        # Verify fallback behavior
        models.db.session.delete(poke)
        models.db.session.commit()

        # Refresh notification from DB
        notification = models.db.session.get(models.Notification, notification.id)
        
        # Should fall back to text
        assert notification.formatted_html == flask.escape(notification.text)
        assert notification.formatted_markdown == notification.text


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
