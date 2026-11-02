import os
from pathlib import Path
from config.settings import *
DATA_DIR = Path(os.environ['TODOTONER_DATA_DIR'])
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': DATA_DIR / 'plataforma.sqlite3', 'OPTIONS': {'timeout': 30}}}
DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
CSRF_TRUSTED_ORIGINS = []
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_NAME = 'todotoner_local_session'
CSRF_COOKIE_NAME = 'todotoner_local_csrf'
STATIC_ROOT = DATA_DIR / 'staticfiles'
EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
