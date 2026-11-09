"""Google OpenID Connect: acceso a cuentas existentes, sin registro público."""
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode, urlsplit

import requests
from google.auth.exceptions import GoogleAuthError
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET, require_POST

from .models import GoogleIdentity, User
from .onboarding import AccountAuthenticationForm

AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
FLOW_KEY = '_google_login_flow'
FLOW_LIFETIME = 600


class GoogleLoginDenied(Exception):
    pass


def configured():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def available():
    return User.objects.filter(allow_email_login=True, is_active=True,
        deletion_due_at__isnull=True, deleted_at__isnull=True).exclude(email='').exists()


class PlatformLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = AccountAuthenticationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(google_available=available(), google_configured=configured())
        return context


def _next(request, value):
    if value and url_has_allowed_host_and_scheme(value, {request.get_host()}, require_https=request.is_secure()):
        return value
    return reverse('task-list')


def _redirect_uri(request):
    uri = settings.GOOGLE_OAUTH_REDIRECT_URI or request.build_absolute_uri(reverse('google-callback'))
    parsed = urlsplit(uri)
    if (not url_has_allowed_host_and_scheme(uri, {request.get_host()}, require_https=not settings.DEBUG)
            or parsed.path != reverse('google-callback') or parsed.query or parsed.fragment
            or parsed.username or parsed.password):
        raise GoogleLoginDenied
    return uri


def _error(request, message=None, status=400):
    response = render(request, 'accounts/google_error.html', {
        'message': message or 'No fue posible iniciar sesión con Google. Usa tu usuario y contraseña o contacta a gerencia.'
    }, status=status)
    response['Referrer-Policy'] = 'no-referrer'
    return response


@never_cache
@require_POST
def start(request):
    if request.user.is_authenticated:
        return redirect('task-list')
    if not configured() or not available():
        return _error(request, 'El inicio con Google aún no está disponible. Puedes ingresar con tu usuario y contraseña.', 503)
    try:
        redirect_uri = _redirect_uri(request)
    except GoogleLoginDenied:
        return _error(request, status=503)
    verifier = secrets.token_urlsafe(64)
    flow = {'state': secrets.token_urlsafe(32), 'nonce': secrets.token_urlsafe(32),
            'verifier': verifier, 'created': time.time(), 'redirect_uri': redirect_uri,
            'next': _next(request, request.POST.get('next', ''))}
    request.session[FLOW_KEY] = flow
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    params = dict(client_id=settings.GOOGLE_OAUTH_CLIENT_ID, redirect_uri=redirect_uri,
                  response_type='code', scope='openid email', state=flow['state'], nonce=flow['nonce'],
                  code_challenge=challenge, code_challenge_method='S256', prompt='select_account')
    response = redirect(AUTH_ENDPOINT + '?' + urlencode(params))
    response['Referrer-Policy'] = 'no-referrer'
    return response


@sensitive_variables('code', 'flow', 'response', 'payload')
def _exchange_code(code, flow):
    response = requests.post(TOKEN_ENDPOINT, data={
        'code': code, 'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET, 'redirect_uri': flow['redirect_uri'],
        'grant_type': 'authorization_code', 'code_verifier': flow['verifier'],
    }, timeout=(3.05, 10))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise GoogleLoginDenied
    encoded = payload.get('id_token')
    if not isinstance(encoded, str) or not encoded or len(encoded) > 16384:
        raise GoogleLoginDenied
    return encoded


@sensitive_variables('encoded')
def _decode_token(encoded):
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import verify_oauth2_token

    class BoundedRequest(Request):
        def __call__(self, *args, **kwargs):
            kwargs['timeout'] = (3.05, 10)
            return super().__call__(*args, **kwargs)

    # La biblioteca oficial comprueba firma, emisor, audiencia y caducidad.
    return verify_oauth2_token(encoded, BoundedRequest(), settings.GOOGLE_OAUTH_CLIENT_ID)


def _validate_claims(claims, nonce):
    if not isinstance(claims, dict):
        raise GoogleLoginDenied
    subject, email, token_nonce = claims.get('sub'), claims.get('email'), claims.get('nonce')
    if (not isinstance(subject, str) or not subject or len(subject) > 255
            or not isinstance(email, str) or len(email) > 254 or claims.get('email_verified') is not True
            or not isinstance(token_nonce, str) or not secrets.compare_digest(token_nonce.encode(), nonce.encode())):
        raise GoogleLoginDenied
    validate_email(email)
    # Google solo es autoridad del correo en Gmail o Google Workspace.
    hosted_domain = claims.get('hd')
    if email.rsplit('@', 1)[1].lower() != 'gmail.com' and not (isinstance(hosted_domain, str) and hosted_domain):
        raise GoogleLoginDenied
    return subject, email


@transaction.atomic
def _resolve_user(subject, email):
    matches = list(User.objects.select_for_update().filter(email__iexact=email).order_by('pk')[:2])
    if len(matches) != 1:
        raise GoogleLoginDenied
    user = matches[0]
    if not user.allow_email_login or not user.is_active or user.deletion_due_at or user.deleted_at:
        raise GoogleLoginDenied
    identity, _ = GoogleIdentity.objects.get_or_create(user=user, defaults={'subject': subject})
    if identity.subject != subject:
        raise GoogleLoginDenied
    return user


@never_cache
@require_GET
@sensitive_variables('code', 'flow', 'encoded', 'claims')
def callback(request):
    # Consumir el estado antes de intercambiar el código: cada intento se usa una vez.
    flow = request.session.pop(FLOW_KEY, None)
    state = request.GET.get('state', '')
    if (not configured() or not flow or not isinstance(state, str)
            or not secrets.compare_digest(state.encode(), flow['state'].encode())
            or not 0 <= time.time() - flow['created'] <= FLOW_LIFETIME):
        return _error(request)
    code = request.GET.get('code', '')
    if request.GET.get('error') or not code or len(code) > 4096:
        return _error(request)
    try:
        encoded = _exchange_code(code, flow)
        claims = _decode_token(encoded)
        subject, email = _validate_claims(claims, flow['nonce'])
        user = _resolve_user(subject, email)
    except (GoogleLoginDenied, ValidationError, IntegrityError, ValueError,
            requests.RequestException, GoogleAuthError):
        return _error(request)
    login(request, user, backend='accounts.authentication.GoogleBackend')
    response = redirect(_next(request, flow['next']))
    response['Referrer-Policy'] = 'no-referrer'
    return response
