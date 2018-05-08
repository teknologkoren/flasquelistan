import flask
import flask_login
from flasquelistan import models, forms

mod = flask.Blueprint('quotes', __name__)


@mod.before_request
@flask_login.login_required
def before_request():
    """Make sure user is logged in before request.
    This function does nothing, but the decorators do.
    """
    pass


@mod.route('/citat', methods=['GET', 'POST'])
def index():
    quotes = models.Quote.query.order_by(models.Quote.timestamp.desc()).all()

    return flask.render_template('quotes.html', quotes=quotes)


@mod.route('/citat/nytt', methods=['GET', 'POST'])
def add_quote():
    form = forms.QuoteForm()
    if form.validate_on_submit():
        quote = models.Quote(text=form.text.data, who=form.who.data)
        models.db.session.add(quote)
        models.db.session.commit()
        flask.flash('Citat tillagt!', 'success')
        return flask.redirect(flask.url_for('.index'))
    else:
        forms.flash_errors(form)

    return flask.render_template('add_quote.html', form=form)


@mod.route('/citat/<int:quote_id>')
def quote(quote_id):
    quote = models.Quote.query.get_or_404(quote_id)

    return flask.render_template('quote.html', quote=quote)
