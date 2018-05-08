import flask
import flask_wtf
from wtforms import fields, validators
import wtforms.fields.html5 as html5_fields
from flasquelistan import models, util


def flash_errors(form):
    """Flash all errors in a form."""
    for field in form:
        for error in field.errors:
            flask.flash(("Fel i fältet \"{}\": {}"
                        .format(field.label.text, error)),
                        'error')


class QuoteForm(flask_wtf.FlaskForm):
    text = fields.TextAreaField('Citat', validators=[
        validators.InputRequired(),
        validators.Length(max=150)
    ])
    who = fields.StringField('Upphovsman (frivilligt)', validators=[
        validators.Length(max=150)
    ])


class Unique:
    """Validate that field is unique in model."""
    def __init__(self, model, field, message='Detta element existerar redan.'):
        self.model = model
        self.field = field
        self.message = message

    def __call__(self, form, field):
        if (models.db.session.query(self.model)
                .filter(self.field == field.data).scalar()):
            raise validators.ValidationError(self.message)


class Exists:
    """Validate that field is unique in model."""
    def __init__(self, model, field, message='Detta element existerar inte.'):
        self.model = model
        self.field = field
        self.message = message

    def __call__(self, form, field):
        if not (models.db.session.query(self.model)
                .filter(self.field == field.data).scalar()):
            raise validators.ValidationError(self.message)


class RedirectForm(flask_wtf.FlaskForm):
    next = fields.HiddenField()

    def __init__(self, *args, **kwargs):
        flask_wtf.FlaskForm.__init__(self, *args, **kwargs)
        if not self.next.data:
            self.next.data = util.get_redirect_target() or ''

    def redirect(self, endpoint='index', **values):
        if self.next.data and util.is_safe_url(self.next.data):
            return flask.redirect(self.next.data)
        target = util.get_redirect_target()
        return flask.redirect(target or flask.url_for(endpoint, **values))


class LowercaseEmailField(html5_fields.EmailField):
    """Custom field that lowercases input."""
    def process_formdata(self, valuelist):
        valuelist[0] = valuelist[0].lower()
        super().process_formdata(valuelist)


class EmailForm(flask_wtf.FlaskForm):
    email = LowercaseEmailField('E-post', validators=[
        validators.InputRequired(),
        validators.Email()
        ])


class ExistingEmailForm(flask_wtf.FlaskForm):
    email = LowercaseEmailField('E-post', validators=[
        validators.InputRequired(),
        validators.Email(),
        Exists(
            models.User,
            models.User.email,
            message='Okänd e-postadress.')
        ])


class PasswordForm(flask_wtf.FlaskForm):
    password = fields.PasswordField(
        'Lösenord',
        validators=[validators.InputRequired()],
        description="Obligatoriskt: ditt nuvarande lösenord."
        )


class NewPasswordForm(flask_wtf.FlaskForm):
    new_password = fields.PasswordField(
        'New password',
        validators=[validators.InputRequired(), validators.Length(min=8)],
        description=("Obligatoriskt: ditt nya lösenord. "
                     "Åtminstone 8 karaktärer långt.")
        )


class ChangePasswordForm(PasswordForm, NewPasswordForm):
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def validate(self):
        if not flask_wtf.FlaskForm.validate(self):
            return False

        if not self.user.verify_password(self.password.data):
            self.password.errors.append("Fel lösenord.")
            return False

        return True


class LoginForm(RedirectForm, EmailForm, PasswordForm):
    """Get login details."""
    remember = fields.BooleanField("Håll mig inloggad")

    def __init__(self, *args, **kwargs):
        self.user = None
        super().__init__(*args, **kwargs)

    def validate(self):
        if not flask_wtf.FlaskForm.validate(self):
            return False

        user = models.User.authenticate(self.email.data, self.password.data)
        if not user:
            return False

        self.user = user
        return True


class AddUserForm(flask_wtf.FlaskForm):
    first_name = fields.StringField('Förnamn', validators=[
        validators.InputRequired()
        ])

    last_name = fields.StringField('Efternamn', validators=[
        validators.InputRequired()
        ])

    email = LowercaseEmailField('E-post', validators=[
        validators.InputRequired(),
        validators.Email(),
        Unique(
            models.User,
            models.User.email,
            message="Denna e-postadress används redan.")
        ])

    phone = html5_fields.TelField('Telefon', validators=[
        validators.Regexp(r'^\+?[0-9]*$')
        ])

    group = fields.SelectField('Grupp')


class EditUserForm(flask_wtf.FlaskForm):
    email = LowercaseEmailField(
        'E-post',
        validators=[
            validators.InputRequired(),
            validators.Email()
        ],
        description="Obligatoriskt: en giltig e-postadress."
        )

    phone = html5_fields.TelField(
        'Telefon',
        validators=[
            validators.InputRequired(),
            validators.Regexp(r'^\+?[0-9]*$')
        ],
        description="Obligatoriskt: ett telefonnummer, med eller utan landskod"
        )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(obj=user, *args, **kwargs)

    def validate(self):
        if not flask_wtf.FlaskForm.validate(self):
            return False

        if (models.db.session.query(models.User.id)
                .filter_by(email=self.email.data).scalar()):
            if self.email.data != self.user.email:
                self.email.errors.append("Denna e-postadress används redan.")
                return False

        return True


class FullEditUserForm(EditUserForm):
    first_name = fields.StringField(
        'Förnamn',
        validators=[validators.InputRequired()],
        description="Obligatoriskt: användarens förnamn."
        )

    last_name = fields.StringField(
        'Efternamn',
        validators=[validators.InputRequired()],
        description="Obligatoriskt: användarens efternamn/familjenamn."
        )
