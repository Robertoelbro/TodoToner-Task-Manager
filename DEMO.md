# Demostración

`python manage.py seed_demo --reset --confirm-reset REEMPLAZAR_DATOS_DEMO --backup backups/antes-demo.json.gz`

**Reemplaza todos los usuarios, tareas, metas y sesiones de la base configurada.**
Genera primero un respaldo comprimido de los datos anteriores y luego ejecuta la
carga en una transacción. Si algo falla, los cambios de datos se revierten.
No modifica el esquema ni el registro de migraciones. Usa una ruta nueva por ejecución.
Los respaldos contienen datos privados y hashes de contraseña: no se publican en Git.

Crea 10 colaboradores: un supervisor y un usuario base por cada una de las cinco
áreas, además de la cuenta gerencial `agerente` (11 cuentas en total).
Los nombres de acceso son `supervisor_ventas`, `usuario_ventas`, y el mismo patrón
para `postventas`, `storage`, `administracion` y `bodega`.
Todas usan la contraseña `contraseña` y están listas para entrar sin primer ingreso.
Son cuentas ficticias de prueba con direcciones de correo no entregables.
La variable `DEMO_PASSWORD` permite cambiar la clave del conjunto al ejecutar el script.

Genera 20 tareas principales y 10 subtareas adicionales, con prioridades, estados,
responsables y espectadores individuales y por área variados. Hay fechas pasadas,
actuales y futuras. Las fechas se calculan respecto del día de ejecución en Chile.
Incluye seis metas (una por área y una general) para el mes actual y para cada uno
de los dos meses siguientes: 18 metas en total. Se usa aleatoriedad reproducible;
`--seed 123` permite cambiar la distribución.

La política de contraseñas acepta desde cinco caracteres, sin exigir mayúsculas,
números ni signos especiales. No se ejecuta esta carga automáticamente al desplegar.
