from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_post_parameters
from django.db import transaction


@require_http_methods(['GET', 'POST'])
def register(request):
    # El registro público se sustituye por alta exclusiva de gerencia.
    if not request.user.is_authenticated or not request.user.is_superuser:
        raise Http404
    return redirect('user-create')


from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
from .models import User
from .forms import ManagedUserForm
from django.views.decorators.cache import never_cache


def filter_people(query):
    from django.db.models import Q, Value
    from django.db.models.functions import Concat
    people = User.objects.filter(deleted_at__isnull=True).select_related('area').annotate(
        full_name=Concat('first_name', Value(' '), 'last_name'))
    if query.strip():
        people = people.filter(Q(full_name__icontains=query.strip()) | Q(username__icontains=query.strip()))
    return people.order_by('first_name', 'last_name', 'username')


@login_required
@never_cache
@sensitive_post_parameters('temporary_password')
@require_http_methods(['GET', 'POST'])
def user_create(request):
    if not request.user.is_superuser:
        raise Http404
    from .forms import ManagedCreationForm
    from django.db import IntegrityError
    from .usernames import username_candidates
    form = ManagedCreationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        password = user.issue_temporary_password()
        user.must_complete_profile = True
        user.is_superuser = user.is_supervisor = user.is_staff = False
        for candidate in username_candidates(user.first_name, user.last_name):
            if User.objects.filter(username=candidate).exists():
                continue
            user.username = candidate
            try:
                with transaction.atomic():
                    user.save(force_insert=True)
            except IntegrityError:
                if not User.objects.filter(username=candidate).exists():
                    raise
            else:
                break
        # Se entrega solo en esta respuesta; nunca se guarda la contraseña en sesión o logs.
        return render(request, 'accounts/created.html', {'created_user': user, 'temporary_password': password})
    return render(request, 'accounts/create.html', {'form': form})


@login_required
@never_cache
@sensitive_post_parameters('new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def complete_profile(request):
    from .forms import CompleteProfileForm
    from django.contrib.auth import update_session_auth_hash
    if not request.user.must_complete_profile:
        return redirect('task-list')
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if not user.is_active or user.deletion_due_at or user.deleted_at:
            return render(request, 'accounts/inactive.html', status=403)
        if user.get_session_auth_hash() != request.user.get_session_auth_hash():
            from django.contrib.auth import logout
            logout(request)
            return redirect('login')
        form = CompleteProfileForm(user, request.POST if request.method == 'POST' else None)
        if request.method == 'POST' and form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Tu cuenta está lista.')
            return redirect('task-list')
    return render(request, 'accounts/complete_profile.html', {'form': form})


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def users_manage(request, pk=None):
    if not request.user.is_superuser:
        raise Http404
    if pk is not None:
        # Serializar cambios de rol para conservar al menos una gerencia activa.
        managers = list(User.objects.select_for_update().filter(is_superuser=True)
                        .order_by('pk').values_list('pk', flat=True))
        if request.user.pk not in managers:
            raise Http404
    target = get_object_or_404(User.objects.select_for_update(), pk=pk, deleted_at__isnull=True, deletion_due_at__isnull=True) if pk is not None else None
    if target and (target.must_complete_profile or target.must_change_password):
        password = target.temporary_password
        return render(request, 'accounts/pending_credentials.html', {'target_user': target, 'temporary_password': password})
    form = ManagedUserForm(request.POST if request.method == 'POST' else None, instance=target) if target else None
    if request.method == 'POST':
        if target is None:
            raise Http404
        if form.is_valid():
            updated_user = form.save()
            messages.success(request, 'Usuario actualizado.')
            return redirect('task-list' if updated_user.pk == request.user.pk and not updated_user.is_superuser else 'users-manage')
    if target is None and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        response = render(request, 'accounts/people.html', {'people': filter_people(request.GET.get('q', ''))})
        response['X-Turno-Fragment'] = 'users'
        response['Cache-Control'] = 'no-store'
        return response
    return render(request, 'accounts/manage.html', {
        'people': filter_people(request.GET.get('q', '')), 'query': request.GET.get('q', ''), 'form': form, 'target_user': target,
    })


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def email_access(request, pk):
    if not request.user.is_superuser:
        raise Http404
    from .forms import EmailAccessForm
    target = get_object_or_404(User.objects.select_for_update(), pk=pk,
                              deleted_at__isnull=True, deletion_due_at__isnull=True)
    form = EmailAccessForm(request.POST if request.method == 'POST' else None, instance=target)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Opción de acceso actualizada.')
        return redirect('users-manage')
    return render(request, 'accounts/email_access.html', {'form': form, 'target_user': target})


def not_found(request, exception=None):
    return render(request, '404.html', status=404)


@login_required
@sensitive_post_parameters('current_password')
@require_http_methods(['GET', 'POST'])
def profile(request):
    from .forms import ProfileForm
    form = ProfileForm(request.POST if request.method == 'POST' else None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Perfil actualizado.')
        return redirect('profile')
    return render(request, 'accounts/profile.html', {'form': form})




from django.db import transaction
from django.core.exceptions import ValidationError
from .forms import DeletionConfirmationForm
from .deletion import schedule_deletion, cancel_deletion, delete_now


@login_required
@never_cache
@sensitive_post_parameters('password')
@require_http_methods(['GET', 'POST'])
def user_deletion(request, pk, cancel=False, immediate=False):
    if not request.user.is_superuser:
        raise Http404
    target = get_object_or_404(User, pk=pk, is_superuser=False, deleted_at__isnull=True)
    if immediate and not target.can_cancel_deletion:
        raise Http404
    form = DeletionConfirmationForm(request.POST if request.method == 'POST' else None, actor=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            if immediate:
                delete_now(actor=request.user, target_id=pk)
            elif cancel:
                cancel_deletion(actor=request.user, target_id=pk)
            else:
                schedule_deletion(actor=request.user, target_id=pk)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'La cuenta se eliminó de la gestión. Sus tareas e historial se conservaron.' if immediate else ('Eliminación cancelada.' if cancel else 'Eliminación programada; la cuenta quedó desactivada.'))
            return redirect('users-manage')
    return render(request, 'accounts/deletion.html', {'form': form, 'target_user': target, 'cancel': cancel, 'immediate': immediate})


@login_required
@never_cache
@sensitive_post_parameters('password')
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def password_reset_by_management(request, pk):
    if not request.user.is_superuser:
        raise Http404
    target = get_object_or_404(User.objects.select_for_update(), pk=pk,
        is_superuser=False, is_active=True, deleted_at__isnull=True, deletion_due_at__isnull=True)
    form = DeletionConfirmationForm(request.POST if request.method == 'POST' else None, actor=request.user)
    if request.method == 'POST' and form.is_valid():
        target.issue_temporary_password()
        target.must_change_password = True
        target.save(update_fields=['password', 'onboarding_nonce', 'must_change_password'])
        messages.success(request, 'Se generó una nueva clave temporal. El trabajador deberá cambiarla al ingresar.')
        return redirect('user-edit', pk=target.pk)
    return render(request, 'accounts/reset_password.html', {'form': form, 'target_user': target})


@login_required
@never_cache
@sensitive_post_parameters('old_password', 'new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def password_change(request):
    from django.contrib.auth import update_session_auth_hash, logout
    from .forms import ForcedPasswordForm, SelfPasswordChangeForm
    user = get_object_or_404(User.objects.select_for_update(), pk=request.user.pk,
        is_active=True, deleted_at__isnull=True, deletion_due_at__isnull=True)
    if user.get_session_auth_hash() != request.user.get_session_auth_hash():
        logout(request)
        return redirect('login')
    forced = user.must_change_password
    form_class = ForcedPasswordForm if forced else SelfPasswordChangeForm
    form = form_class(user, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.must_change_password = False
        user.onboarding_nonce = ''
        user.save(update_fields=['password', 'must_change_password', 'onboarding_nonce'])
        update_session_auth_hash(request, user)
        messages.success(request, 'Contraseña actualizada.')
        return redirect('task-list' if forced else 'profile')
    return render(request, 'accounts/password_change.html', {'form': form, 'forced': forced})
