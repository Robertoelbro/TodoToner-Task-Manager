from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
root = Path(SPECPATH).parent
datas = [(str(root/'templates'), 'templates'), (str(root/'static'), 'static'), (str(root/'accounts/migrations'), 'accounts/migrations'), (str(root/'tasks/migrations'), 'tasks/migrations')]
datas += collect_data_files('tzdata')
hidden = collect_submodules('accounts') + collect_submodules('tasks') + collect_submodules('config')
hidden += ['desktop.local_settings', 'waitress', 'django.db.backends.sqlite3', 'django.contrib.staticfiles.handlers']
a = Analysis([str(root/'desktop/launcher.py')], pathex=[str(root)], binaries=[], datas=datas, hiddenimports=hidden, hookspath=[str(root/'desktop/hooks')], excludes=['psycopg', 'psycopg_binary', 'django.contrib.gis', 'django.contrib.postgres', 'django.db.backends.postgresql', 'django.db.backends.mysql', 'django.db.backends.oracle'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='TodoToner', debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='TodoToner')
