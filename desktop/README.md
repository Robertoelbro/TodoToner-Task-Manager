# Copia local de Todotoner

La entrega Windows x64 contiene TodoToner.exe y la carpeta _internal. Conserva ambos juntos.
No usa Python instalado, Neon ni las credenciales del proyecto web. Usa Waitress y SQLite,
escucha únicamente en 127.0.0.1 y abre la interfaz en el navegador. No es un servicio de Windows.
Cierra su ventana para detenerlo. La URL real se muestra en la ventana (8000 o un puerto libre).

## Primer inicio

Extraer todo el ZIP en una carpeta con permisos de escritura, como Documentos. Ejecutar
TodoToner.exe. En el primer inicio se aplican las migraciones y se solicita crear la primera
cuenta de gerencia. No hay usuarios ni contraseñas predeterminados. Los datos quedan en
la subcarpeta datos, junto al ejecutable. No ejecutar desde el ZIP ni copiar solamente el EXE.

## Respaldos

Guardar respaldo crea un ZIP con plataforma.sqlite3 y secret.key. No compartirlo públicamente.
Para restaurar: cerrar el programa, respaldar la carpeta datos existente, extraer esos dos archivos
del ZIP dentro de datos y volver a iniciar. Reemplazar archivos solamente con el servicio cerrado.
La base y la clave deben conservarse juntas, ya que las claves temporales dependen del secreto.
No reemplazar datos al actualizar el ejecutable. Esta copia no se sincroniza con Vercel.

## Desarrollo y construcción

Usar Python 3.12 de 64 bits en Windows. Desde la raíz:

    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
    .\.venv\Scripts\python.exe desktop\build_windows.py

La salida queda en dist/TodoToner. El comando también ejecuta --self-test en una base temporal.
Para verificar un binario ya construido:

    TodoToner.exe --self-test --report verificacion-local.json

El modo de prueba no utiliza los datos reales de la instalación. Para iniciar desde fuentes:

    .\.venv\Scripts\python.exe desktop\launcher.py --data-dir .\datos-locales

El launcher fija desktop.local_settings y SQLite, independientemente del DATABASE_URL del equipo.
La configuración web normal sigue usando config.settings. No se modifican Neon ni Vercel al abrirlo.
El hook personalizado de PyInstaller evita la autodetección de bases del desarrollador. Los datos,
.env y claves nunca se incluyen en la distribución. No copiar datos, .env, .venv ni backups al ZIP de fuentes.
El binario no lleva firma de editor. Si Windows o una política empresarial lo bloquean, TI debe evaluar
su distribución y firma; no se requiere desactivar las protecciones del equipo.
