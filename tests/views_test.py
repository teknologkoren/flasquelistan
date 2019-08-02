#!/usr/bin/env python3

import pytest

from flask import url_for
from flask_login import current_user

from flasquelistan import models

from tests.helpers import app
from tests.helpers import client
from tests.helpers import logged_in
from tests.helpers import login
from tests.helpers import logout


class TestIndexPage():
    def test_name_in_list(self, client):
        """Test that users full name shows up on index page if no nickname is present"""
        with logged_in(client):
            response = client.get(url_for('strequelistan.index'))
            text = response.get_data(as_text=True)
            assert 'Monty Python' in text

    def test_nickname_replaces_rea_name(self, client):
        """Test that nicknames replace 'real' name on index page"""
        with logged_in(client):
            current_user.nickname = "Black Knight"
            models.db.session.commit()
            response = client.get(url_for('strequelistan.index'))
            text = response.get_data(as_text=True)
            assert 'Monty Python' not in text
            assert 'Black Knight' in text


class TestGroups():
    def test_group_show_up_on_index_page(self, client):
        """Tests that a group with members shows up on the index page"""
        group = models.Group(
            name="Knights who say Ni",
            weight=1000
        )

        models.db.session.add(group)
        models.db.session.commit()

        with logged_in(client):
            current_user.group=group
            models.db.session.commit()
            response = client.get(url_for('strequelistan.index'))
            text = response.get_data(as_text=True)
            assert group.name in text

    def test_empty_group_hidden_on_index_page(self, client):
        """Tests that a group without members is hidden on the index page"""
        group = models.Group(
            name="Knights who say Ni!",
            weight=1000
        )

        models.db.session.add(group)
        models.db.session.commit()

        with logged_in(client):
            response = client.get(url_for('strequelistan.index'))
            text = response.get_data(as_text=True)
            assert group.name not in text


class TestQuotes():
    def test_empty_quotes(self, client):
        """Test with blank database"""
        with logged_in(client):
            response = client.get(url_for('quotes.index'))
            text = response.get_data(as_text=True)

            assert 'No quotes yet!' in text

    def test_index_no_quotes(self, client):
        """Test that the index page works without quotes"""
        with logged_in(client):
            response = client.get(url_for('strequelistan.index'))
            text = response.get_data(as_text=True)

            assert 'permalänk' not in text

    def test_quote_on_index_page(self, client):
        """Test that a quote shows up on the index page"""
        quote = models.Quote(
            text="And now for something completely different.",
            who="Newsreader [John Cleese]"
        )
        models.db.session.add(quote)
        models.db.session.commit()

        with logged_in(client):
            response = client.get(url_for('strequelistan.index'))
            text = response.get_data(as_text=True)

            # Check if the quote text is present
            assert quote.text in text

            # Check if the person who said the quote is present
            assert quote.who in text


class TestStrequa():
    """Test views related to the strequa action"""

    def test_strequa_json(self, client):
        article = models.Article(
            weight=1,
            name='Holy Grail',
            value=10000,
            description="Difficult to find. Watch out for the rabbit.",
            standardglas=2,
            is_active=True
        )

        models.db.session.add(article)
        models.db.session.commit()

        with logged_in(client):
            response = client.post(
                url_for('strequelistan.add_streque'),
                json={
                    'user_id': current_user.id,
                    'article_id': article.id
                }
            )

            assert response.json.get('user_id') == current_user.id
            assert response.json.get('value') == -article.value
            assert current_user.balance == -article.value
            assert current_user.transactions[0].text == 'Holy Grail'

    def test_strequa_form(self, client):
        article = models.Article(
            weight=1,
            name='Holy Grail',
            value=10000,
            description="Difficult to find. Watch out for the rabbit.",
            standardglas=2,
            is_active=True
        )

        models.db.session.add(article)
        models.db.session.commit()

        with logged_in(client):
            response = client.post(
                url_for('strequelistan.add_streque'),
                json={
                    'user_id': current_user.id,
                    'article_id': article.id
                }
            )

            assert response.json.get('user_id') == current_user.id
            assert response.json.get('value') == -article.value
            assert current_user.balance == -article.value
            assert current_user.transactions[0].text == 'Holy Grail'


class TestProfilePage:
    """Tests for the profile page"""
    pass


class TestHistoryPage:
    """Tests for the transaction history page"""
    pass


class TestMorePage:
    """Tests for the 'More' page"""
    pass
