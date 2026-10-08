# Despliegue de pruebas en Vercel

El proyecto usa la detección nativa de Django (manage.py, config.wsgi y STATIC_ROOT).
Vercel recopila los estáticos automáticamente; no añadir rutas legacy de @vercel/python.
Python se fija en 3.12. Root Directory debe ser la carpeta que contiene manage.py.

## Base de datos
En el proyecto de Vercel, Storage / Marketplace, crear o conectar Neon PostgreSQL.
Conectar inicialmente solo al entorno Production, usando una base vacía de pruebas.
Confirmar que la integración configure DATABASE_URL con conexión PostgreSQL y SSL.
Para Preview usar otra base/rama, nunca compartir automáticamente los datos de producción.
No subir db.sqlite3: los datos locales no se transfieren automáticamente.

## Variables de Production
- DJANGO_SECRET_KEY: nueva clave aleatoria privada y estable.
- DJANGO_DEBUG: False.
- DJANGO_ALLOWED_HOSTS: dominio exacto asignado al proyecto, sin https://.
- DJANGO_CSRF_TRUSTED_ORIGINS: https:// seguido de ese dominio.
- DATABASE_URL: conexión PostgreSQL SSL proporcionada por Neon.
Los dominios VERCEL_URL y VERCEL_PROJECT_PRODUCTION_URL también se permiten automáticamente.
El .env local no se lee en Vercel; los archivos locales y ZIP se excluyen del envío por CLI.

## Inicializar la base antes de publicar
Con el entorno virtual local y desde la carpeta de manage.py, cargar temporalmente DATABASE_URL
como variable de entorno del proceso (usar la conexión directa de Neon para migraciones).
No escribir secretos en comandos que queden en el historial ni enviarlos por chat.
Ejemplo en PowerShell para solicitar la conexión sin mostrarla:

```powershell
$secureDatabase = Read-Host 'Conexión PostgreSQL directa de pruebas' -AsSecureString
$env:DATABASE_URL = [System.Net.NetworkCredential]::new('', $secureDatabase).Password
try {
    .\.venv\Scripts\python.exe manage.py migrate
    if ($LASTEXITCODE -ne 0) { throw 'Falló la migración' }
    .\.venv\Scripts\python.exe manage.py createsuperuser
} finally {
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Variable secureDatabase
}
```

El superusuario es gerencia. No se ejecutan migraciones ni se crean usuarios en cada petición
ni automáticamente al construir previews. Aplicar nuevas migraciones explícitamente antes
del despliegue correspondiente.

## Publicación y comprobación
La recuperación de acceso requiere aplicar también `accounts.0005_recoveryrequest`
en la base de destino con `manage.py migrate` antes de desplegar este cambio.
Configurar EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend, EMAIL_HOST,
EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD y DEFAULT_FROM_EMAIL con un remitente
autorizado por el proveedor. Puerto 587 suele usar EMAIL_USE_TLS=True y EMAIL_USE_SSL=False;
usar los valores indicados por el proveedor. Guardar credenciales solo como variables privadas.
Sin SMTP configurado no se entregan correos reales. Validar un envío con una cuenta propia
antes de habilitar recuperación. No usar el backend de consola en producción.

Subir los cambios al repositorio conectado. En Vercel, usar el framework Django y sus
comandos predeterminados; desplegar/redeploy después de configurar la base y las variables.
Probar /login/, estilos/logo, creación de tarea, ocultar del hub, historial y gestión.
Comprobar persistencia tras un redeploy. El registro público sigue habilitado: usar datos
ficticios para esta demo y preparar cuentas de prueba. La base remota es independiente de SQLite.

Vercel Hobby está limitado a uso personal no comercial; usar un plan apropiado para la empresa.
Documentación: https://vercel.com/docs/frameworks/full-stack/django
