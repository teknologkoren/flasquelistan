#!/usr/bin/env python3


from flask import url_for

from tests.helpers import logged_in


class TestQuotesPage():

    def test_status(self, client):
        with logged_in(client):
            response = client.get(url_for('quotes.index'))
            assert response.status_code == 200

    def test_empty_quotes(self, client):
        """Test with blank database"""
        with logged_in(client):
            response = client.get(url_for('quotes.index'))
            text = response.get_data(as_text=True)

            assert 'No quotes yet!' in text
