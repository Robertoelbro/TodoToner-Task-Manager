# Turno

Aplicación web responsive para asignar tareas a trabajadores y consultar sus fechas límite y responsables.

## Implementado

- Alta de cuentas por gerencia, primer ingreso obligatorio, inicio y cierre de sesión con Django.
- Usuario propio desde la primera migración, con casilla booleana `is_supervisor`.
- Usuario base: crea tareas y las asigna inicialmente a una o más personas activas. Consulta las que creó y las que tiene asignadas.
- Supervisor: conserva las funciones base, ve las tareas de su equipo (área), las propias y las compartidas. Solo puede gestionar las propias o de su equipo; ser espectador no concede edición.
- Solo el supervisor puede reasignar, incluso si el creador de la tarea es un usuario base.
- Historial de asignaciones con actor, fecha, responsables anteriores y nuevos.
- Dashboard por trabajador, incluidos usuarios sin tareas e inactivos identificados.
- Prioridad, estado y supervisor visibles en tarjetas y detalle.
- Tareas anteriores migradas con prioridad media, estado pendiente y supervisor sin asignar.
- Fecha límite inclusiva: vence al terminar el día indicado, en America/Santiago.
- Registro público cerrado. Gerencia crea usuarios base y puede promoverlos a supervisor o gerencia.
- Gerencia utiliza el superusuario de Django y gestiona usuarios desde una vista propia. GeoVictoria queda pendiente.

Supervisor y gerencia son roles distintos. Gerencia gestiona cuentas y puede supervisar tareas.

## Tecnologías y alcance

Python 3.12, Django 5.2 LTS, django-environ y psycopg 3.
Se usa SQLite para desarrollo local; PostgreSQL queda preparado mediante DATABASE_URL.
La interfaz utiliza templates y CSS responsive local, sin dependencias CDN.
Bootstrap y HTMX quedan pendientes; el dashboard actual se actualiza al recargar la página.
Estados disponibles: pendiente, en proceso, en revisión y finalizada. Los usuarios base pueden cambiar el estado de las tareas que crearon o tienen asignadas, mediante Actualizar estado. Solo supervisores y gerencia pueden modificar prioridad, fechas, zonas y supervisor a cargo mediante Actualizar seguimiento. Todos los cambios efectivos conservan autor y detalle en el historial. Las tareas nuevas comienzan pendientes. El supervisor a cargo es opcional y debe ser un supervisor activo. Las tareas finalizadas no cuentan como fuera de plazo. No se han implementado edición de contenido, eliminación, recuperación de contraseña, verificación de correo ni GeoVictoria.

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

Abrir http://127.0.0.1:8000. Gerencia crea las cuentas desde Usuarios → Crear usuario.
El login utiliza el nombre de usuario, no el correo.
El servidor de desarrollo se detiene con Ctrl+C y no debe utilizarse en producción.

Activar el entorno es opcional:

```powershell
.\.venv\Scripts\Activate.ps1
```

El .venv original usa Python 3.12 incluido con las herramientas locales. Si cambia esa instalación o se mueve el proyecto, recrear .venv con una instalación propia de Python 3.12.

## Gerencia y gestión de usuarios

Gerencia corresponde a is_superuser de Django y también puede supervisar tareas. Crear la primera cuenta gerencial desde terminal:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Iniciar sesión en /login/ y abrir Usuarios (/usuarios/). Gerencia crea cuentas y edita nombre, apellido, correo, área y rol de las cuentas no gerenciales. Puede promoverlas a supervisor o gerencia. Las cuentas gerenciales quedan protegidas contra edición y eliminación desde esta vista. El perfil personal no permite cambiar área ni privilegios.

Django Admin está deshabilitado: no existe la ruta /admin/. Las rutas inexistentes y los intentos sin permiso de acceder a gestión muestran un 404 personalizado sin listar rutas, incluso con DEBUG=True. DEBUG=False sigue siendo necesario en producción para evitar otras páginas técnicas de error.

Las cuentas anteriormente marcadas is_management se convierten a superusuarios mediante migración; ese campo se elimina. Los superusuarios existentes pasan a mostrarse como Gerencia sin cambiar su contraseña. No hay cuentas ni contraseñas predeterminadas.

## Configuración

- DJANGO_SECRET_KEY: obligatoria, fuera de Git.
- DJANGO_DEBUG: True solo para desarrollo local.
- DJANGO_ALLOWED_HOSTS: nombres del servidor; no son IP de clientes autorizados.
- DATABASE_URL: opcional en desarrollo; si falta se utiliza db.sqlite3.
- Para PostgreSQL: configurar DATABASE_URL con los datos reales y ejecutar migrate. El servidor y la base deben existir previamente. Cambiar la URL no transfiere los datos de SQLite.
- Con DEBUG=False se exigen cookies seguras y redirección HTTPS. El despliegue requiere configurar servidor HTTPS, archivos estáticos, respaldos y red con TI.

El registro público está cerrado; solo gerencia da de alta usuarios.

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

## Hub de supervisión y zonas

La portada del supervisor abre /dashboard/ con tareas personales y últimos cambios. El menú /gantt/ contiene el Gantt general y el desglose por Ventas, Postventas y Bodega. Paleta blanca, negra y verde.

Las tareas nuevas requieren fecha de inicio, fecha límite y una o más zonas. Solo supervisores pueden modificar fechas y zonas posteriormente en Actualizar seguimiento. Las tareas compartidas aparecen en cada zona pero se cuentan una vez en el total.

Filtros combinables: zona, trabajador responsable, fechas, prioridad y más de un responsable. Las fechas seleccionan tareas que coincidan total o parcialmente con el intervalo. Los filtros afectan al equipo, no a las tareas personales. Limpiar filtros restaura todas las tareas. El Gantt se desplaza horizontalmente en móvil, admite períodos largos con hasta 90 columnas y sus barras abren el detalle; no se arrastran para editar.

La migración conserva las tareas antiguas: inicio provisional según su creación en Chile, sin superar la fecha límite, y sin zona hasta clasificarlas. Las tres zonas se crean automáticamente mediante migrate. Se guardó un respaldo local previo fuera del repositorio, en work.

Actualizar otra instalación con manage.py migrate. Iniciar el servidor desde VS Code sin --noreload para detectar cambios Python.

## Navegación y últimos cambios

El hub principal /dashboard/ muestra las tareas personales y los últimos 20 cambios del equipo. El usuario base ve los últimos cambios únicamente de tareas que puede consultar. El Gantt tiene su menú independiente en /gantt/, reservado a supervisores.

Aplicar filtros y Limpiar filtros actualizan la sección mediante fetch sin recargar la página. Cambiar un selector por sí solo no consulta al servidor. Se conserva la URL filtrada y la navegación atrás/adelante. Si JavaScript no está disponible, el formulario GET sigue funcionando con navegación normal. Los errores de conexión conservan el contenido previo y permiten reintentar.

Filtros añadidos: supervisor a cargo y estado de tarea. Se combinan con zona, trabajador, fechas, prioridad y múltiples responsables.

Se registran creación, reasignación y cambios de estado, prioridad, supervisor, fechas y zonas, con actor, fecha y valores anteriores/nuevos. Guardar sin cambios no genera un evento. La migración importa las asignaciones históricas conservando sus fechas; no reconstruye cambios de seguimiento anteriores que no se registraban.


## Semáforo de vencimientos y alertas

Cada tarea tiene fecha y hora de inicio y límite, en America/Santiago. Para registros anteriores se conserva la fecha con inicio 00:00:00 y vencimiento 23:59:59. El supervisor puede ajustar ambas horas desde Actualizar seguimiento. Se registran estos cambios en el historial.

- Duración mayor a 24 horas: verde cuando faltan más de 48 h; amarillo entre 24 y 48 h inclusive; rojo cuando faltan menos de 24 h.
- Duración de hasta 24 horas: primer tercio verde, segundo amarillo, tercero rojo. Ejemplo 09:00–18:00: verde hasta las 12:00, amarillo desde las 12:00, rojo desde las 15:00, vencida a las 18:00.
- Las tareas futuras son verdes, las vencidas rojas y las finalizadas neutras y excluidas de alertas.
- Los colores indican plazo, independientemente de la prioridad manual. El Gantt conserva escala por fechas y muestra horas en las filas.
- Colores actualizados en pantalla cada 30 segundos según el reloj del dispositivo. Alertas del hub consultadas al servidor cada minuto, con aviso si falla la conexión. Mantener los relojes sincronizados.
- El hub muestra tareas amarillas, rojas y vencidas: todas para supervisores y únicamente las visibles para usuarios base. No se envían correos ni notificaciones externas.

El logo original de Todotoner se sirve localmente en static/brand/logo.png y se usa en la cabecera, el favicon y el 404. Los selectores muestran nombre y apellido registrados, sin @usuario; las cuentas sin nombre usan el nombre de usuario como alternativa.

## Interfaz compacta y Dashboard TV

La interfaz diaria usa tamaños y espaciados menores. En escritorio, el hub del supervisor presenta tareas a la izquierda y alertas/historial a la derecha, con desplazamiento interno en estos últimos. En móvil se apilan los bloques y se conservan controles táctiles.

Supervisores y gerencia tienen Dashboard TV en el menú (/tv/). Diseño independiente con indicadores grandes, semáforo y seis tareas activas por página, ordenadas por vencimiento. Rota y actualiza cada 20 segundos, permite pausar la rotación sin detener las actualizaciones y activar pantalla completa mediante un botón. Si falla la conexión o caduca la sesión, muestra aviso de datos desactualizados. No requiere cambios de base de datos.

## Eliminación programada y Administración

Gerencia puede programar la eliminación de usuarios base y supervisores desde Usuarios. Se exige la contraseña de gerencia (también para cancelar). La cuenta queda inactiva inmediatamente; el plazo termina a la misma hora tras cinco días de lunes a viernes, sin contar el día de solicitud ni descontar feriados. La vista muestra el vencimiento.

Antes del vencimiento se puede cancelar y restaurar el estado activo/inactivo anterior. Al cumplirse el plazo no se admite cancelación. La eliminación es lógica: conserva usuario, tareas y referencias históricas, pero lo retira de la gestión y los selectores, sin permitir el login. El cierre se materializa automáticamente en la siguiente petición al sistema; no depende de un servidor de tareas externo. Gerencia no se puede eliminar por esta vista. Mientras está pendiente no se permite editar esa cuenta.

La migración agrega el cuarto sector Administración. Las tareas pueden combinarlo con Ventas, Postventas y Bodega.

### Historial y eliminación de tareas

- El menú Historial reúne las tareas finalizadas, las que ocultaste de tu hub y las eliminadas. Los usuarios base mantienen acceso únicamente a las tareas que crearon o tienen asignadas; supervisores y gerencia pueden consultar todas.
- La × de una tarea vencida o finalizada solo la oculta del hub y las alertas del usuario que la presiona. No elimina registros ni afecta al hub de otros usuarios. Las tareas en proceso no se pueden ocultar, incluso vencidas.
- Las tareas finalizadas aparecen automáticamente en Historial y pueden permanecer en el hub hasta que el usuario las oculte. Si se reabren o reprograman y dejan de ser ocultables, vuelven al hub.
- Supervisores y gerencia pueden usar Eliminar tarea desde el detalle, con una pantalla de confirmación. La eliminación de tareas es definitiva: borra la tarea, sus relaciones y sus cambios de la base de datos y del historial. El botón de confirmación espera 5 segundos. Los usuarios y las zonas se conservan. Ocultar con × sigue siendo una acción personal que conserva la tarea.
- Después de actualizar el proyecto, ejecuta `.\.venv\Scripts\python.exe manage.py migrate` antes de iniciar el servidor.


### Historial completo y filtros mensuales
El historial incluye todas las tareas conservadas a las que tiene acceso el usuario,
ordenadas por creación descendente. Los filtros Mes y Año consultan la fecha de creación;
sin selección se muestran todos los períodos. Un mes requiere un año.
El Gantt usa Mes y Año para el período planificado (incluye tareas que cruzan meses),
abre el mes actual y permite consultar un año completo dejando Mes vacío.
Cada detalle muestra el historial de modificaciones con autor, fecha y valores anteriores/nuevos.
Las tarjetas y el historial identifican al último autor de una modificación efectiva;
la creación y guardar sin cambios no se presentan como modificaciones.
El hub base utiliza la misma distribución de tareas y panel lateral que supervisión,
conservando sus permisos y su alcance personal. Las tareas borradas definitivamente
no se pueden recuperar desde este historial.


### Perfil, recuperación y privacidad de gerencia
El nombre y rol del menú abren Mi perfil. Cada cuenta edita únicamente sus nombres,
apellidos y correo; cambiar el correo exige su contraseña actual. Registro, perfil y
edición gerencial rechazan correos duplicados sin distinguir mayúsculas. Si ya existen
cuentas con un mismo correo, corregirlas desde Usuarios: recuperación no selecciona
arbitrariamente una de ellas.

En login hay pantallas separadas para recuperar usuario por correo y contraseña por
código de seis dígitos. El código se almacena como hash, caduca a los diez minutos,
admite cinco intentos y se vincula a la sesión solicitante. Tras verificarlo aparece
la pantalla de contraseña nueva y confirmación, con los validadores de Django.
Un cambio de contraseña invalida los códigos pendientes. Se limita a un envío por
minuto y tres por quince minutos por correo, además del límite por sesión. El mensaje
público no confirma si existe la cuenta. En local con DEBUG=True el correo aparece en
la terminal; para entrega real configurar SMTP (ver .env.example y DEPLOY_VERCEL.md).

Las tareas asignadas exclusivamente a responsables de gerencia son privadas para gerencia.
Las compartidas con usuarios base o supervisores conservan su visibilidad habitual.
Las privadas se excluyen del hub, alertas, historial, cambios, Gantt y TV de
usuarios base y supervisores, y tampoco admiten acceso o modificación mediante URL.
Una tarea creada por gerencia para otros responsables conserva su visibilidad habitual.
Los números internos no se muestran en las tarjetas, detalle ni tabla del historial.

Asistencia es una demostración reservada a supervisores y gerencia con personas y
estados ficticios, sin grabar marcaciones ni inferir asistencia de inicios de sesión.
GeoVictoria sigue pendiente.

## Áreas, espectadores, subtareas y primer ingreso (octubre 2026)

- Cada cuenta nueva requiere un área: Ventas, Administración, Postventas, Storage o Bodega. Son cinco áreas independientes. La migración 0013 separa Bodega de Storage, conservando las asignaciones existentes de Storage.
- Las cuentas existentes mantienen sus datos y no se fuerzan a cambiar contraseña. Gerencia debe asignarles área desde Usuarios. Un supervisor sin área solo accede a las tareas en las que participa explícitamente o es espectador; no obtiene acceso general.
- El equipo se determina por el área de los responsables, no por las zonas de la tarea. Gerencia conserva acceso general. Las tareas asignadas exclusivamente a gerencia siguen ocultas para otros roles.
- Usuarios base consultan Mi Gantt con las tareas accesibles. Espectadores individuales o por área tienen acceso de lectura; la pertenencia actual al área determina el acceso. Crear una tarea o ser responsable permite elegir espectadores. El autor, responsables, supervisor a cargo y supervisión del equipo mantienen su acceso.
- Asignar a toda un área incorpora los miembros activos al guardar; futuros integrantes no se asignan automáticamente. La búsqueda por nombre conserva selecciones aunque se filtre la lista.
- Las subtareas tienen responsables y espectadores independientes. Ver una subtarea no concede acceso a su tarea principal ni viceversa. Eliminar la principal conserva sus subtareas como tareas independientes.
- Gerencia entrega el usuario generado y una contraseña temporal, visible solo en la respuesta de creación. Se almacena únicamente su hash. En el primer ingreso se exige correo único y contraseña nueva distinta de la temporal antes de acceder al sistema.
- Las cuentas desactivadas o pendientes de eliminación no pueden iniciar sesión ni reactivarse. Al ingresar credenciales correctas se muestra Cuenta desactivada. La cancelación de eliminación permanece reservada a gerencia.
- Los cambios de espectadores quedan en el historial con actor y valores anteriores/nuevos.

Aplicar `python manage.py migrate` antes de iniciar esta versión. Incluye tareas 0011/0012 y cuentas 0006. No requiere nuevas dependencias.
