# Inicio de sesión con Google

## Qué hace

Gerencia activa **Permitir ingresar con correo electrónico** en Usuarios → Editar
usuario. Ese mismo permiso admite correo y contraseña, y acceso con Google. El
nombre de usuario y la contraseña siguen disponibles. El botón **Iniciar sesión
con Google** aparece cuando existe al menos una cuenta activa habilitada; el
servidor verifica el permiso de la cuenta concreta después de volver de Google.
No se publica una lista de correos ni se necesita escribir el correo antes de
seleccionar Google.

Sin credenciales OAuth, el botón aparece deshabilitado con una explicación. La
aplicación sigue permitiendo el ingreso habitual. Configurar las credenciales es
necesario para activar la conexión real; las pruebas no sustituyen ese paso.

Solo se admiten cuentas ya creadas en la plataforma con correo válido, exclusivo
y coincidente con el correo verificado de Google. Se admite Gmail y Google
Workspace. Google no es autoridad sobre correos externos sin Workspace, aunque
hayan sido verificados al crear una cuenta Google; en ese caso se usa el ingreso
habitual. No se crean cuentas ni se cambian roles, áreas, nombres o contraseñas
desde Google.

En el primer acceso se vincula el identificador estable de Google (`sub`) con la
cuenta existente. No se sustituye esa vinculación por otro identificador ni se
transfiere a otra persona por coincidencia de correo. El usuario conserva su
contraseña local. Los cambios obligatorios de perfil o contraseña también se
exigen después de ingresar con Google. Retirar el permiso impide nuevos accesos
y deja sin autenticación las sesiones iniciadas mediante Google.

## Crear el cliente en Google Cloud

1. Entrar a [Google Cloud Console](https://console.cloud.google.com/) con una
   cuenta de la empresa y seleccionar o crear el proyecto correspondiente.
2. Abrir **Google Auth Platform**. Configurar **Branding**, **Audience** y
   **Data Access**: nombre de la app, correo de soporte/contacto y público. Si se
   usa el estado de prueba externo, añadir los correos de quienes probarán.
3. Solicitar únicamente identidad básica `openid` y `email`. No habilitar Gmail
   API, lectura de mensajes, Drive ni permisos de envío para este inicio.
4. En **Clients**, crear un cliente OAuth de tipo **Web application**.
5. Añadir las **Authorized redirect URIs** de cada instancia que vaya a usarlo.
   Deben coincidir exactamente, incluido el protocolo y la barra final:

   - Local: `http://localhost:8000/login/google/callback/`
   - Staging actual: `https://todo-toner-task-manager-git-staging-roberto-el-bro.vercel.app/login/google/callback/`
   - Dev: `https://DOMINIO-DEV/login/google/callback/`
   - Replit: `https://DOMINIO-DE-LA-APP/login/google/callback/`

   Usar el dominio que realmente sirve la app, no `replit.com/@...` ni la página
   de configuración de Vercel. No se admiten comodines. Para probar dentro de
   Replit, abrir Preview en una pestaña externa: Google no permite su pantalla
   de autenticación dentro de un iframe. Si cambia el dominio de Preview, hay
   que registrar el nuevo callback. Para producción se recomienda un cliente
   distinto y un dominio estable.
6. Guardar el ID y la clave secreta en el gestor de secretos del servicio. Nunca
   publicarlos en Git, capturas, documentación o conversaciones.

La interfaz de Google puede cambiar de idioma o distribución; la documentación
oficial está al final de este archivo. La cuenta que controla el proyecto debe
completar cualquier aceptación de términos que solicite Google.

## Variables por ambiente

```dotenv
GOOGLE_OAUTH_CLIENT_ID=ID_DEL_CLIENTE
GOOGLE_OAUTH_CLIENT_SECRET=CLAVE_SECRETA
# Opcional: debe ser el callback exacto de esta instancia.
GOOGLE_OAUTH_REDIRECT_URI=https://DOMINIO-DE-ESTA-APP/login/google/callback/
```

Si se omite la última variable, la app calcula el callback desde su propio
dominio. El cliente de Google debe tener ese URI registrado de todas formas.

- Local: configurar `.env` privado y reiniciar Django.
- Vercel dev: variables del despliegue de main (Vercel lo llama Production).
- Vercel staging: variables Preview específicas de la rama `staging`.
- Replit Preview: usar Secrets y volver a ejecutar el workflow Todotoner.
- Replit publicado: configurar sus secretos por separado cuando se autorice la
  publicación. Los secretos de Preview no se dan por existentes en producción.

No habilitar credenciales de producción en un dominio de prueba ajeno.

## Instalación y migración

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
```

En Linux/Codespaces/Replit se usa `python -m pip install -r requirements.txt` y
`python manage.py migrate`. Replit usa además `requirements-replit.txt`.
La migración `accounts.0010_googleidentity` crea la tabla de vínculos; no elimina
usuarios ni tareas. Aplicarla en cada base antes de activar el cliente OAuth.

## Comprobación real después de configurar

1. Registrar en Mi perfil el correo real de una cuenta de prueba existente.
2. Gerencia habilita el permiso en esa cuenta.
3. Abrir la app fuera de un iframe y pulsar Iniciar sesión con Google.
4. Seleccionar la cuenta de Google correspondiente y completar el consentimiento.
5. Verificar el retorno al hub y que se conservan rol, área y tareas.
6. Repetir con una cuenta sin permiso: no debe poder ingresar ni crear usuarios.
7. Retirar el permiso y verificar que la sesión Google pierde el acceso.

## Verificación implementada

Flujo de código de autorización con POST y CSRF al iniciar, estado de un solo
uso vinculado a la sesión, nonce y PKCE S256. El token se intercambia en el
servidor. La biblioteca oficial `google-auth` verifica firma, emisor, audiencia
y vencimiento; la aplicación verifica nonce, correo y permiso vigente. No se
guardan tokens de acceso o refresco. Las solicitudes a Google tienen límites de
tiempo y los errores no revelan tokens ni secretos en la respuesta.

Documentación oficial:

- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
- [Verificación de ID tokens](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)
- [Botón e identidad visual](https://developers.google.com/identity/branding-guidelines)
