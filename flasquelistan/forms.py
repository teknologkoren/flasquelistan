import flask
import flask_wtf
import random
import hashlib
from flask_wtf.file import FileAllowed
from wtforms import fields, validators
import wtforms.fields.html5 as html5_fields
from flasquelistan import models, util
from flask_babel import lazy_gettext as _l
from flask_babel import gettext as _


def flash_errors(form):
    """Flash all errors in a form."""
    for field in form:
        if isinstance(field, (fields.FormField, fields.FieldList)):
            flash_errors(field)
            continue

        for error in field.errors:
            flask.flash(
                _('Fel i fältet "%(label_text)s": %(error_text)s',
                  label_text=field.label.text,
                  error_text=error),
                'error'
            )


class Unique:
    """Validate that field is unique in model."""
    def __init__(self, model, field,
                 message=_l('Detta element existerar redan.')):
        self.model = model
        self.field = field
        self.message = message

    def __call__(self, form, field):
        if (models.db.session.query(self.model)
                .filter(self.field == field.data).scalar()):
            raise validators.ValidationError(self.message)


class Exists:
    """Validate that field is unique in model."""
    def __init__(self, model, field,
                 message=_('Detta element existerar inte.')):
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


def AreYouARobotFormFactory(*args, **kwargs):
    def make_hash(n):
        s = (flask.current_app.config['SECRET_KEY']+str(n)).encode()
        h = hashlib.sha256(s).hexdigest()
        return h

    class F(flask_wtf.FlaskForm):
        def validate(self):
            if self.answer.data != make_hash(self.question.data):
                errors = list(self.question.errors)
                errors.append(_l("Fel svar."))
                self.question.errors = errors
                self.answer.data = self.answer.default
                return False

            self.answer.data = self.answer.default
            return True

    x, y = random.randint(1, 9), random.randint(1, 9)
    answer = x+y
    ans_hash = make_hash(answer)

    F.question = html5_fields.IntegerField(
        _l("Vad är %(x)d + %(y)d?", x=x, y=y),
        validators=[
            validators.InputRequired()
        ]
    )

    F.answer = fields.HiddenField(default=ans_hash)

    return F(*args, **kwargs)


class LowercaseEmailField(html5_fields.EmailField):
    """Custom field that lowercases input."""
    def process_formdata(self, valuelist):
        if valuelist:
            valuelist[0] = valuelist[0].lower()

        super().process_formdata(valuelist)


class EmailForm(flask_wtf.FlaskForm):
    email = LowercaseEmailField(_l('E-post'), validators=[
        validators.InputRequired(),
        validators.Email(),
        validators.Length(max=254)
    ])


class ExistingEmailForm(flask_wtf.FlaskForm):
    email = LowercaseEmailField(_l('E-post'), validators=[
        validators.InputRequired(),
        validators.Email(),
        Exists(models.User,
               models.User.email,
               message=_('Okänd e-postadress.'))
    ])


class UniqueEmailForm(flask_wtf.FlaskForm):
    email = LowercaseEmailField(_('E-post'), validators=[
        validators.InputRequired(),
        validators.Email(),
        validators.Length(max=254),
        Unique(models.User,
               models.User.email,
               message=_('Denna e-postadress används redan.'))
    ])


class PasswordForm(flask_wtf.FlaskForm):
    password = fields.PasswordField(
        _l('Lösenord'),
        validators=[validators.InputRequired()],
        description=_l("Ditt nuvarande lösenord.")
    )


class NewPasswordForm(flask_wtf.FlaskForm):
    new_password = fields.PasswordField(
        _l('Nytt lösenord'),
        validators=[validators.InputRequired(), validators.Length(min=8)],
        description=_l("Ditt nya lösenord. Åtminstone 8 tecken långt.")
    )


class LoginForm(RedirectForm, EmailForm, PasswordForm):
    remember = fields.BooleanField(_l("Håll mig inloggad"))

    def validate(self):
        if not flask_wtf.FlaskForm.validate(self):
            return False

        user = models.User.authenticate(self.email.data, self.password.data)

        if not user:
            return False

        self.user = user
        return True


class ChangeEmailOrPasswordForm(EmailForm, PasswordForm):
    new_password = fields.PasswordField(
        _l('Nytt lösenord'),
        validators=[validators.Optional(), validators.Length(min=8)],
        description=_l("Ditt nya lösenord. Åtminstone 8 tecken långt.")
    )

    def __init__(self, user, nopasswordvalidation=False, *args, **kwargs):
        self.user = user
        self.nopasswordvalidation = nopasswordvalidation
        super().__init__(*args, **kwargs)

    def validate_email(self, field):
        if models.User.query.filter_by(email=field.data).scalar():
            if field.data != self.user.email:
                self.email.errors.append(
                    _l("Denna e-postadress används redan.")
                )
                return False

        return True

    def validate_password(self, field):
        if not self.user.verify_password(self.password.data):
            if self.nopasswordvalidation:
                return True

            self.password.errors.append(_l("Fel lösenord."))
            return False


class AddStrequeForm(flask_wtf.FlaskForm):
    user_id = fields.HiddenField()
    article_id = fields.HiddenField()


class VoidStrequeForm(flask_wtf.FlaskForm):
    streque_id = fields.HiddenField()


class VoidTransactionForm(flask_wtf.FlaskForm):
    transaction_id = fields.HiddenField()


class EditUserForm(flask_wtf.FlaskForm):
    nickname = fields.StringField(
        _l('Smeknamn'),
        description=_l("Något roligt."),
        validators=[
            validators.Length(max=50)
        ]
    )

    phone = html5_fields.TelField(
        _l('Telefon'),
        description=_l("Ett telefonnummer, med eller utan landskod.")
    )

    body_mass = html5_fields.IntegerField(
        _l('Kroppsvikt'),
        description=_l("Din vikt i kg. Används för att mer precist räkna ut "
                       "alkoholkoncentrationen i blodet. Fältet kan lämnas "
                       "tomt"),
        render_kw={'min': 1, 'max': 20743},
        validators=[
            validators.NumberRange(min=1, max=20743),
            validators.Optional()
        ]
    )

    y_chromosome = fields.SelectField(
        _l('Har du en Y-kromosom?'),
        description=_l("Används för att mer precist räkna ut "
                       "alkoholkoncentrationen i blodet."),
        choices=[
            ('n/a', _l('Vill ej uppge')),
            ('yes', _l('Ja')),
            ('no', _l('Nej'))
        ],
        validators=[
            validators.Optional()
        ]
    )


class FullEditUserForm(EditUserForm):
    first_name = fields.StringField(
        _l('Förnamn'),
        validators=[
            validators.InputRequired(),
            validators.Length(max=50)
        ],
    )
    last_name = fields.StringField(
        _l('Efternamn'),
        validators=[
            validators.InputRequired(),
            validators.Length(max=50)
        ],
    )
    active = fields.BooleanField(
        _l('Aktiv'),
        description=_l("Om medlemmen är aktiv i föreningen.")
    )
    group_id = fields.SelectField(_l('Grupp'), coerce=int)
    # Populate .choices in view!


class AddUserForm(UniqueEmailForm, FullEditUserForm):
    pass


class RegistrationRequestForm(UniqueEmailForm):
    first_name = fields.StringField(
        _l('Förnamn'),
        validators=[
            validators.InputRequired(),
            validators.Length(max=50)
        ],
    )
    last_name = fields.StringField(
        _l('Efternamn'),
        validators=[
            validators.InputRequired(),
            validators.Length(max=50)
        ],
    )
    phone = html5_fields.TelField(
        _l('Telefon'),
        description=_l("Ett telefonnummer, med eller utan landskod.")
    )
    message = fields.TextAreaField(_l('Meddelande till QM'))

    are_you_a_robot = fields.FormField(AreYouARobotFormFactory)


class QuoteForm(flask_wtf.FlaskForm):
    text = fields.TextAreaField(
        _l('Citat'),
        description=_l("Max 150 tecken."),
        validators=[
            validators.InputRequired(),
            validators.Length(max=150)
        ])
    who = fields.StringField(_l('Upphovsman'), validators=[
        validators.Length(max=150)
    ])


def ChangeProfilePictureFormFactory(user):
    class ChangeProfilePictureForm(flask_wtf.FlaskForm):
        choices = [('none', _l('Ingen'))]
        default = None

        pictures = (
            models.ProfilePicture
            .query
            .filter(
                models.ProfilePicture.user_id.is_(user.id)
            )
            .order_by(models.ProfilePicture.timestamp.desc())
        )
        for pic in pictures:
            if pic == user.profile_picture:
                default = str(pic.id)

            choices.append((str(pic.id), pic.filename))

        profile_picture = fields.RadioField(choices=choices,
                                            default=default or 'none')

    return ChangeProfilePictureForm()


class UploadProfilePictureForm(flask_wtf.FlaskForm):
    upload = fields.FileField(_l('Ladda upp ny profilbild'), validators=[
        FileAllowed(util.image_uploads, _l('Endast bilder!'))
    ])


class DateRangeForm(flask_wtf.FlaskForm):
    start = html5_fields.DateField(_l('Från'), validators=[
        validators.InputRequired()
    ])
    end = html5_fields.DateField(_l('Till'), validators=[
        validators.InputRequired()
    ])


class UserTransactionForm(flask_wtf.FlaskForm):
    value = html5_fields.DecimalField(
        _l('Transaktionsvärde'),
        render_kw={'step': .01, 'min': -10000, 'max': 10000},
        validators=[
            validators.NumberRange(min=-10000, max=10000),
        ])

    text = fields.StringField(_l('Meddelande'), validators=[
        validators.Length(max=50)
    ])


def BulkTransactionFormFactory(active=True):
    class BulkTransactionForm(flask_wtf.FlaskForm):
        pass

    query = models.User.query.order_by(models.User.first_name)

    if active:
        query.filter_by(active=True)

    users = query.all()

    for user in users:
        class F(flask_wtf.FlaskForm):
            user_name = fields.HiddenField(_l('Namn'),
                                           default=user.full_name)
            user_id = fields.HiddenField('ID', default=user.id)

            value = html5_fields.DecimalField(
                _l('Transaktionsvärde'),
                render_kw={'step': .01, 'min': -10000, 'max': 10000},
                validators=[
                    validators.NumberRange(min=-10000, max=10000),
                    validators.Optional()
                ])

            text = fields.StringField(_l('Meddelande'), validators=[
                validators.Length(max=50),
            ])

        transaction_form = fields.FormField(F)

        setattr(BulkTransactionForm,
                "user-{}".format(user.id),
                transaction_form)

    return BulkTransactionForm()


class EditArticleForm(flask_wtf.FlaskForm):
    name = fields.StringField(_l('Namn'), validators=[
        validators.InputRequired(),
        validators.Length(max=15)
    ])
    value = html5_fields.DecimalField(
        _l('Pris'),
        default=0,
        render_kw={'step': .01, 'min': -1000, 'max': 1000},
        validators=[
            validators.InputRequired(),
            validators.NumberRange(min=-1000, max=1000),
        ]
    )
    standardglas = html5_fields.DecimalField(
        _l('Standardglas'),
        default=1,
        render_kw={'step': .1},
        validators=[
            validators.InputRequired(),
        ]
    )
    description = fields.TextAreaField(
        _l('Beskrivning'),
        description=_l("Vilka produkter som ingår och/eller beskrivning. "
                       "Markdown.")
    )
    weight = html5_fields.IntegerField(
        _l('Sorteringsvikt'),
        description=_l("Heltal. En högre vikt stiger."),
        validators=[
            validators.InputRequired()
        ]
    )
    is_active = fields.BooleanField(
        _l('Aktiv'),
        description=_l("Produkten är synlig och går att strequa på."),
        default=True
    )


class EditGroupForm(flask_wtf.FlaskForm):
    name = fields.StringField(_l('Namn'), validators=[
        validators.InputRequired(),
        validators.Length(max=50)
    ])
    weight = html5_fields.IntegerField(
        _l('Sorteringsvikt'),
        description=_l("Heltal. En högre vikt stiger."),
        validators=[
            validators.InputRequired()
        ]
    )


class CreditTransferForm(flask_wtf.FlaskForm):
    payer_id = fields.HiddenField()
    payee_id = fields.HiddenField()

    message = fields.StringField(_l('Meddelande'), validators=[
        validators.Length(max=50)
    ])

    value = html5_fields.DecimalField(
        _l('Summa'),
        render_kw={'step': .01, 'min': 1, 'max': 10000},
        validators=[
            validators.NumberRange(min=1, max=10000),
        ]
    )


class EditQuoteForm(flask_wtf.FlaskForm):
    text = fields.TextAreaField(
        _l('Citat'),
        description=_l("Max 150 tecken."),
        validators=[
            validators.InputRequired(),
            validators.Length(max=150)
        ]
    )
    who = fields.TextAreaField(
        _l('Upphovsman'),
        validators=[
            validators.Length(max=150)
        ]
    )
    timestamp = html5_fields.DateTimeLocalField(
        _l('Tid'),
        description=_l("Tidszon UTC."),
        validators=[
            validators.InputRequired()
        ],
        format='%Y-%m-%dT%H:%M'
    )
