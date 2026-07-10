from flasquelistan import models
from tests.helpers import logged_in


class TestTransferViews:
    def test_transfer_standalone_page(self, client):
        """The standalone Streque Pay page renders for a logged in user."""
        with logged_in(client):
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
            )
            models.db.session.add(payee)
            models.db.session.commit()

            response = client.get(f'/profile/{payee.id}/pay?value=13.37')
            assert response.status_code == 200
            assert 'John Cleese' in response.get_data(as_text=True)

    def test_transfer_standalone_requires_login(self, client):
        """Anonymous users are redirected to the login page."""
        response = client.get('/profile/1/pay')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_credit_transfer(self, client):
        """A credit transfer moves money from payer to payee."""
        with logged_in(client) as user:
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
            )
            models.db.session.add(payee)
            models.db.session.commit()

            response = client.post('/transfer', data={
                'payer_id': user.id,
                'payee_id': payee.id,
                'value': '10',
                'message': 'tack för senast',
            })

            assert response.status_code == 302
            assert payee.balance == 1000
            assert user.balance == -1000

    def test_admin_transaction_requires_admin(self, client):
        """Non-admins may not make admin transactions."""
        with logged_in(client) as user:
            response = client.post(
                f'/profile/{user.id}/admin-transaction',
                data={'value': '10', 'text': 'testing'}
            )
            assert response.status_code == 302
            assert user.balance == 0
