# settings/production.py
import os
from .base import *

DEBUG = True

# ALLOWED_HOSTS = ['lavaott.com', '164.52.200.90', 'www.lavaott.com']
ALLOWED_HOSTS = ['api.lavaott.com', '164.52.200.90','127.0.0.1', 'lavaott.com', 'www.lavaott.com']

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

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql_psycopg2',
#         'NAME': 'mylava',
#         'USER': 'mylavauser',
#         'PASSWORD': 'mylava@2024',
#         'HOST': 'localhost',
#         'PORT': '',
#     }
# }

CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_HEADERS = [
    'access-control-allow-headers',
    'access-control-allow-methods',
    'access-control-allow-origin',
    'authorization',
    'content-type',
    'xauth',
]

OTP_SEND = True

STATIC_URL = '/lava-static/'
STATIC_ROOT = '/var/backend-static/'
STATIC_FILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_ROOT = '/var/backend-static/media/'
MEDIA_URL = '/lava-media/'


# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'handlers': {
#         'nginx_error_log': {
#             'level': 'DEBUG',
#             'class': 'logging.handlers.WatchedFileHandler',
#             'filename': '/var/log/nginx/error.log',
#         },
#     },
#     'loggers': {
#         'django': {
#             'handlers': ['nginx_error_log'],
#             'level': 'DEBUG',
#             'propagate': True,
#         },
#     },
# }

BY_PASS_VERIFY = False

# SECURE_SSL_REDIRECT = True


# PAYMENT_URL_CONFIG = {
#     'base_url': 'https://api.lavaott.com/',
#     'response_url': 'https://api.lavaott.com/payment/response/',
#     'order_create_url': 'https://api.cachefree.com/v1/orders'
# }
# PAYMENT_CONFIG = {
#     "key_id": '79818249a83e188184b2d75955281897',
#     "key_secret": 'cfsk_ma_prod_728d9c870c640d503eeab6f13973a473_98c07237'
# }
# Production settings
# PAYMENT_URL_CONFIG = {
#     'base_url': 'https://api.lavaott.com/',
#     'response_url': 'https://api.lavaott.com/payment/response/',
#     'sandbox_api_url': 'https://sandbox.cashfree.com/pg/orders',
#     'production_api_url': 'https://api.cashfree.com/pg/orders'
# }



PAYMENT_CONFIG = {
    'key_id': os.getenv('CASHFREE_KEY_ID'),
    'key_secret': os.getenv('CASHFREE_KEY_SECRET'),
}

PAYMENT_URL_CONFIG = {
    'response_url': 'https://api.lavaott.com/payment/response/',
    'webhook_url': 'https://api.lavaott.com/payment/webhook/',
}

