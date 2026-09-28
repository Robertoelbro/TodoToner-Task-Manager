# Turno

Proyecto de una aplicación web responsive para planificar y registrar las actividades de los trabajadores, y consultar su estado desde un dashboard de jefatura.

Nombre provisional tomado del mockup. El sistema contempla usuarios de administración, ventas, postventa y bodega, distribuidos entre casa matriz y bodega.

## Estado actual

Preparación inicial del entorno de desarrollo. Todavía no se han creado el proyecto Django, las pantallas, los modelos ni la conexión a la base de datos. No hay un servidor web ejecutándose.

- Entorno virtual local `.venv` con Python 3.12.
- Dependencias Python registradas en `requirements.txt`.
- Plantilla `.env.example` sin secretos reales.
- Exclusiones de Git para entornos, secretos y datos locales.

## Tecnologías

| Tecnología | Uso |
| --- | --- |
| Python 3.12 | Lenguaje de desarrollo |
| Django 5.2 LTS | Backend, autenticación y páginas con templates |
| psycopg 3 | Conector de Python para PostgreSQL |
| django-environ | Lectura de configuración desde variables de entorno |
| PostgreSQL | Base de datos prevista; servidor aún no instalado ni configurado |
| Bootstrap y HTMX | Interfaz responsive y actualizaciones parciales; pendientes de integrar |
| Git | Control de versiones |

Despliegue previsto: servidor Linux con Nginx y Gunicorn. La ubicación del servidor y el acceso entre sedes se definirán con TI. Nginx y Gunicorn no se instalan en este entorno Windows inicial.

## Preparar el entorno en Windows

En un equipo nuevo, instalar Python 3.12 y Git. Después de clonar el repositorio privado, abrir PowerShell dentro de la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
```

En el equipo donde se preparó este proyecto, el entorno ya existe. Se utilizó el Python 3.12 incluido con las herramientas locales porque `python` no estaba disponible en PATH. El entorno depende de esa instalación base; si desaparece, recrearlo con una instalación propia de Python 3.12.

No copiar `.venv` entre equipos ni subirlo al repositorio. Recrearlo a partir de `requirements.txt`.

Si PowerShell bloquea la activación, no es necesario cambiar la política del sistema: se puede ejecutar el intérprete directamente.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m django --version
```

Para salir de un entorno activado:

```powershell
deactivate
```

## Configuración local

`.env.example` documenta las variables previstas. No se carga automáticamente: la integración se hará al crear la configuración Django. No colocar contraseñas reales en esa plantilla.

Cuando se implemente la configuración:

```powershell
Copy-Item .env.example .env
```

Completar `.env` localmente con una clave secreta aleatoria y las credenciales de PostgreSQL. Nunca subir `.env`, bases de datos, respaldos ni datos de trabajadores, incluso a un repositorio privado.

## Subir a un repositorio privado de GitHub

1. Crear un repositorio en GitHub con visibilidad **Private**. Dejarlo vacío, sin README, licencia ni `.gitignore`, porque estos archivos se preparan localmente.
2. Desde esta carpeta, revisar los archivos que Git incluirá:

```powershell
git status --short
git add README.md .gitignore .env.example requirements.in requirements.txt
git diff --cached --stat
git diff --cached
git commit -m "Preparar entorno inicial del proyecto"
```

3. Reemplazar `TU_USUARIO` y `TU_REPOSITORIO` por los datos reales, conectar el repositorio y subirlo:

```powershell
git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git
git push -u origin main
```

Se requiere autenticación de GitHub. Si Git solicita identidad para el commit, configurar `user.name` y `user.email` con los datos propios. Comprobar en GitHub que el repositorio muestre **Private** antes de subir archivos. No guardar tokens en el código ni en la URL del remoto.

La privacidad del repositorio protege el acceso al código; el acceso a la futura aplicación se configura por separado.

## Alcance previsto, pendiente de validar

- Jornada y actividades asignadas por trabajador.
- Horarios planificados y registros reales de inicio y término separados.
- Pausas, actualizaciones, pendientes e historial de cambios.
- Dashboard de jefatura y vista resumida para pantalla compartida.
- Cuentas individuales y permisos por perfil.

Primero se confirmarán las reglas de asignación, los roles y la infraestructura. No se prioriza funcionamiento sin conexión.

## Referencias

- [Django: versiones y soporte](https://www.djangoproject.com/download/)
- [Psycopg: instalación](https://www.psycopg.org/psycopg3/docs/basic/install.html)
