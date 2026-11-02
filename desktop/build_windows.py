"""Construcción reproducible de la copia Windows sin datos ni credenciales."""
import argparse, json, os, subprocess, sys
from pathlib import Path

def main():
    if sys.platform != 'win32': raise SystemExit('Construye este ejecutable desde Windows x64 con Python 3.12.')
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, default=root/'dist'); args=parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    work = root/'build'; (work/'tmp').mkdir(parents=True,exist_ok=True)
    env = os.environ.copy()
    env.update(TEMP=str(work/'tmp'), TMP=str(work/'tmp'), PYINSTALLER_CONFIG_DIR=str(work/'cache'),
               DJANGO_SETTINGS_MODULE='desktop.local_settings', DJANGO_SECRET_KEY='build-only-not-a-runtime-secret',
               DJANGO_DEBUG='False', TODOTONER_DATA_DIR=str(work/'empty-data'), DATABASE_URL='sqlite:///:memory:')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--distpath',str(output),'--workpath',str(work/'pyinstaller'),str(root/'desktop/TodoToner.spec')],cwd=root,env=env,check=True)
    app=output/'TodoToner'
    forbidden=[str(p.relative_to(app)) for p in app.rglob('*') if p.is_file() and (p.name in ('.env','secret.key') or p.suffix=='.sqlite3' or 'backups' in p.relative_to(app).parts)]
    if forbidden: raise SystemExit('Entrega cancelada por archivos privados: '+str(forbidden))
    report=output/'verificacion-ejecutable.json'
    subprocess.run([str(app/'TodoToner.exe'),'--self-test','--report',str(report)],cwd=output,env=env,check=True,timeout=120)
    if not json.loads(report.read_text(encoding='utf-8'))['ok']: raise SystemExit('Falló la verificación del ejecutable.')
    print('Ejecutable verificado:',app/'TodoToner.exe')
if __name__=='__main__': main()
