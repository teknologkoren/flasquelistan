from flask import Blueprint, render_template, abort
import random

from flask_login import login_required
from flasquelistan.models import User, ProfilePicture, db
from flasquelistan import util
from flasquelistan.views.strequelistan import gallery_page_for_image

mod = Blueprint("goofs", __name__)
mod.before_request(login_required(lambda: None))


def init_goof_routes(app):
    """Initialize goof routes with application context"""
    with app.app_context():
        goofs_config = app.config.get("GOOFS_CONFIG", {})

        for goof_id, config in goofs_config.items():
            if config.get("enabled", False):
                goof_type = config.get("type")
                route = config.get("route")

                if goof_type == "random_picture":
                    create_random_picture_route(app, route, config, goof_id)


def create_random_picture_route(app, route, config, goof_id):
    """Create a random picture goof route"""

    def random_picture_view():
        user_id = config.get("user_id")
        if not user_id:
            abort(404)

        user = User.query.get(user_id)
        if not user:
            abort(404)

        # Get all profile pictures for this user
        profile_pictures = ProfilePicture.query.filter_by(user_id=user_id).all()

        if not profile_pictures:
            abort(404)

        # Select a random profile picture
        random_picture = random.choice(profile_pictures)

        # Generate secure URL for the image
        image_url = util.url_for_image(random_picture.filename, "profilepicture")

        # Find which page this image is on in the user gallery
        gallery_page = gallery_page_for_image(random_picture, user)
        
        # Generate URL to user gallery at the specific page with anchor
        from flask import url_for
        if gallery_page:
            gallery_url = url_for("strequelistan.user_gallery", user_id=user_id, page=gallery_page, _anchor=str(random_picture.id))
        else:
            gallery_url = url_for("strequelistan.user_gallery", user_id=user_id, _anchor=str(random_picture.id))

        title = config.get("title", "Random Pictures")

        return render_template(
            "goofs/random_picture.html",
            image_url=image_url,
            gallery_url=gallery_url,
            title=title,
            route_id=goof_id,
        )

    # Create unique endpoint name
    endpoint_name = f"goofs.random_picture_{hash(goof_id) % 10000}"
    app.add_url_rule(route, endpoint_name, random_picture_view)
