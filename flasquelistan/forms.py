import flask
import flask_wtf
from flask_wtf.file import FileAllowed
from wtforms import fields, validators
import wtforms.fields.html5 as html5_fields
from flasquelistan import models, util


def flash_errors(form):
    """Flash all errors in a form."""
    for field in form:
        if isinstance(field, (fields.FormField, fields.FieldList)):
            flash_errors(field)
            continue

        for error in field.errors:
            flask.flash(("Fel i fältet \"{}\": {}"
                         .format(field.label.text, error)),
                        'error')


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
        if valuelist:
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
        Exists(models.User,
               models.User.email,
               message='Okänd e-postadress.')
    ])


class UniqueEmailForm(flask_wtf.FlaskForm):
    email = LowercaseEmailField('E-post', validators=[
        validators.InputRequired(),
        validators.Email(),
        Unique(models.User,
               models.User.email,
               message='Denna e-postadress används redan.')
    ])


class PasswordForm(flask_wtf.FlaskForm):
    password = fields.PasswordField(
        'Lösenord',
        validators=[validators.InputRequired()],
        description="Ditt nuvarande lösenord."
    )


class NewPasswordForm(flask_wtf.FlaskForm):
    new_password = fields.PasswordField(
        'Nytt lösenord',
        validators=[validators.InputRequired(), validators.Length(min=8)],
        description="Ditt nya lösenord. Åtminstone 8 tecken långt."
    )


class LoginForm(RedirectForm, EmailForm, PasswordForm):
    remember = fields.BooleanField("Håll mig inloggad")

    def validate(self):
        if not flask_wtf.FlaskForm.validate(self):
            return False

        user = models.User.authenticate(self.email.data, self.password.data)

        if not user:
            return False

        self.user = user
        return True


class AddUserForm(UniqueEmailForm):
    first_name = fields.StringField('Förnamn', validators=[
        validators.InputRequired()
    ])

    last_name = fields.StringField('Efternamn', validators=[
        validators.InputRequired()
    ])

    phone = html5_fields.TelField('Telefon')

    group = fields.SelectField('Grupp')


class ChangeEmailOrPasswordForm(EmailForm, PasswordForm):
    new_password = fields.PasswordField(
        'Nytt lösenord',
        validators=[validators.Optional(), validators.Length(min=8)],
        description="Ditt nya lösenord. Åtminstone 8 tecken långt."
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def validate_email(self, field):
        if models.User.query.filter_by(email=field.data).scalar():
            if field.data != self.user.email:
                self.email.errors.append("Denna e-postadress används redan.")
                return False

        return True

    def validate_password(self, field):
        if not self.user.verify_password(self.password.data):
            self.password.errors.append("Fel lösenord.")
            return False


class EditUserForm(flask_wtf.FlaskForm):
    nickname = fields.StringField('Smeknamn', description="Något roligt.")

    phone = html5_fields.TelField(
        'Telefon',
        description="Ett telefonnummer, med eller utan landskod."
    )


class FullEditUserForm(EditUserForm):
    first_name = fields.StringField(
        'Förnamn',
        validators=[validators.InputRequired()],
        description="Användarens förnamn."
    )

    last_name = fields.StringField(
        'Efternamn',
        validators=[validators.InputRequired()],
        description="Användarens efternamn/familjenamn."
    )


class QuoteForm(flask_wtf.FlaskForm):
    text = fields.TextAreaField('Citat', validators=[
        validators.InputRequired(),
        validators.Length(max=150)
    ])
    who = fields.StringField('Upphovsman', validators=[
        validators.Length(max=150)
    ])


def ChangeProfilePictureFormFactory(user):
    class ChangeProfilePictureForm(flask_wtf.FlaskForm):
        choices = [('none', 'Ingen')]
        default = None

        for pic in user.profile_pictures:
            if pic == user.profile_picture:
                default = str(pic.id)

            choices.append((str(pic.id), pic.filename))

        profile_picture = fields.RadioField(choices=choices,
                                            default=default or 'none')

    return ChangeProfilePictureForm()


class UploadProfilePictureForm(flask_wtf.FlaskForm):
    upload = fields.FileField('Profilbild', validators=[
        FileAllowed(util.image_uploads, 'Endast bilder!')
    ])


class DateRangeForm(flask_wtf.FlaskForm):
    start = html5_fields.DateField('Från', validators=[
        validators.InputRequired()
    ])
    end = html5_fields.DateField('Till', validators=[
        validators.InputRequired()
    ])
