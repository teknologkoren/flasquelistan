#!/usr/bin/env python3

import pytest
from flasquelistan import models
from tests.helpers import app, client, login

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
