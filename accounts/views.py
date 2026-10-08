from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_post_parameters
from .forms import RegistrationForm


@require_http_methods(['GET', 'POST'])
def register(request):
    if request.user.is_authenticated:
        return redirect('task-list')
    form = RegistrationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        form.save()  # No se aceptan privilegios desde el registro.
        messages.success(request, 'Cuenta creada. Ya puedes iniciar sesión.')
        return redirect('login')
    return render(request, 'accounts/register.html', {'form': form})



from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
from .models import User
from .forms import ManagedUserForm


@login_required
@require_http_methods(['GET', 'POST'])
def users_manage(request, pk=None):
    if not request.user.is_superuser:
        raise Http404
    # Gerencia no cambia sus propios privilegios ni los de otra cuenta gerencial.
    target = get_object_or_404(User, pk=pk, is_superuser=False, deleted_at__isnull=True, deletion_due_at__isnull=True) if pk is not None else None
    form = ManagedUserForm(request.POST if request.method == 'POST' else None, instance=target) if target else None
    if request.method == 'POST':
        if target is None:
            raise Http404
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario actualizado.')
            return redirect('users-manage')
    return render(request, 'accounts/manage.html', {
        'people': User.objects.filter(deleted_at__isnull=True).order_by('first_name', 'username'), 'form': form, 'target_user': target,
    })


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


@login_required
@require_http_methods(['GET'])
def attendance(request):
    if not request.user.can_supervise:
        raise Http404
    from django.utils import timezone
    # Datos ficticios: no representan presencia real ni se guardan en la BD.
    people = [
        {'name': 'Colaborador de ejemplo A', 'zone': 'Ventas', 'status': 'Presente', 'time': '09:00'},
        {'name': 'Colaborador de ejemplo B', 'zone': 'Postventas', 'status': 'Presente', 'time': '08:55'},
        {'name': 'Colaborador de ejemplo C', 'zone': 'Bodega', 'status': 'Sin marcación', 'time': '—'},
        {'name': 'Colaborador de ejemplo D', 'zone': 'Administración', 'status': 'Vacaciones', 'time': '—'},
    ]
    return render(request, 'accounts/attendance.html', {'people': people, 'today': timezone.localdate()})


from django.db import transaction
from django.core.exceptions import ValidationError
from .forms import DeletionConfirmationForm
from .deletion import schedule_deletion, cancel_deletion


@login_required
@require_http_methods(['GET', 'POST'])
def user_deletion(request, pk, cancel=False):
    if not request.user.is_superuser:
        raise Http404
    target = get_object_or_404(User, pk=pk, is_superuser=False, deleted_at__isnull=True)
    form = DeletionConfirmationForm(request.POST if request.method == 'POST' else None, actor=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            if cancel:
                cancel_deletion(actor=request.user, target_id=pk)
            else:
                schedule_deletion(actor=request.user, target_id=pk)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Eliminación cancelada.' if cancel else 'Eliminación programada; la cuenta quedó desactivada.')
            return redirect('users-manage')
    return render(request, 'accounts/deletion.html', {'form': form, 'target_user': target, 'cancel': cancel})
