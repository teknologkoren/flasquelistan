from werkzeug.datastructures import MultiDict

from flasquelistan import forms, models

from tests.helpers import captcha_answer, make_user


class TestUniqueValidator:
    def test_duplicate_email_rejected(self, app):
        make_user()

        with app.test_request_context('/', method='POST'):
            form = forms.UniqueEmailForm(
                formdata=MultiDict({'email': 'monty@python.tld'})
            )
            assert form.validate() is False
            assert form.email.errors

    def test_unused_email_accepted(self, app):
        make_user()

        with app.test_request_context('/', method='POST'):
            form = forms.UniqueEmailForm(
                formdata=MultiDict({'email': 'brian@pfoj.tld'})
            )
            assert form.validate() is True


class TestUniqueEditValidator:
    def make_api_key(self, user, name):
        api_key = models.ApiKey(name=name, user_id=user.id, is_enabled=True)
        api_key.api_key = models.ApiKey.generate_key()
        models.db.session.add(api_key)
        models.db.session.commit()
        return api_key

    def test_keeping_own_value_allowed(self, app):
        user = make_user()
        api_key = self.make_api_key(user, 'my key')

        with app.test_request_context('/', method='POST'):
            form = forms.EditApiKeyForm(
                obj=api_key,
                formdata=MultiDict({'name': 'my key'})
            )
            assert form.validate() is True

    def test_taking_other_objects_value_rejected(self, app):
        user = make_user()
        self.make_api_key(user, 'first key')
        other = self.make_api_key(user, 'second key')

        with app.test_request_context('/', method='POST'):
            form = forms.EditApiKeyForm(
                obj=other,
                formdata=MultiDict({'name': 'first key'})
            )
            assert form.validate() is False
            assert form.name.errors

    def test_new_unused_value_accepted(self, app):
        user = make_user()
        self.make_api_key(user, 'first key')

        with app.test_request_context('/', method='POST'):
            form = forms.EditApiKeyForm(formdata=MultiDict({'name': 'new key'}))
            assert form.validate() is True


class TestExistsValidator:
    def test_unknown_email_rejected(self, app):
        with app.test_request_context('/', method='POST'):
            form = forms.ExistingEmailForm(
                formdata=MultiDict({'email': 'ghost@python.tld'})
            )
            assert form.validate() is False
            assert form.email.errors

    def test_existing_email_accepted(self, app):
        make_user()

        with app.test_request_context('/', method='POST'):
            form = forms.ExistingEmailForm(
                formdata=MultiDict({'email': 'monty@python.tld'})
            )
            assert form.validate() is True


class TestLowercaseEmailField:
    def test_email_is_lowercased(self, app):
        with app.test_request_context('/', method='POST'):
            form = forms.EmailForm(
                formdata=MultiDict({'email': 'Monty@PYTHON.Tld'})
            )
            assert form.validate() is True
            assert form.email.data == 'monty@python.tld'


class TestAreYouARobotForm:
    def test_correct_answer_validates(self, app):
        with app.test_request_context('/', method='POST'):
            form = forms.AreYouARobotFormFactory(formdata=MultiDict({
                'question': '7',
                'answer': captcha_answer(app, 7),
            }))
            assert form.validate() is True

    def test_wrong_answer_fails(self, app):
        with app.test_request_context('/', method='POST'):
            form = forms.AreYouARobotFormFactory(formdata=MultiDict({
                'question': '7',
                'answer': captcha_answer(app, 8),
            }))
            assert form.validate() is False
            assert form.question.errors

    def test_garbage_answer_fails(self, app):
        with app.test_request_context('/', method='POST'):
            form = forms.AreYouARobotFormFactory(formdata=MultiDict({
                'question': '7',
                'answer': 'not-a-hash',
            }))
            assert form.validate() is False


class TestChangeEmailOrPasswordForm:
    def make_user_with_password(self):
        user = make_user()
        user.password = 'solidsnake'
        models.db.session.commit()
        return user

    def test_correct_current_password_validates(self, app):
        user = self.make_user_with_password()

        with app.test_request_context('/', method='POST'):
            form = forms.ChangeEmailOrPasswordForm(user, formdata=MultiDict({
                'email': 'monty@python.tld',
                'password': 'solidsnake',
                'new_password': 'liquidsnake',
            }))
            assert form.validate() is True

    def test_wrong_current_password_rejected(self, app):
        user = self.make_user_with_password()

        with app.test_request_context('/', method='POST'):
            form = forms.ChangeEmailOrPasswordForm(user, formdata=MultiDict({
                'email': 'monty@python.tld',
                'password': 'wrongpassword',
                'new_password': 'liquidsnake',
            }))
            assert form.validate() is False
            assert form.password.errors

    def test_changing_to_taken_email_rejected(self, app):
        user = self.make_user_with_password()
        make_user(email='brian@pfoj.tld')

        with app.test_request_context('/', method='POST'):
            form = forms.ChangeEmailOrPasswordForm(user, formdata=MultiDict({
                'email': 'brian@pfoj.tld',
                'password': 'solidsnake',
            }))
            assert form.validate() is False
            assert form.email.errors
