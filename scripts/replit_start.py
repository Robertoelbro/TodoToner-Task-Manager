"""Arranque de Preview; el despliegue requiere su propio secreto y migraciones."""
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.replit_settings')
published = os.environ.get('REPLIT_DEPLOYMENT') == '1'
if not os.environ.get('DATABASE_URL'):
    raise SystemExit('Falta DATABASE_URL. Revisa la base de Replit antes de iniciar.')
if published and not os.environ.get('DJANGO_SECRET_KEY'):
    raise SystemExit('Configura DJANGO_SECRET_KEY en los Secrets de publicación.')
if not os.environ.get('DJANGO_SECRET_KEY') and not (ROOT / '.env').exists():
    with (ROOT / '.env').open('x', encoding='utf-8') as handle:
        handle.write('DJANGO_SECRET_KEY=' + secrets.token_urlsafe(64) + chr(10) + 'DJANGO_DEBUG=False' + chr(10))
    (ROOT / '.env').chmod(0o600)

import django
django.setup()
from django.core.management import call_command

call_command('check')
if not published:
    call_command('migrate', interactive=False)
call_command('collectstatic', interactive=False, verbosity=0)
port = int(os.environ.get('PORT', '5000'))
os.execv(sys.executable, [sys.executable, '-m', 'gunicorn', 'config.wsgi:application',
         '--bind', f'0.0.0.0:{port}', '--workers', '1', '--threads', '4',
         '--timeout', '60', '--access-logfile', '-', '--error-logfile', '-'])
