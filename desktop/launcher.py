import argparse, json, logging, os, queue, secrets, sqlite3, sys, tempfile, threading, traceback, webbrowser, zipfile
from http.client import HTTPConnection
from pathlib import Path
from datetime import datetime
from contextlib import closing
ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

def configure(folder):
    folder.mkdir(parents=True, exist_ok=True)
    key = folder / 'secret.key'
    try:
        with key.open('x', encoding='ascii') as out: out.write(secrets.token_urlsafe(64))
    except FileExistsError: pass
    os.environ.pop('VERCEL', None)
    os.environ.update(DJANGO_SECRET_KEY=key.read_text().strip(), DJANGO_DEBUG='False', DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1', DATABASE_URL='sqlite:///' + (folder/'plataforma.sqlite3').as_posix(), DJANGO_SETTINGS_MODULE='desktop.local_settings', TODOTONER_DATA_DIR=str(folder))
    logging.basicConfig(filename=folder/'servicio.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')
    import django
    django.setup()

def initialize():
    from django.core.management import call_command
    from django.db import connections
    call_command('migrate', interactive=False, verbosity=0)
    connections.close_all()

def make_server(port=8000):
    from waitress import create_server
    from django.core.wsgi import get_wsgi_application
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    app = StaticFilesHandler(get_wsgi_application())
    try: return create_server(app, host='127.0.0.1', port=port, threads=4)
    except OSError: return create_server(app, host='127.0.0.1', port=0, threads=4)

def stop(server):
    server.close()
    server.task_dispatcher.shutdown()

def backup(folder, target):
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp)/'plataforma.sqlite3'
        with closing(sqlite3.connect(folder/'plataforma.sqlite3')) as source, closing(sqlite3.connect(snapshot)) as dest: source.backup(dest)
        with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as out:
            out.write(snapshot, 'plataforma.sqlite3')
            out.write(folder/'secret.key', 'secret.key')

def self_test(report):
    result = {}
    with tempfile.TemporaryDirectory(prefix='todotoner-test-') as tmp:
        folder = Path(tmp); configure(folder); initialize()
        from django.contrib.auth import get_user_model
        from django.test import Client
        from django.db import connections
        from tasks.models import Zone
        user = get_user_model().objects.create_superuser('prueba', 'prueba@example.invalid', secrets.token_urlsafe(20))
        result['areas'] = list(Zone.objects.values_list('name', flat=True))
        client = Client(HTTP_HOST='localhost'); client.force_login(user)
        result['views'] = {p: client.get(p).status_code for p in ['/', '/dashboard/', '/historial/', '/gantt/', '/usuarios/', '/perfil/', '/tv/', '/tareas/nueva/']}
        server = make_server(0); worker = threading.Thread(target=server.run, daemon=True); worker.start()
        result['http'] = {}
        try:
            for path in ['/login/', '/static/app.css', '/static/people-search.js', '/static/brand/logo.png']:
                with closing(HTTPConnection('127.0.0.1', server.effective_port, timeout=15)) as connection:
                    connection.request('GET', path)
                    response = connection.getresponse()
                    result['http'][path] = response.status
                    response.read()
            backup(folder, folder/'respaldo.zip')
            with zipfile.ZipFile(folder/'respaldo.zip') as archive: result['backup'] = set(archive.namelist()) == {'plataforma.sqlite3', 'secret.key'}
        finally:
            stop(server); worker.join(timeout=5); connections.close_all()
        logging.shutdown()
        result['ok'] = len(result['areas']) == 5 and all(s in (200,302) for s in result['views'].values()) and all(s == 200 for s in result['http'].values()) and result['backup']
    report.parent.mkdir(parents=True, exist_ok=True); report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    return 0 if result['ok'] else 1

def gui(folder):
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    root = tk.Tk(); root.title('Todotoner Task Manager local'); root.geometry('620x375'); root.minsize(580,355)
    events = queue.Queue(); server = None; url = None; lock = None
    frame = ttk.Frame(root, padding=22); frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Todotoner Task Manager', font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(frame, text='Copia local para este equipo', font=('Segoe UI',11)).pack(anchor='w', pady=(4,18))
    status = tk.StringVar(value='Preparando la base de datos local...'); address = tk.StringVar()
    ttk.Label(frame, textvariable=status, wraplength=560).pack(anchor='w')
    ttk.Label(frame, textvariable=address, font=('Segoe UI',11,'bold')).pack(anchor='w', pady=12)
    open_button = ttk.Button(frame, text='Abrir plataforma', state='disabled', command=lambda: webbrowser.open(url) if url else None); open_button.pack(fill='x', pady=4)
    def do_backup():
        target = filedialog.asksaveasfilename(title='Guardar respaldo', defaultextension='.zip', initialfile='Todotoner-respaldo-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip', filetypes=[('ZIP','*.zip')])
        if target:
            try:
                backup(folder, target); messagebox.showinfo('Respaldo guardado', 'Se guardaron la base local y su clave de servidor. Conserva el ZIP en un lugar protegido.')
            except Exception as error:
                logging.exception('Error al respaldar'); messagebox.showerror('No se pudo respaldar', str(error))
    backup_button = ttk.Button(frame, text='Guardar respaldo', state='disabled', command=do_backup); backup_button.pack(fill='x', pady=4)
    ttk.Button(frame, text='Abrir carpeta de datos', command=lambda: os.startfile(folder)).pack(fill='x', pady=4)
    ttk.Label(frame, text='Mantén esta ventana abierta. Al cerrarla se detiene el servicio.\nLa información local es independiente de Vercel y Neon.', wraplength=560).pack(anchor='w', pady=14)
    def setup():
        from django.contrib.auth import get_user_model
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        if get_user_model().objects.exists(): return True
        dialog = tk.Toplevel(root); dialog.title('Crear primera cuenta de gerencia'); dialog.transient(root); dialog.grab_set()
        box = ttk.Frame(dialog, padding=20); box.pack(); values = {}; created = []
        ttk.Label(box,text='Primera instalación', font=('Segoe UI',14,'bold')).grid(row=0,column=0,columnspan=2,sticky='w',pady=8)
        for row,(key,label,value) in enumerate([('username','Usuario','roberto'),('first_name','Nombre','Roberto'),('password','Contraseña',''),('confirmation','Repite la contraseña','')],1):
            ttk.Label(box,text=label).grid(row=row,column=0,sticky='w',padx=(0,12),pady=6)
            values[key] = tk.StringVar(value=value)
            ttk.Entry(box,textvariable=values[key],show='*' if key in ('password','confirmation') else '',width=28).grid(row=row,column=1,pady=6)
        ttk.Label(box,text='Mínimo 5 caracteres. No exige mayúsculas ni símbolos.').grid(row=5,column=0,columnspan=2,pady=8)
        def save():
            username = values['username'].get().strip(); password = values['password'].get()
            if not username or password != values['confirmation'].get():
                messagebox.showerror('Revisa los datos','Ingresa un usuario y dos contraseñas iguales.',parent=dialog); return
            try:
                user = get_user_model()(username=username,first_name=values['first_name'].get().strip(),is_superuser=True,is_staff=True)
                validate_password(password,user); user.set_password(password); user.full_clean(exclude=['password']); user.save()
            except ValidationError as error:
                messagebox.showerror('Revisa los datos','\n'.join(error.messages),parent=dialog); return
            created.append(True); dialog.destroy()
        ttk.Button(box,text='Crear gerencia y abrir plataforma',command=save).grid(row=6,column=0,columnspan=2,sticky='ew',pady=10)
        root.wait_window(dialog); return bool(created)
    def initialize_worker():
        try: configure(folder); initialize(); events.put(('ready',None))
        except Exception: logging.exception('Error al iniciar'); events.put(('error',traceback.format_exc()))
    def poll():
        nonlocal server,url
        try:
            event,payload = events.get_nowait()
            if event == 'ready':
                if setup():
                    try:
                        server = make_server(); url = f'http://127.0.0.1:{server.effective_port}'
                        threading.Thread(target=server.run,daemon=True).start(); address.set(url); status.set('Servicio local en funcionamiento')
                        open_button.config(state='normal'); backup_button.config(state='normal'); webbrowser.open(url)
                    except Exception as error: logging.exception('Error de servidor'); messagebox.showerror('Error',str(error))
                else: status.set('Primera cuenta pendiente. Cierra y vuelve a abrir el programa para crearla.')
            else: status.set('No se pudo iniciar. Revisa datos/servicio.log.'); messagebox.showerror('Error de inicio',payload[-1800:])
        except queue.Empty: pass
        root.after(200,poll)
    def close():
        if server: status.set('Deteniendo...'); root.update_idletasks(); stop(server)
        root.destroy()
    try:
        folder.mkdir(parents=True,exist_ok=True)
        import msvcrt
        lock = (folder/'servicio.lock').open('a+b')
        if lock.tell()==0: lock.write(b'0'); lock.flush()
        lock.seek(0); msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        messagebox.showerror('No se pudo iniciar','Ya existe una instancia abierta o la carpeta no permite escritura. Usa una carpeta propia, como Documentos.')
        root.destroy()
        if lock: lock.close()
        return 1
    root.protocol('WM_DELETE_WINDOW',close); threading.Thread(target=initialize_worker,daemon=True).start(); root.after(200,poll); root.mainloop(); lock.close(); return 0

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--data-dir',type=Path); parser.add_argument('--self-test',action='store_true'); parser.add_argument('--report',type=Path,default=Path('verificacion-local.json')); args=parser.parse_args()
    if args.self_test:
        try: return self_test(args.report.resolve())
        except Exception:
            args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps({'ok':False,'error':traceback.format_exc()},indent=2),encoding='utf-8'); return 1
    folder = Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
    return gui((args.data_dir or folder/'datos').resolve())
if __name__=='__main__': raise SystemExit(main())
