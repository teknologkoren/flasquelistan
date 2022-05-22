import logging

from flask import has_request_context, request
from flask_login import current_user


class RequestFormatter(logging.Formatter):
    def format(self, record):
        if has_request_context():
            try:
                if current_user.is_authenticated:
                    user = current_user
                else:
                    user = "not logged in"
            except:  # noqa: E722 (ignore 'bare except' warning)
                # we don't want to crash while formatting the error
                # if the database is unreachable, for example.
                user = "error while getting user"
            record.url = request.url
            record.remote_addr = request.remote_addr
            record.user = user
        else:
            record.url = None
            record.remote_addr = None
            record.user = None

        return super().format(record)


formatter = RequestFormatter(
        '[%(asctime)s] %(remote_addr)s (%(user)s) requested %(url)s\n'
        '%(levelname)s in %(module)s: %(message)s'
)
