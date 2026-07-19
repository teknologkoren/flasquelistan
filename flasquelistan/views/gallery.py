import flask
from flask_login import login_required

from flasquelistan import models

mod = flask.Blueprint('gallery', __name__)
mod.before_request(login_required(lambda: None))


def gallery_page_for_image(image, user=None):
    images = (
        models.ProfilePicture
        .query
        .order_by(models.ProfilePicture.timestamp.desc())
    )

    if user:
        images = images.filter(models.ProfilePicture.user_id.is_(user.id))

    pagination = images.paginate(per_page=20)

    if not pagination.has_next:
        return pagination.page

    while pagination.has_next:
        pagination = pagination.next()
        if image in pagination.items:
            return pagination.page

    return None


@mod.route('/gallery/')
@mod.route('/gallery/<int:page>/')
def gallery(page=1):
    image_query = (
        models.ProfilePicture
        .query
        .order_by(models.ProfilePicture.timestamp.desc())
        .paginate(
            page=page,
            per_page=20
        )
    )

    return flask.render_template(
        'gallery.html',
        images=image_query.items,
        page=page,
        has_prev=image_query.has_prev,
        has_next=image_query.has_next,
        last_page=image_query.pages,
    )


@mod.route('/gallery/user/<int:user_id>/')
@mod.route('/gallery/user/<int:user_id>/<int:page>')
def user_gallery(user_id, page=1):
    user = models.db.get_or_404(models.User, user_id)

    image_query = (
        models.ProfilePicture
        .query
        .filter(
            models.ProfilePicture.user_id.is_(user.id)
        )
        .order_by(models.ProfilePicture.timestamp.desc())
        .paginate(
            page=page,
            per_page=20,
        )
    )

    return flask.render_template(
        'user_gallery.html',
        user=user,
        images=image_query.items,
        page=page,
        has_prev=image_query.has_prev,
        has_next=image_query.has_next,
        last_page=image_query.pages,
    )
