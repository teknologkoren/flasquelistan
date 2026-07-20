from flasquelistan import models
from tests.helpers import logged_in, logged_in_admin


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

    def test_credit_transfer_creates_notification(self, client):
        """The payee is notified about the transfer with the message."""
        with logged_in(client) as user:
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
            )
            models.db.session.add(payee)
            models.db.session.commit()

            client.post('/transfer', data={
                'payer_id': user.id,
                'payee_id': payee.id,
                'value': '10',
                'message': 'tack för senast',
            })

            notification = models.Notification.query.filter_by(
                type='streque-pay', user_id=payee.id).one()
            assert notification.text.startswith('Streque Pay!')
            assert 'tack för senast' in notification.text

    def test_credit_transfer_from_other_user_rejected(self, client):
        """You can only transfer money from yourself."""
        with logged_in(client):
            payer = models.User(
                email='payer@python.tld',
                first_name='Graham',
                last_name='Chapman',
                balance=1000,
            )
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
            )
            models.db.session.add(payer)
            models.db.session.add(payee)
            models.db.session.commit()

            response = client.post('/transfer', data={
                'payer_id': payer.id,
                'payee_id': payee.id,
                'value': '10',
            })

            assert response.status_code == 302
            assert payer.balance == 1000
            assert payee.balance == 0
            assert models.CreditTransfer.query.count() == 0

    def test_credit_transfer_unknown_user_is_400(self, client):
        """Transfers to or from nonexistent users are rejected."""
        with logged_in(client) as user:
            response = client.post('/transfer', data={
                'payer_id': user.id,
                'payee_id': 4711,
                'value': '10',
            })
            assert response.status_code == 400

    def test_credit_transfer_invalid_value_rejected(self, client):
        """An invalid value does not create a transfer."""
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
                'value': 'not-a-number',
            })

            assert response.status_code == 302
            assert user.balance == 0
            assert payee.balance == 0
            assert models.CreditTransfer.query.count() == 0

    def test_generate_transfer_link(self, client):
        """A Streque Pay link with value and message is generated."""
        with logged_in(client) as user:
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
            )
            models.db.session.add(payee)
            models.db.session.commit()

            response = client.post('/transfer-generate-link', data={
                'payer_id': user.id,
                'payee_id': payee.id,
                'value': '13.37',
                'message': 'middag',
            }, follow_redirects=True)

            assert response.status_code == 200
            page = response.get_data(as_text=True)
            assert f'/profile/{payee.id}/pay' in page
            assert 'value=13.37' in page
            assert 'middag' in page

    def test_transfer_standalone_ignores_invalid_value(self, client):
        """A bogus value query parameter is ignored, not a server error."""
        with logged_in(client):
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
            )
            models.db.session.add(payee)
            models.db.session.commit()

            response = client.get(f'/profile/{payee.id}/pay?value=bogus')
            assert response.status_code == 200

    def test_swish_button_on_standalone_page(self, client):
        """The pay page has a Swish button when the payee has a phone."""
        with logged_in(client):
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
                phone='070-123 45 67',
            )
            models.db.session.add(payee)
            models.db.session.commit()

            response = client.get(f'/profile/{payee.id}/pay')
            page = response.get_data(as_text=True)
            assert 'Swisha istället' in page
            assert 'data-swish-number="+46701234567"' in page
            # The button submits a separate GET form to the Swish app,
            # which works without javascript, with just the number.
            assert 'form="swish-pay-form"' in page
            assert 'action="https://app.swish.nu/1/p/sw/"' in page
            assert 'name="sw" value="+46701234567"' in page
            assert 'js/swishPay.js' in page

    def test_swish_button_disabled_without_phone(self, client):
        """A grayed out Swish button when the payee has no phone number."""
        with logged_in(client):
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
            )
            models.db.session.add(payee)
            models.db.session.commit()

            response = client.get(f'/profile/{payee.id}/pay')
            page = response.get_data(as_text=True)
            assert 'Swisha istället' in page
            assert 'Inget giltigt telefonnummer' in page
            assert 'data-swish-number' not in page
            assert 'app.swish.nu' not in page

    def test_swish_button_with_foreign_phone(self, client):
        """Foreign numbers can have Swish too, the button is shown."""
        with logged_in(client):
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
                phone='+4531123456',  # Danish
            )
            models.db.session.add(payee)
            models.db.session.commit()

            response = client.get(f'/profile/{payee.id}/pay')
            page = response.get_data(as_text=True)
            assert 'Swisha istället' in page
            assert 'data-swish-number="+4531123456"' in page

    def test_swish_button_disabled_with_invalid_phone(self, client):
        """A grayed out Swish button when the payee's phone is not a
        valid number."""
        with logged_in(client):
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
                phone='0710001122',  # Invalid Swedish number
            )
            models.db.session.add(payee)
            models.db.session.commit()

            response = client.get(f'/profile/{payee.id}/pay')
            page = response.get_data(as_text=True)
            assert 'Swisha istället' in page
            assert 'app.swish.nu' not in page

    def test_no_swish_button_on_own_pay_page(self, client):
        """You cannot Swish yourself, so your own pay page has no button."""
        with logged_in(client) as user:
            user.phone = '070-123 45 67'
            models.db.session.commit()

            response = client.get(f'/profile/{user.id}/pay')
            page = response.get_data(as_text=True)
            assert 'Swisha istället' not in page

    def test_swish_button_on_profile_page(self, client):
        """The profile page's Streque Pay form has a Swish button."""
        with logged_in(client):
            payee = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
                phone='070-123 45 67',
            )
            models.db.session.add(payee)
            models.db.session.commit()

            response = client.get(f'/profile/{payee.id}/')
            page = response.get_data(as_text=True)
            assert 'Swisha istället' in page
            assert 'data-swish-number="+46701234567"' in page
            assert 'js/swishPay.js' in page

    def test_no_swish_button_on_own_profile_page(self, client):
        """Your own profile has the link generator form, no Swish button."""
        with logged_in(client) as user:
            user.phone = '070-123 45 67'
            models.db.session.commit()

            response = client.get(f'/profile/{user.id}/')
            page = response.get_data(as_text=True)
            assert 'Swisha istället' not in page

    def test_admin_transaction_requires_admin(self, client):
        """Non-admins may not make admin transactions."""
        with logged_in(client) as user:
            response = client.post(
                f'/profile/{user.id}/admin-transaction',
                data={'value': '10', 'text': 'testing'}
            )
            assert response.status_code == 302
            assert user.balance == 0

    def test_admin_transaction_as_admin(self, client):
        """Admins can adjust a user's balance, which notifies the user."""
        with logged_in_admin(client):
            user = models.User(
                email='payee@python.tld',
                first_name='John',
                last_name='Cleese',
            )
            models.db.session.add(user)
            models.db.session.commit()

            response = client.post(
                f'/profile/{user.id}/admin-transaction',
                data={'value': '10', 'text': 'insättning'}
            )

            assert response.status_code == 302
            assert user.balance == 1000

            notification = models.Notification.query.filter_by(
                type='admintransaction', user_id=user.id).one()
            assert notification.text.startswith('Insättning!')
