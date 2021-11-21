import datetime

import flask
import flask_babel
import flask_login
import sqlalchemy as sqla
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_login import current_user

from flasquelistan import forms, models, util
from flasquelistan.views import auth

mod = flask.Blueprint('strequeadmin', __name__)
mod.before_request(
    flask_login.login_required(
        auth.admin_required(lambda: None)
    )
)


@mod.route('/admin/')
def index():
    return flask.render_template('strequeadmin/index.html')


@mod.route('/admin/transactions/', methods=['GET', 'POST'])
def transactions():
    form = forms.DateRangeForm()

    if form.validate_on_submit():
        from_date = form.start.data
        to_date = form.end.data

        return flask.redirect(flask.url_for('strequeadmin.transactions',
                                            from_date=from_date,
                                            to_date=to_date))

    from_date = flask.request.args.get('from_date', None)
    to_date = flask.request.args.get('to_date', None)

    if from_date and to_date:
        try:
            from_date = datetime.date.fromisoformat(from_date)
            to_date = datetime.date.fromisoformat(to_date)
        except ValueError:
            flask.flash(_l("Ogiltigt datumintervall!"), 'error')
            from_date, to_date = None, None

    if not (from_date and to_date):
        to_date = datetime.date.today()
        from_date = to_date - datetime.timedelta(days=30)

    form.start.data = from_date
    form.end.data = to_date

    transactions = models.Transaction.query.filter(
        sqla.func.DATE(models.Transaction.timestamp) >= from_date,
        sqla.func.DATE(models.Transaction.timestamp) <= to_date,
        sqla.or_(
            # Only include UserTransaction if positive, which means the
            # transaction of the payee. Include 0 too if that somehow
            # would find its way into the database. We'll just hope we
            # don't ever have a CreditTransfer where both sides are
            # negative. That could be fixed in the db admin-interface.
            models.Transaction.type.isnot('user_transaction'),
            models.Transaction.value >= 0
        )
    ).order_by(models.Transaction.timestamp.desc())

    return flask.render_template('strequeadmin/transactions.html',
                                 transactions=transactions,
                                 form=form)


@mod.route('/admin/transactions/stats', methods=['GET', 'POST'])
def streque_stats():
    form = forms.DateRangeForm()

    if form.validate_on_submit():
        from_date = form.start.data
        to_date = form.end.data

        return flask.redirect(flask.url_for('strequeadmin.streque_stats',
                                            from_date=from_date,
                                            to_date=to_date))

    from_date = flask.request.args.get('from_date', None)
    to_date = flask.request.args.get('to_date', None)

    if from_date and to_date:
        try:
            from_date = datetime.date.fromisoformat(from_date)
            to_date = datetime.date.fromisoformat(to_date)
        except ValueError:
            flask.flash(_l("Ogiltigt datumintervall!"), 'error')
            from_date, to_date = None, None

    if not (from_date and to_date):
        to_date = datetime.date.today()
        from_date = to_date - datetime.timedelta(days=1)

    form.start.data = from_date
    form.end.data = to_date

    counts = (
        models.User.query
        .join(models.Streque, models.User.id == models.Streque.user_id)
        .with_entities(
            models.User.first_name,
            models.User.last_name,
            sqla.func.count(models.Streque.user_id).label('count')
        )
        .filter(
            sqla.func.DATE(models.Streque.timestamp) >= from_date,
            sqla.func.DATE(models.Streque.timestamp) <= to_date,
            models.Streque.voided.is_(False)
        )
        .group_by(
            models.Streque.user_id
        )
        .order_by(sqla.desc('count'))
    )

    return flask.render_template('strequeadmin/streque_stats.html',
                                 counts=counts,
                                 form=form)


@mod.route('/admin/transactions/void', methods=['POST'])
def void_transaction():
    if flask.request.is_json:
        data = flask.request.get_json()
    else:
        form = forms.VoidTransactionForm()
        data = {
            'transaction_id': form.transaction_id.data
        }

    try:
        transaction_id = data['transaction_id']
    except (KeyError, TypeError):
        flask.abort(400)

    transaction = models.Transaction.query.get(transaction_id)

    if not transaction or transaction.voided:
        flask.abort(400)

    if transaction.type == 'user_transaction':
        credit_transfer = models.CreditTransfer.query.filter(
            sqla.or_(
                # As we include potential transactions where value is 0
                # (maybe on both sides), we'll search on both sides
                # here.
                models.CreditTransfer.payer_transaction_id.is_(transaction.id),
                models.CreditTransfer.payee_transaction_id.is_(transaction.id),
            )
        ).first()
        credit_transfer.void()
    else:
        transaction.void_and_refund()

    if flask.request.is_json:
        return flask.jsonify(
            transaction_id=transaction.id,
            user_id=transaction.user.id,
            value=transaction.value,
            balance=transaction.user.balance
        )

    else:
        flask.flash(
            _("Ångrade %(type)s \"%(text)s\", "
              "%(value)s den %(date)s på %(user)s.",
              type=transaction.type,
              text=transaction.text,
              value=transaction.formatted_value,
              date=flask_babel.format_datetime(
                  transaction.timestamp,
                  "dd MMMM yyyy, HH:mm"
              ),
              user=transaction.user.full_name
              ),
            'success'
        )
        return flask.redirect(flask.url_for('strequeadmin.transactions'))


@mod.route('/admin/transactions/bulk', methods=['GET', 'POST'])
def bulk_transactions():
    form = forms.BulkTransactionFormFactory(active=False)

    if form.validate_on_submit():
        transactions = []

        for form_field in form:
            if form_field.name == 'csrf_token':
                continue

            if form_field.value.data:
                user = models.User.query.get(form_field.user_id.data)
                if user:
                    transactions.append({
                        'user_id': user.id,
                        'user_name': user.full_name,
                        'value': int(form_field.value.data * 100),
                        'text': form_field.text.data or _l('Admintransaktion')
                    })

        if transactions:
            return flask.render_template(
                'strequeadmin/confirm_bulk_transactions.html',
                transactions=transactions)
        else:
            flask.flash(_l("Inga transaktioner utförda. "
                        "Väl spenderade klockcykler, bra jobbat!"), 'info')

    return flask.render_template('strequeadmin/bulk_transactions.html', form=form)


@mod.route('/admin/transactions/bulk/confirm', methods=['POST'])
def confirm_bulk_transactions():
    form = flask.request.form
    transactions = {}

    for name, value in form.items():
        if not name.startswith('user'):
            continue

        user_id, field = name.split('-')[1:]

        transactions.setdefault(user_id, {})
        if field == 'value':
            transactions[user_id][field] = int(value)
        elif field == 'text':
            transactions[user_id][field] = value
        else:
            flask.abort(400)

    for user_id, transaction in transactions.items():
        user = models.User.query.get(user_id)
        user.admin_transaction(
            transaction['value'],
            transaction['text'],
            by_user=current_user
        )

    flask.flash(_l("Transaktionerna utfördes!"), 'success')
    return flask.redirect(flask.url_for('strequeadmin.bulk_transactions'))


@mod.route('/admin/articles/')
def articles():
    articles = (models.Article
                .query
                .order_by(
                    models.Article.is_active.desc(),
                    models.Article.weight.desc()
                )
                .all()
                )
    return flask.render_template('strequeadmin/articles.html', articles=articles)


@mod.route('/admin/articles/new', methods=['GET', 'POST'])
@mod.route('/admin/articles/edit/<int:article_id>', methods=['GET', 'POST'])
def edit_article(article_id=None):
    if article_id:
        article = models.Article.query.get_or_404(article_id)
        form = forms.EditArticleForm(obj=article)
        if not form.is_submitted():
            form.value.data = form.value.data / 100
    else:
        article = None
        form = forms.EditArticleForm()

    if form.validate_on_submit():
        if not article:
            article = models.Article()
            flash = _l("Produkt \"{}\" skapad.")
        else:
            flash = _("Produkt \"{}\" ändrad.")

        article.name = form.name.data
        article.value = int(form.value.data * 100)
        article.description = form.description.data
        article.weight = form.weight.data
        article.standardglas = form.standardglas.data
        article.is_active = form.is_active.data

        if not article_id:
            models.db.session.add(article)

        models.db.session.commit()

        flask.flash(flash.format(article.name), 'success')

        return flask.redirect(flask.url_for('strequeadmin.articles'))

    return flask.render_template('strequeadmin/edit_article.html', form=form,
                                 article=article)


@mod.route('/admin/articles/remove/<int:article_id>', methods=['POST'])
def remove_article(article_id):
    article = models.Article.query.get_or_404(article_id)

    models.db.session.delete(article)
    models.db.session.commit()

    flask.flash(_l("Produkt \"%(name)s\" borttagen.", name=article.name), 'success')
    return flask.redirect(flask.url_for('strequeadmin.articles'))


@mod.route('/admin/spam', methods=['GET', 'POST'])
def spam():
    users = (models.User.query
             .order_by(models.User.balance.asc())
             .filter(models.User.balance < 0))

    if flask.request.method == 'POST':
        subject = "Hälsning från QM"
        for user in users:
            mail = flask.render_template('strequeadmin/negative_balance_mail.jinja2',
                                         user=user)
            util.send_email(user.email, subject, mail)

        flask.flash(_("Skickade %(nr)i saldopåminnelser!", nr=users.count()),
                    'success')

    return flask.render_template('strequeadmin/spam.html', users=users)


@mod.route('/admin/add-user/', methods=['GET', 'POST'])
@mod.route('/admin/add-user/request/<int:request_id>', methods=['GET', 'POST'])
def add_user(request_id=None):
    request = (models.RegistrationRequest.query.get_or_404(request_id)
               if request_id else None)

    form = forms.AddUserForm(obj=request, group_id=-1)

    form.group_id.choices = [(g.id, g.name) for g in models.Group.query]
    form.group_id.choices.insert(0, (-1, _l('Ingen')))

    if form.validate_on_submit():
        user = models.User(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            nickname=form.nickname.data,
            email=form.email.data,
            phone=form.phone.data,
            active=form.active.data,
            group_id=form.group_id.data if form.group_id.data != -1 else None,
        )

        models.db.session.add(user)
        models.db.session.commit()

        if request:
            models.db.session.delete(request)
            models.db.session.commit()
            flask.flash(_("%(user_name)s skapad och förfrågan borttagen!", user_name=user),
                        'success')
            return flask.redirect(flask.url_for('strequeadmin.requests'))

        else:
            flask.flash(_("%(user_name)s skapad!", user_name=user), 'success')
            # Redirect to clear form
            return flask.redirect(flask.url_for('strequeadmin.add_user'))

    return flask.render_template('strequeadmin/add_user.html', form=form,
                                 is_request=bool(request_id))


@mod.route('/admin/users')
def show_users():
    users = models.User.query.order_by(models.User.first_name.asc()).all()
    return flask.render_template('strequeadmin/users.html', users=users)


@mod.route('/admin/requests/')
def requests():
    requests = models.RegistrationRequest.query

    return flask.render_template('strequeadmin/requests.html', requests=requests)


@mod.route('/admin/requests/remove/<int:request_id>', methods=['POST'])
def remove_request(request_id):
    request = models.RegistrationRequest.query.get_or_404(request_id)
    models.db.session.delete(request)
    models.db.session.commit()

    flask.flash(
        _("Förfrågan från %(first)s %(last)s borttagen.",
          first=request.first_name,
          last=request.last_name),
        'success'
    )

    return flask.redirect(flask.url_for('strequeadmin.requests'))


@mod.route('/admin/groups')
def show_groups():
    groups = models.Group.query.order_by(models.Group.weight.desc()).all()
    return flask.render_template('strequeadmin/groups.html', groups=groups)


@mod.route('/admin/groups/new', methods=['GET', 'POST'])
@mod.route('/admin/groups/edit/<int:group_id>', methods=['GET', 'POST'])
def edit_group(group_id=None):
    if group_id:
        group = models.Group.query.get_or_404(group_id)
        form = forms.EditGroupForm(obj=group)
    else:
        group = None
        form = forms.EditGroupForm()

    if form.validate_on_submit():
        if not group:
            group = models.Group()

        group.name = form.name.data
        group.weight = form.weight.data

        if not group_id:
            models.db.session.add(group)

        models.db.session.commit()

        flask.flash(
            _("Grupp \"%(group_name)s\" skapad.", group_name=group.name),
            'success'
        )

        return flask.redirect(flask.url_for('strequeadmin.show_groups'))

    return flask.render_template('strequeadmin/edit_group.html',
                                 form=form,
                                 group=group)


@mod.route('/admin/groups/remove/<int:group_id>', methods=['POST'])
def remove_group(group_id):
    group = models.Group.query.get_or_404(group_id)

    models.db.session.delete(group)
    models.db.session.commit()

    flask.flash(
        _("Grupp \"%(group_name)s\" borttagen.", group_name=group.name),
        'success'
    )
    return flask.redirect(flask.url_for('strequeadmin.show_groups'))


@mod.route('/admin/quotes/')
def show_quotes():
    quotes = models.Quote.query.order_by(models.Quote.timestamp.desc()).all()
    return flask.render_template('strequeadmin/quotes.html', quotes=quotes)


@mod.route('/admin/quotes/edit/<int:quote_id>', methods=['GET', 'POST'])
def edit_quote(quote_id):
    quote = models.Quote.query.get_or_404(quote_id)
    form = forms.EditQuoteForm(obj=quote)

    if form.validate_on_submit():
        quote.text = form.text.data
        quote.who = form.who.data
        quote.timestamp = form.timestamp.data
        models.db.session.commit()
        flask.flash(_l("Citat har ändrats!"), 'success')

    return flask.render_template('strequeadmin/edit_quote.html',
                                 quote=quote,
                                 form=form)


@mod.route('/admin/quotes/remove/<int:quote_id>', methods=['POST'])
def remove_quote(quote_id):
    quote = models.Quote.query.get_or_404(quote_id)

    models.db.session.delete(quote)
    models.db.session.commit()

    flask.flash(_l("Citat borttaget."), 'success')
    return flask.redirect(flask.url_for('strequeadmin.show_quotes'))


@mod.route('/admin/stats')
def stats():
    positive_balance = (
        models.User.query
        .filter(models.User.balance > 0)
        .order_by(models.User.balance.desc())
    )
    negative_balance = (
        models.User.query
        .filter(models.User.balance < 0)
        .order_by(models.User.balance)
    )
    deposits = sum(user.balance for user in positive_balance)
    loans = sum(user.balance for user in negative_balance)
    return flask.render_template(
        'strequeadmin/stats.html',
        positive_balance=positive_balance,
        negative_balance=negative_balance,
        deposits=deposits,
        loans=loans
    )
