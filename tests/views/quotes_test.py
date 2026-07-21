#!/usr/bin/env python3


from flask import url_for

from flasquelistan import models
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


class TestQuoteViews:
    """Test adding and viewing quotes"""

    def test_add_quote(self, client):
        with logged_in(client):
            response = client.post(
                url_for('quotes.add_quote'),
                data={
                    'text': 'He is not the Messiah!',
                    'who': 'Brians mother',
                },
                follow_redirects=True
            )
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'Citat tillagt!' in text

            quote = models.Quote.query.one()
            assert quote.text == 'He is not the Messiah!'
            assert quote.who == 'Brians mother'

    def test_add_quote_requires_text(self, client):
        with logged_in(client):
            response = client.post(
                url_for('quotes.add_quote'),
                data={'text': '', 'who': 'Nobody'}
            )

            assert response.status_code == 200
            assert models.Quote.query.count() == 0

    def test_single_quote_page(self, client):
        quote = models.Quote(
            text="And now for something completely different.",
            who="Newsreader [John Cleese]"
        )
        models.db.session.add(quote)
        models.db.session.commit()

        with logged_in(client):
            response = client.get(url_for('quotes.quote', quote_id=quote.id))
            text = response.get_data(as_text=True)

            assert response.status_code == 200
            assert quote.text in text

    def test_unknown_quote_404(self, client):
        with logged_in(client):
            response = client.get(url_for('quotes.quote', quote_id=4711))
            assert response.status_code == 404
