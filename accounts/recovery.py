"""Recuperación con códigos de un uso, persistente entre instancias de Vercel."""
from datetime import timedelta
import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .forms import RecoveryEmailForm, RecoveryCodeForm
from .models import RecoveryRequest, User

logger = logging.getLogger(__name__)


def send_recovery(email, purpose):
    now = timezone.now()
    key = salted_hmac('recovery-email', email, algorithm='sha256').hexdigest()
    with transaction.atomic():
        users = list(User.objects.select_for_update().filter(email__iexact=email,
            is_active=True, deleted_at__isnull=True, deletion_due_at__isnull=True)[:2])
        recent = RecoveryRequest.objects.filter(email_key=key, created_at__gte=now-timedelta(minutes=15))
        if recent.count() >= 3 or recent.filter(created_at__gte=now-timedelta(seconds=60)).exists():
            return None
        user = users[0] if len(users) == 1 and users[0].has_usable_password() else None
        code = f'{secrets.randbelow(1000000):06d}'
        record = RecoveryRequest.objects.create(email_key=key, purpose=purpose, user=user,
            code_hash=make_password(code), expires_at=now+timedelta(minutes=10),
            account_token=default_token_generator.make_token(user) if user else '')
        if user:
            body = (f'Tu usuario de Todotoner es: {user.username}' if purpose == 'username' else
                f'Tu código para cambiar la contraseña es: {code}\nCaduca en 10 minutos y permite hasta 5 intentos.')
            try:
                send_mail('Todotoner · Recuperación de acceso', body + '\nSi no lo solicitaste, ignora este correo.',
                    settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            except Exception:
                # No registrar cuerpos, códigos, direcciones ni excepciones SMTP con secretos.
                logger.error('No se pudo entregar un correo de recuperación. Revisar configuración SMTP.')
                record.consumed = True
                record.save(update_fields=['consumed'])
        return str(record.pk)


@never_cache
@require_http_methods(['GET', 'POST'])
def recovery_start(request, purpose='password'):
    form = RecoveryEmailForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        # Límite adicional por sesión, también para direcciones inexistentes.
        now = timezone.now().timestamp()
        if now - request.session.get('recovery_last_sent', 0) >= 60:
            record_id = send_recovery(form.cleaned_data['email'].strip().lower(), purpose)
            request.session['recovery_last_sent'] = now
            if purpose == 'password' and record_id:
                request.session['recovery_id'] = record_id
        messages.success(request, 'Si el correo corresponde a una cuenta habilitada, recibirás las instrucciones. Revisa también spam. Los envíos repetidos tienen un tiempo de espera.')
        if purpose == 'password':
            return redirect('recovery-code')
        return redirect('recover-username')
    return render(request, 'accounts/recovery.html', {'form': form,
        'heading': '¿Olvidaste tu usuario?' if purpose == 'username' else '¿Olvidaste tu contraseña?',
        'description': 'Te enviaremos tu nombre de usuario.' if purpose == 'username' else 'Te enviaremos un código para confirmar el cambio.',
        'button': 'Enviar correo'})


def valid_record(record):
    return (record and record.purpose == 'password' and not record.consumed and record.user
        and record.expires_at > timezone.now() and record.user.is_active
        and record.user.deleted_at is None and record.user.deletion_due_at is None
        and default_token_generator.check_token(record.user, record.account_token))


@never_cache
@sensitive_post_parameters('code')
@require_http_methods(['GET', 'POST'])
def recovery_code(request):
    form = RecoveryCodeForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            record = RecoveryRequest.objects.select_for_update().filter(pk=request.session.get('recovery_id')).first()
            if valid_record(record) and not record.verified and record.attempts < 5:
                record.attempts += 1
                record.verified = check_password(form.cleaned_data['code'], record.code_hash)
                record.save(update_fields=['attempts', 'verified'])
                if record.verified:
                    request.session.cycle_key()
                    return redirect('recovery-password')
        form.add_error('code', 'Código inválido, caducado o sin intentos disponibles. Solicita otro correo.')
    return render(request, 'accounts/recovery.html', {'form': form, 'heading': 'Confirma el código',
        'description': 'Ingresa el código de seis dígitos recibido por correo. Caduca a los 10 minutos.', 'button': 'Confirmar código'})


@never_cache
@sensitive_post_parameters('new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def recovery_password(request):
    record = RecoveryRequest.objects.select_for_update().filter(pk=request.session.get('recovery_id')).first()
    if not valid_record(record) or not record.verified:
        return redirect('recover-password')
    user = User.objects.select_for_update().get(pk=record.user_id)
    record.user = user
    if not valid_record(record):
        return redirect('recover-password')
    form = SetPasswordForm(user, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        RecoveryRequest.objects.filter(user=user, purpose='password').update(consumed=True)
        request.session.pop('recovery_id', None)
        messages.success(request, 'Contraseña actualizada. Inicia sesión con tu nueva contraseña.')
        return redirect('login')
    return render(request, 'accounts/recovery.html', {'form': form,
        'heading': 'Nueva contraseña', 'description': 'Escribe y confirma tu nueva contraseña.', 'button': 'Cambiar contraseña'})
