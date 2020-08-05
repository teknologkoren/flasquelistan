import flask
import flask_login
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flasquelistan import models, forms
import sqlalchemy as sqla

mod = flask.Blueprint('quotes', __name__)


@mod.before_request
@flask_login.login_required
def before_request():
    """Make sure user is logged in before request.
    This function does nothing, but the decorators do.
    """
    pass


@mod.route('/quotes/', methods=['GET', 'POST'])
def index():
    quotes = models.Quote.query.order_by(models.Quote.timestamp.desc(),
                                         models.Quote.id.desc()).all()
    reaction_items = models.QuoteReactionItem.query.all()
    reaction_counts = (
        models.QuoteReaction.query
        .with_entities(
            models.QuoteReaction.quote_id,
            models.QuoteReaction.reaction,
            sqla.func.count(models.QuoteReaction.quote_id),
            sqla.func.count(models.QuoteReaction.reaction)
        )
        .group_by(
            models.QuoteReaction.quote_id,
            models.QuoteReaction.reaction
        )
    )

    for i in reaction_counts:
        print(i[0], i[1], i[2], i[3])

    return flask.render_template(
        'quotes.html',
        quotes=quotes,
        reactions=reaction_items
    )


@mod.route('/quotes/new', methods=['GET', 'POST'])
def add_quote():
    form = forms.QuoteForm()
    if form.validate_on_submit():
        quote = models.Quote(text=form.text.data, who=form.who.data)
        models.db.session.add(quote)
        models.db.session.commit()
        flask.flash(_l('Citat tillagt!'), 'success')
        return flask.redirect(flask.url_for('.index'))

    return flask.render_template('add_quote.html', form=form)


@mod.route('/quotes/<int:quote_id>')
def quote(quote_id):
    quote = models.Quote.query.get_or_404(quote_id)
    reaction_items = models.QuoteReactionItem.query.all()

    return flask.render_template(
        'quote.html',
        quote=quote,
        reactions=reaction_items
    )


@mod.route('/quotes/<int:quote_id>/react', methods=['POST'])
def add_reaction(quote_id):
    quote = models.Quote.query.get_or_404(quote_id)

    if flask.request.is_json:
        data = flask.request.get_json()
    else:
        data = flask.request.form

    try:
        reaction_id = data['reaction_id']
    except KeyError:
        flask.abort(400)

    reaction_item = models.QuoteReactionItem.query.get_or_404(reaction_id)

    already_reacted = (models.QuoteReaction.query
                       .filter_by(
                           user_id=flask_login.current_user.id,
                           quote_id=quote.id,
                           reaction=reaction_item.item
                       )
                       .scalar()
                       )

    if already_reacted:
        if flask.request.is_json:
            return 204
        else:
            flask.flash("Du har redan reagerat med '{}' på det citatet!"
                        .format(reaction_item.item), 'warning')
            return flask.redirect(flask.url_for('quotes.index'))

    reaction = models.QuoteReaction(
        reaction=reaction_item.item,
        user_id=flask_login.current_user.id,
        quote_id=quote.id
    )
    models.db.session.add(reaction)
    models.db.session.commit()

    if flask.request.is_json:
        return 204
    else:
        flask.flash("Reagerade med '{}'!".format(reaction.reaction), 'success')
        return flask.redirect(flask.url_for('quotes.index'))
