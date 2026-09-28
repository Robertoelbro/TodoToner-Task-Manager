# Turno

Aplicación web responsive para asignar tareas a trabajadores y consultar sus fechas límite y responsables.

## Implementado

- Registro, inicio y cierre de sesión con autenticación de Django.
- Usuario propio desde la primera migración, con casilla booleana `is_supervisor`.
- Usuario base: crea tareas y las asigna inicialmente a una o más personas activas. Consulta las que creó y las que tiene asignadas.
- Supervisor: conserva las funciones base, ve las tareas de todos los usuarios y puede cambiar sus responsables.
- Solo el supervisor puede reasignar, incluso si el creador de la tarea es un usuario base.
- Historial de asignaciones con actor, fecha, responsables anteriores y nuevos.
- Dashboard por trabajador, incluidos usuarios sin tareas e inactivos identificados.
- Fecha límite inclusiva: vence al terminar el día indicado, en America/Santiago.
- Registro público siempre crea usuarios base. No permite otorgarse privilegios.
- El tercer perfil y GeoVictoria quedan pendientes.

El usuario supervisor no equivale al superusuario técnico de Django. No requiere acceso al panel administrativo. El superusuario gestiona las cuentas; para usar las funciones de supervisor en la aplicación también debe tener marcada esa casilla.

## Tecnologías y alcance

Python 3.12, Django 5.2 LTS, django-environ y psycopg 3.
Se usa SQLite para desarrollo local; PostgreSQL queda preparado mediante DATABASE_URL.
La interfaz utiliza templates y CSS responsive local, sin dependencias CDN.
Bootstrap y HTMX quedan pendientes; el dashboard actual se actualiza al recargar la página.
No se han implementado todavía estados de avance/finalización, edición de contenido o eliminación de tareas, recuperación de contraseña, verificación de correo ni GeoVictoria. Las etiquetas Dentro/Fuera de plazo comparan fechas, no progreso.

## Instalación en Windows

Abrir PowerShell en la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copiar la clave generada al campo DJANGO_SECRET_KEY de .env. No sobrescribir un .env existente.
En el equipo original el entorno y .env ya están creados, con una clave aleatoria local.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Abrir http://127.0.0.1:8000 y utilizar Crear cuenta.
El login utiliza el nombre de usuario, no el correo.
El servidor de desarrollo se detiene con Ctrl+C y no debe utilizarse en producción.

Activar el entorno es opcional:

```powershell
.\.venv\Scripts\Activate.ps1
```

El .venv original usa Python 3.12 incluido con las herramientas locales. Si cambia esa instalación o se mueve el proyecto, recrear .venv con una instalación propia de Python 3.12.

## Habilitar supervisores

Crear un administrador técnico con contraseña elegida por quien ejecute el comando:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Entrar a http://127.0.0.1:8000/admin/, abrir Usuarios, seleccionar la cuenta y marcar **Es supervisor** en la sección Turno.
No hay cuentas ni contraseñas predeterminadas. Los permisos de administración de usuarios están restringidos al superusuario técnico.

## Configuración

- DJANGO_SECRET_KEY: obligatoria, fuera de Git.
- DJANGO_DEBUG: True solo para desarrollo local.
- DJANGO_ALLOWED_HOSTS: nombres del servidor; no son IP de clientes autorizados.
- DATABASE_URL: opcional en desarrollo; si falta se utiliza db.sqlite3.
- Para PostgreSQL: configurar DATABASE_URL con los datos reales y ejecutar migrate. El servidor y la base deben existir previamente. Cambiar la URL no transfiere los datos de SQLite.
- Con DEBUG=False se exigen cookies seguras y redirección HTTPS. El despliegue requiere configurar servidor HTTPS, archivos estáticos, respaldos y red con TI.

El registro actual es abierto para quien alcance la aplicación. Antes de habilitar acceso empresarial se debe acordar si será por invitación/aprobación, configurar límites de intentos de login y completar el despliegue de producción.

## Verificación

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Las pruebas cubren registro sin elevación de privilegios, contraseñas, login/logout, cuentas inactivas, redirecciones, asignación múltiple, fechas inválidas, acceso a tareas, permisos de supervisor, historial y CSRF.
Se ejecutan en una base de pruebas separada; no crean usuarios de prueba en la base local.

## Estructura

- accounts/: usuario, registro y administración.
- tasks/: tareas, formularios, permisos, reasignación transaccional y pruebas.
- config/: configuración y rutas.
- templates/: vistas HTML.
- static/: estilos locales.
- requirements.in: rangos de dependencias directas.
- requirements.txt: versiones exactas instaladas.
- .env.example: ejemplo sin credenciales.

## GitHub privado

El repositorio local está inicializado. En GitHub Desktop agregar esta carpeta y publicar manteniendo **Keep this code private**.
Si ya está vinculado, revisar los cambios, crear un commit y realizar Push.

Antes de confirmar, revisar que .env, .venv, bases de datos y datos de trabajadores no estén incluidos:

```powershell
git status --short
git add .
git diff --cached --stat
git diff --cached
git commit -m "Agregar autenticacion y tareas con permisos de supervisor"
```

No se realizan commits ni publicaciones automáticamente. Mantener el repositorio privado no sustituye los permisos de acceso a la aplicación.
