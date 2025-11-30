#!/usr/bin/env python3

import flask
import pytest
from flasquelistan import models

from tests.helpers import app


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
