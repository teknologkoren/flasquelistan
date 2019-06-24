from pathlib import Path

DEBUG = True
SECRET_KEY = 'super secret secret'

BASEDIR = Path(__file__).parent.resolve()

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + str(BASEDIR.joinpath('db.sqlite'))

# FSADeprecationWarning: SQLALCHEMY_TRACK_MODIFICATIONS adds significant
# overhead and will be disabled by default in the future. Set it to
# True or False to suppress this warning.
SQLALCHEMY_TRACK_MODIFICATIONS = False

BABEL_DEFAULT_LOCALE = 'sv_SE'
BABEL_DEFAULT_TIMEZONE = 'CET'

UPLOADS_DEFAULT_DEST = BASEDIR.joinpath('flasquelistan/static/uploads')
UPLOADS_DEFAULT_URL = '/static/uploads/'

WTF_CSRF_TIME_LIMIT = 21600  # 6 hours

# Email settings
SMTP_MAILSERVER = 'smtp.example.com'
SMTP_STARTTLS_PORT = 587
SMTP_USERNAME = 'webmaster@example.com'
SMTP_PASSWORD = 'smtpsecretpassword'
SMTP_SENDADDR = 'webmaster@example.com'
