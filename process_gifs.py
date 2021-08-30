import pathlib
import ffmpy
from flasquelistan import factory, models, util


def gif_to_webp(in_filename):
    in_path = pathlib.PurePath(in_filename)
    out_path = in_path.with_suffix('.webp')
    ff = ffmpy.FFmpeg(
        inputs={str(in_path): None},
        outputs={str(out_path): '-loop 0'}
    )
    ff.run()
    return out_path


def process_oldest_gif():
    profile_picture = (
        models.ProfilePicture
        .query
        .filter(
            models.ProfilePicture.filename.like("%.gif")
        )
        .order_by(models.ProfilePicture.timestamp)
        .first()
    )
    if not profile_picture:
        return
    path = util.profile_pictures.path(profile_picture.filename)
    print(path)
    new_path = gif_to_webp(path)
    print(new_path)
    profile_picture.filename = new_path.name
    models.db.session.commit()


if __name__ == '__main__':
    app = factory.create_app(instance_config='config.py')
    app.app_context().push()
    process_oldest_gif()
