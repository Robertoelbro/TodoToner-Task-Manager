# Ejecutar Todotoner en Replit

Esta configuración usa Django, Gunicorn, WhiteNoise y PostgreSQL. No cambia el
arranque de Vercel. La base de desarrollo de Replit es independiente de Neon.

## Preparación

1. Revisar que `DATABASE_URL` corresponda a la base de Replit. No copiar la de Vercel.
2. Instalar `python -m pip install -r requirements-replit.txt`.
3. Configurar Run con el workflow `Todotoner`, comando
   `python scripts/replit_start.py` y puerto interno 5000. `.replit.example`
   sirve como referencia; conservar las otras opciones que ya tenga el proyecto.

En Preview, el primer arranque genera una clave aleatoria en `.env`, excluida de
Git, si no existe una clave o configuración previa. Nunca se imprime esa clave.
El arranque aplica las migraciones pendientes y prepara los archivos estáticos.
Las siguientes ejecuciones conservan usuarios y tareas.

La instalación inicial de esta copia creó `gerencia` con una clave temporal y
primer ingreso obligatorio. Las credenciales se guardaron exclusivamente en
`.replit-local/acceso-inicial.txt`, fuera de Git. Abrir ese archivo dentro de
Replit para obtenerlas; completar correo y contraseña personal al ingresar.
Eliminar la nota temporal después de completar el ingreso. El arranque no crea
ni restablece cuentas y no establece contraseñas predeterminadas.

Para usar un comando de gestión en Shell, seleccionar la configuración:

```sh
export DJANGO_SETTINGS_MODULE=config.replit_settings
python manage.py createsuperuser
```

## Publicación posterior

Preview no es una publicación permanente. Antes de publicar con Autoscale o
Reserved VM, configurar `DJANGO_SECRET_KEY` persistente en los Secrets del
despliegue, revisar `DATABASE_URL` de producción y añadir sus dominios exactos
a `DJANGO_ALLOWED_HOSTS` y orígenes HTTPS a `DJANGO_CSRF_TRUSTED_ORIGINS` si no
figuran en `REPLIT_DOMAINS`. No definir `VERCEL=1`.

Instalar las dependencias durante el build. Aplicar las migraciones Django sobre
la base de producción en una operación controlada antes de iniciar servidores;
el script no las aplica automáticamente al ejecutar una instancia publicada.
Comprobar `django_migrations`, tablas y datos; no confiar en que una publicación
automática copie correctamente el historial de migraciones Django.

Crear la cuenta gerencial en cada base nueva y validar login, edición, permisos,
Gantt y recursos estáticos. La base de desarrollo y la publicada pueden tener
usuarios y tareas distintos. No se configuraron buckets: actualmente no se
suben adjuntos ni fotografías personales.
