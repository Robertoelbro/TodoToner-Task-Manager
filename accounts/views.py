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
    import secrets
    from django.utils.text import slugify
    form = ManagedCreationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.username = (slugify(user.first_name + '.' + user.last_name)[:110] or 'usuario') + '-' + secrets.token_hex(4)
        password = form.cleaned_data['temporary_password'] or secrets.token_urlsafe(15)
        user.set_password(password)
        user.must_complete_profile = True
        user.is_superuser = user.is_supervisor = user.is_staff = False
        user.save()
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
        form = CompleteProfileForm(user, request.POST if request.method == 'POST' else None)
        if request.method == 'POST' and form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Tu cuenta está lista.')
            return redirect('task-list')
    return render(request, 'accounts/complete_profile.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def users_manage(request, pk=None):
    if not request.user.is_superuser:
        raise Http404
    # Gerencia no cambia sus propios privilegios ni los de otra cuenta gerencial.
    target = get_object_or_404(User.objects.select_for_update(), pk=pk, is_superuser=False, deleted_at__isnull=True, deletion_due_at__isnull=True) if pk is not None else None
    form = ManagedUserForm(request.POST if request.method == 'POST' else None, instance=target) if target else None
    if request.method == 'POST':
        if target is None:
            raise Http404
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario actualizado.')
            return redirect('users-manage')
    if target is None and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        response = render(request, 'accounts/people.html', {'people': filter_people(request.GET.get('q', ''))})
        response['X-Turno-Fragment'] = 'users'
        response['Cache-Control'] = 'no-store'
        return response
    return render(request, 'accounts/manage.html', {
        'people': filter_people(request.GET.get('q', '')), 'query': request.GET.get('q', ''), 'form': form, 'target_user': target,
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
