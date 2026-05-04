from .base import *  # noqa: F403
from decouple import config
import dj_database_url
import os
import sentry_sdk

# Render injects DATABASE_URL automatically
if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.parse(
            os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            ssl_require=True,
        )
    }
DEBUG = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')

# ── Sentry ───────────────────────────────────────────────────
# Hard-coded list of field names whose values must never be transmitted
# to Sentry. Covers Nigerian DPA personal data (NIN, phone, name) plus
# anything that could identify a farm location or a customer.
_SENTRY_SENSITIVE_KEYS = {
    'nin', 'phone', 'phone_number',
    'email', 'customer_email', 'customer_phone',
    'password', 'secret', 'token', 'api_key',
    'csrfmiddlewaretoken', 'sessionid',
    'geolocation', 'coordinates', 'lat', 'lng', 'latitude', 'longitude',
    'first_name', 'last_name', 'full_name',
    'customer_name', 'contact_person',
}


def _sentry_scrub(obj):
    if isinstance(obj, dict):
        return {
            k: ('[scrubbed]' if k.lower() in _SENTRY_SENSITIVE_KEYS else _sentry_scrub(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_sentry_scrub(item) for item in obj]
    return obj


def _sentry_before_send(event, hint):
    request = event.get('request')
    if request and isinstance(request.get('data'), (dict, list)):
        request['data'] = _sentry_scrub(request['data'])
    if isinstance(event.get('extra'), dict):
        event['extra'] = _sentry_scrub(event['extra'])
    breadcrumbs = event.get('breadcrumbs') or {}
    for crumb in breadcrumbs.get('values', []):
        if isinstance(crumb.get('data'), (dict, list)):
            crumb['data'] = _sentry_scrub(crumb['data'])
    return event


sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    environment=os.environ.get('DJANGO_ENV', 'production'),
    release=os.environ.get('RENDER_GIT_COMMIT') or os.environ.get('GIT_SHA'),
    traces_sample_rate=0.2,
    send_default_pii=False,
    before_send=_sentry_before_send,
)

# ── HTTPS enforcement ─────────────────────────────────────────
SECURE_SSL_REDIRECT             = True
SESSION_COOKIE_SECURE           = True
CSRF_COOKIE_SECURE              = True
SECURE_BROWSER_XSS_FILTER       = True
SECURE_CONTENT_TYPE_NOSNIFF     = True
X_FRAME_OPTIONS                 = 'DENY'

# ── HSTS ─────────────────────────────────────────────────────
SECURE_HSTS_SECONDS             = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
SECURE_HSTS_PRELOAD             = True

# ── Cookies ──────────────────────────────────────────────────
SESSION_COOKIE_HTTPONLY         = True
CSRF_COOKIE_HTTPONLY            = True
SESSION_COOKIE_SAMESITE         = 'Lax'
CSRF_COOKIE_SAMESITE            = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE              = 28800  # 8 hours

# ── Static and media ─────────────────────────────────────────
STATIC_ROOT = BASE_DIR / 'staticfiles'  # noqa: F405
MEDIA_ROOT  = BASE_DIR / 'media'  # noqa: F405

# ── Email (configure via .env in production) ─────────────────
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT          = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL', default='noreply@agriops.io')

# ── Logging ───────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/tmp/agriops.log',
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# ── Site URL ──────────────────────────────────────────────────
SITE_URL = 'https://app.agriops.io'
