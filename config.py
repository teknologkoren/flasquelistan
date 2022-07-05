from pathlib import Path

DEBUG = True
SECRET_KEY = 'super secret secret'

SITE_TITLE = "Strequelistan"
DISPLAY_BALANCE_WARNINGS = True

SESSION_COOKIE_SECURE = False  # Change to True in production instance config
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

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
SMTP_PORT = 25
#SMTP_USE_STARTTLS = True
#SMTP_USERNAME = 'webmaster@example.com'
#SMTP_PASSWORD = 'smtpsecretpassword'
SYSTEM_EMAILADDR = 'system-noreply@example.com'
# address to send from and to send admin notifications to
ADMIN_EMAILADDR = 'webmaster@example.com'
