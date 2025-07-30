from .base import *

DEBUG = True

# ALLOWED_HOSTS = ['lavaott.com', '164.52.200.90', 'www.lavaott.com']
ALLOWED_HOSTS = ['api.lavaott.com', '164.52.200.90','127.0.0.1']

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
# Production Cashfree Configuration
PAYMENT_URL_CONFIG = {
    'base_url': 'https://api.lavaott.com/',
    'response_url': 'https://api.lavaott.com/payment/response/',
    'sandbox_api_url': 'https://sandbox.cashfree.com/pg/orders',
    'production_api_url': 'https://api.cashfree.com/pg/orders'
}

PAYMENT_CONFIG = {
    "key_id": '79818249a83e188184b2d75955281897',  # Your Cashfree App ID
    "key_secret": 'cfsk_ma_prod_728d9c870c640d503eeab6f13973a473_98c07237',  # Your Cashfree Secret Key
    "test_mode": False,  # Set to False for production
    "api_version": "2023-08-01"
}

# PAYMENT_CONFIG = {
#     "key_id": 'rzp_live_KNVLFuRdQHF0Lu',
#     "key_secret": 'jCmtb49N4bUK7qnuEsE31a2e'
# }
