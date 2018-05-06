import flask
import flask_wtf
import wtforms
from wtforms import validators


def flash_errors(form):
    """Flash all errors in a form."""
    for field in form:
        for error in field.errors:
            flask.flash(("Fel i fältet \"{}\": {}"
                        .format(field.label.text, error)),
                        'error')


class QuoteForm(flask_wtf.FlaskForm):
    text = wtforms.TextAreaField('Citat', validators=[
        validators.InputRequired(),
        validators.Length(max=150)
    ])
    who = wtforms.StringField('Upphovsman (frivilligt)', validators=[
        validators.Length(max=150)
    ])
