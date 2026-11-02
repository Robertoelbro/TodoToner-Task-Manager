# No autodetectar el proyecto: el hook estándar puede copiar db.sqlite3.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
def allowed(name):
    return not any(name.startswith(p) for p in ('django.contrib.gis', 'django.contrib.postgres', 'django.db.backends.postgresql', 'django.db.backends.mysql', 'django.db.backends.oracle'))
datas = collect_data_files('django')
datas += collect_data_files('django', include_py_files=True, includes=['contrib/*/migrations/*.py'])
hiddenimports = collect_submodules('django', filter=allowed, on_error='ignore')
