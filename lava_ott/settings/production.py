# settings/production.py
from .base import *

# PRODUCTION OVERRIDES
DEBUG = False  # Override base.py DEBUG = True

ALLOWED_HOSTS = ['api.lavaott.com', '164.52.200.90', 'lavaott.com', 'www.lavaott.com','127.0.0.1']

# Production Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'lavaproject',
        'USER': 'lavadbuser',
        'PASSWORD': 'lava#dep2024',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# CORS Configuration for Production
CORS_ALLOWED_ORIGINS = [
    "https://api.lavaott.com",
    "https://lavaott.com",
    "https://www.lavaott.com",
]

CORS_ALLOW_HEADERS = [
    'access-control-allow-headers',
    'access-control-allow-methods',
    'access-control-allow-origin',
    'authorization',
    'content-type',
    'xauth',
]

# Production Security Settings
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Session Security
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Static Files for Production
STATIC_URL = '/lava-static/'
STATIC_ROOT = '/var/backend-static/'
STATIC_FILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_ROOT = '/var/backend-static/media/'
MEDIA_URL = '/lava-media/'

# Override OTP bypass for production
BY_PASS_VERIFY = False

# Payment URLs for Production (override base.py URLs)
PAYMENT_URL_CONFIG = {
    'base_url': 'https://api.lavaott.com/',
    'response_url': 'https://api.lavaott.com/payment/response/',
    'webhook_url': 'https://api.lavaott.com/payment/webhook/',
    'sandbox_api_url': 'https://sandbox.cashfree.com/pg/orders',
    'production_api_url': 'https://api.cashfree.com/pg/orders'
}

# Payment config is already perfect in base.py, no need to override

# Simple console logging for now (no file logging issues)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}