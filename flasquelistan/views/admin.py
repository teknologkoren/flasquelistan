import datetime
import flask
import flask_login
import flask_babel
import sqlalchemy as sqla
from flasquelistan import models, forms, util
from flasquelistan.views import auth

mod = flask.Blueprint('strequeadmin', __name__)


@mod.before_request
@flask_login.login_required
@auth.admin_required()
def before_request():
    """Make sure user is logged in before request.
    This function does nothing, but the decorators do.
    """
    pass


@mod.route('/admin/transaktioner/', methods=['GET', 'POST'])
def transactions():
    form = forms.DateRangeForm()

    if form.validate_on_submit():
        from_date = form.start.data
        to_date = form.end.data

        return flask.redirect(flask.url_for('strequeadmin.transactions',
                                            from_date=from_date,
                                            to_date=to_date))
    elif form.is_submitted():
        forms.flash_errors(form)

    from_date = flask.request.args.get('from_date', None)
    to_date = flask.request.args.get('to_date', None)

    if from_date and to_date:
        try:
            from_date = datetime.date.fromisoformat(from_date)
            to_date = datetime.date.fromisoformat(to_date)
        except ValueError:
            flask.flash("Ogiltigt datumintervall!", 'error')
            from_date, to_date = None, None

    if not (from_date and to_date):
        to_date = datetime.date.today()
        from_date = to_date - datetime.timedelta(days=30)

    form.start.data = from_date
    form.end.data = to_date

    transactions = models.Transaction.query.filter(
        sqla.func.DATE(models.Transaction.timestamp) >= from_date,
        sqla.func.DATE(models.Transaction.timestamp) <= to_date,
    ).order_by(models.Transaction.timestamp.desc())

    return flask.render_template('admin/transactions.html',
                                 transactions=transactions,
                                 form=form)


@mod.route('/admin/transaktioner/void', methods=['POST'])
def void_transaction():
    if flask.request.is_json:
        data = flask.request.get_json()
    else:
        data = flask.request.args

    try:
        transaction_id = data['transaction_id']
    except (KeyError, TypeError):
        flask.abort(400)

    transaction = models.Transaction.query.get(transaction_id)

    if not transaction or transaction.voided:
        flask.abort(400)

    transaction.void_and_refund()

    if flask.request.is_json:
        return flask.jsonify(
            transaction_id=transaction.id,
            user_id=transaction.user.id,
            value=transaction.value,
            balance=transaction.user.balance
        )

    else:
        flask.flash("Ångrade {type} \"{text}\", {value} den {date} på {user}."
                    .format(
                        type=transaction.type,
                        text=transaction.text,
                        value=transaction.formatted_value,
                        date=flask_babel.format_datetime(
                            transaction.timestamp,
                            "dd MMMM yyyy, HH:mm"
                        ),
                        user=transaction.user.full_name,
                    ), 'success')
        return flask.redirect(flask.url_for('strequeadmin.transactions'))


@mod.route('/admin/transaktioner/bulk', methods=['GET', 'POST'])
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
                        'value': int(form_field.value.data*100),
                        'text': form_field.text.data or 'Admintransaktion'
                    })

        if transactions:
            return flask.render_template(
                'admin/confirm_bulk_transactions.html',
                transactions=transactions)
        else:
            flask.flash("Inga transaktioner utförda. "
                        "Väl spenderade klockcykler, bra jobbat!", 'info')

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.render_template('admin/bulk_transactions.html', form=form)


@mod.route('/admin/transaktioner/bulk/confirm', methods=['POST'])
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
        user.admin_transaction(transaction['value'], transaction['text'])

    flask.flash("Transaktionerna utfördes!", 'success')
    return flask.redirect(flask.url_for('strequeadmin.bulk_transactions'))


@mod.route('/admin/produkter/')
def articles():
    articles = models.Article.query.order_by(models.Article.weight).all()
    return flask.render_template('admin/articles.html', articles=articles)


@mod.route('/admin/produkter/new', methods=['GET', 'POST'])
@mod.route('/admin/produkter/edit/<int:article_id>', methods=['GET', 'POST'])
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

        article.name = form.name.data
        article.value = int(form.value.data * 100)
        article.description = form.description.data
        article.weight = form.weight.data
        article.standardglas = form.standardglas.data

        if not article_id:
            models.db.session.add(article)

        models.db.session.commit()

        flask.flash("Produkt \"{}\" skapad.".format(article.name), 'success')

        return flask.redirect(flask.url_for('strequeadmin.articles'))

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.render_template('admin/edit_article.html', form=form,
                                 article=article)


@mod.route('/admin/produkter/ta-bort/<int:article_id>', methods=['POST'])
def remove_article(article_id):
    article = models.Article.query.get_or_404(article_id)

    models.db.session.delete(article)
    models.db.session.commit()

    flask.flash("Produkt \"{}\" borttagen.".format(article.name), 'success')
    return flask.redirect(flask.url_for('strequeadmin.articles'))


@mod.route('/admin/spam', methods=['GET', 'POST'])
def spam():
    users = (models.User.query
             .order_by(models.User.first_name)
             .filter(models.User.balance < 0))

    if flask.request.method == 'POST':
        subject = "Hälsning från QM"
        for user in users:
            mail = flask.render_template('admin/negative_balance_mail.jinja2',
                                         user=user)
            util.send_email(user.email, subject, mail)

        flask.flash("Spammade {} personer!".format(users.count()), 'success')

    return flask.render_template('admin/spam.html', users=users)


@mod.route('/admin/add-user/', methods=['GET', 'POST'])
@mod.route('/admin/add-user/request/<int:request_id>', methods=['GET', 'POST'])
def add_user(request_id=None):
    request = (models.RegistrationRequest.query.get_or_404(request_id)
               if request_id else None)

    form = forms.AddUserForm(obj=request, group_id=-1)

    form.group_id.choices = [(g.id, g.name) for g in models.Group.query]
    form.group_id.choices.insert(0, (-1, 'Ingen'))

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
            flask.flash("{} skapad och förfrågan borttagen!".format(user),
                        'success')
            return flask.redirect(flask.url_for('strequeadmin.requests'))

        else:
            flask.flash("{} skapad!".format(user), 'success')
            # Redirect to clear form
            return flask.redirect(flask.url_for('strequeadmin.add_user'))

    elif form.is_submitted():
        forms.flash_errors(form)

    return flask.render_template('admin/add_user.html', form=form,
                                 is_request=bool(request_id))


@mod.route('/admin/users')
def show_users():
    users = models.User.query.all()
    return flask.render_template('admin/users.html', users=users)


@mod.route('/admin/requests/')
def requests():
    requests = models.RegistrationRequest.query

    return flask.render_template('admin/requests.html', requests=requests)


@mod.route('/admin/requests/remove/<int:request_id>', methods=['POST'])
def remove_request(request_id):
    request = models.RegistrationRequest.query.get_or_404(request_id)
    models.db.session.delete(request)
    models.db.session.commit()

    flask.flash("Förfrågan från {} {} borttagen.".format(request.first_name,
                                                         request.last_name),
                'success')

    return flask.redirect(flask.url_for('strequeadmin.requests'))
