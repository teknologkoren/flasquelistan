import os

DEBUG = True
SECRET_KEY = 'super secret secret'

BASEDIR = os.path.abspath(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASEDIR, 'db.sqlite')

# FSADeprecationWarning: SQLALCHEMY_TRACK_MODIFICATIONS adds significant
# overhead and will be disabled by default in the future. Set it to
# True or False to suppress this warning.
SQLALCHEMY_TRACK_MODIFICATIONS = False

BABEL_DEFAULT_LOCALE = 'sv'
BABEL_DEFAULT_TIMEZONE = 'CET'
