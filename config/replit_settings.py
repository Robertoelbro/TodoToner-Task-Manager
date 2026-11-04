"""Configuración de Replit; Vercel sigue utilizando config.settings."""
from urllib.parse import urlsplit
from .settings import *

if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('Replit requiere DATABASE_URL con PostgreSQL.')

DEBUG = False
for domain in [os.environ.get('REPLIT_DEV_DOMAIN', ''),
               *os.environ.get('REPLIT_DOMAINS', '').split(',')]:
    host = urlsplit('//' + domain.strip()).hostname
    if host:
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)
        origin = 'https://' + host
        if origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
MIDDLEWARE = [*MIDDLEWARE]
MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
                  'whitenoise.middleware.WhiteNoiseMiddleware')
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
DATABASES['default']['CONN_MAX_AGE'] = 0
DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
