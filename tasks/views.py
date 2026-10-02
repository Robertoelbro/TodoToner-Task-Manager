from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from accounts.models import User
from .forms import ReassignmentForm, TaskForm, TaskTrackingForm, DashboardFilterForm
from .models import AssignmentChange, Task, Zone, TaskChange
from .services import reassign_task, snapshot, tracking_snapshot


def visible_tasks(user, include_deleted=False):
    queryset = Task.objects.select_related('created_by', 'supervisor').prefetch_related('assignees', 'zones')
    if not include_deleted:
        queryset = queryset.filter(deleted_at__isnull=True)
    if user.can_supervise:
        return queryset
    return queryset.filter(Q(assignees=user) | Q(created_by=user)).distinct()


@login_required
@require_http_methods(['GET'])
def task_list(request):
    if request.user.can_supervise:
        return redirect('dashboard')
    return render(request, 'tasks/list.html', {'tasks': hub_tasks(request.user), 'show_dismiss': True, 'alerts': deadline_alerts(request.user),
        'recent_changes': TaskChange.objects.filter(task__in=visible_tasks(request.user)).select_related('task', 'actor')[:20]})


@login_required
@require_http_methods(['GET', 'POST'])
def task_create(request):
    form = TaskForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            form.save_m2m()
            TaskChange.objects.create(task=task, actor=request.user, summary='Tarea creada')
            AssignmentChange.objects.create(task=task, actor=request.user,
                                            new_assignees=snapshot(task.assignees.all()))
        messages.success(request, 'Tarea creada y responsables asignados.')
        return redirect('task-detail', pk=task.pk)
    return render(request, 'tasks/form.html', {'form': form, 'heading': 'Nueva tarea', 'button': 'Crear tarea'})


@login_required
@require_http_methods(['GET'])
def task_detail(request, pk):
    task = get_object_or_404(visible_tasks(request.user, include_deleted=True), pk=pk)
    return render(request, 'tasks/detail.html', {'task': task,
                  'changes': task.assignment_changes.select_related('actor')})


@login_required
@require_http_methods(['GET', 'POST'])
def task_reassign(request, pk):
    if not request.user.can_supervise:
        raise PermissionDenied
    task = get_object_or_404(Task, pk=pk, deleted_at__isnull=True)
    form = ReassignmentForm(request.POST if request.method == 'POST' else None, instance=task)
    if request.method == 'POST' and form.is_valid():
        reassign_task(actor=request.user, task_id=task.pk, assignees=form.cleaned_data['assignees'])
        messages.success(request, 'Responsables actualizados.')
        return redirect('task-detail', pk=task.pk)
    return render(request, 'tasks/form.html', {'form': form, 'heading': 'Cambiar responsables',
                  'button': 'Guardar responsables', 'task': task})


@login_required
@require_http_methods(['GET'])
def gantt_view(request):
    if not request.user.can_supervise:
        raise PermissionDenied
    from .gantt import build_timeline
    form = DashboardFilterForm(request.GET)
    queryset = Task.objects.filter(deleted_at__isnull=True).select_related('supervisor').prefetch_related('assignees', 'zones').annotate(
        responsible_count=Count('assignees', distinct=True))
    valid = form.is_valid()
    filters = form.cleaned_data if valid else {}
    if not valid:
        queryset = queryset.none()
    if filters.get('zone'):
        queryset = queryset.filter(zones=filters['zone'])
    if filters.get('worker'):
        queryset = queryset.filter(assignees=filters['worker'])
    if filters.get('priority'):
        queryset = queryset.filter(priority=filters['priority'])
    if filters.get('supervisor'):
        queryset = queryset.filter(supervisor=filters['supervisor'])
    if filters.get('status'):
        queryset = queryset.filter(status=filters['status'])
    if filters.get('multiple'):
        queryset = queryset.filter(responsible_count__gt=1)
    if filters.get('date_from'):
        queryset = queryset.filter(deadline__gte=filters['date_from'])
    if filters.get('date_to'):
        queryset = queryset.filter(start_date__lte=filters['date_to'])
    from calendar import monthrange
    anchor = filters.get('date_from') or filters.get('date_to') or timezone.localdate()
    date_from = filters.get('date_from') or anchor.replace(day=1)
    date_to = filters.get('date_to') or anchor.replace(day=monthrange(anchor.year, anchor.month)[1])
    queryset = queryset.filter(deadline__gte=date_from, start_date__lte=date_to)
    filtered = list(queryset.distinct())
    overdue_only = request.GET.get('overdue') == '1'
    overdue_count = sum(t.is_overdue for t in filtered)
    if overdue_only:
        filtered = [t for t in filtered if t.is_overdue]
    toggle_params = request.GET.copy()
    if overdue_only:
        toggle_params.pop('overdue', None)
    else:
        toggle_params['overdue'] = '1'
    timeline = build_timeline(filtered, date_from, date_to)
    groups = []
    for zone in Zone.objects.all():
        if filters.get('zone') and filters['zone'] != zone:
            continue
        rows = [row for row in timeline['rows'] if zone in row['task'].zones.all()]
        groups.append({'name': zone.name, 'rows': rows})
    unassigned = [row for row in timeline['rows'] if not row['task'].zones.all()]
    if unassigned:
        groups.append({'name': 'Sin zona asignada', 'rows': unassigned})
    template = 'tasks/gantt_section.html' if request.headers.get('X-Requested-With') == 'XMLHttpRequest' else 'tasks/gantt_page.html'
    response = render(request, template, {
        'filter_form': form, 'timeline': timeline, 'zone_groups': groups,
        'task_count': len(filtered), 'worker_count': len({u.pk for t in filtered for u in t.assignees.all()}),
        'overdue_count': overdue_count, 'overdue_only': overdue_only,
        'overdue_url': '?' + toggle_params.urlencode(),
    })
    response['X-Turno-Fragment'] = 'gantt'
    response['Vary'] = 'X-Requested-With'
    response['Cache-Control'] = 'no-store'
    return response



@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def task_tracking(request, pk):
    if not request.user.can_supervise:
        raise PermissionDenied
    task = get_object_or_404(Task, pk=pk, deleted_at__isnull=True)
    task = Task.objects.select_for_update().get(pk=task.pk, deleted_at__isnull=True)
    before = tracking_snapshot(task)
    form = TaskTrackingForm(request.POST if request.method == 'POST' else None, instance=task)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
            if not task.can_hide:
                task.hidden_by.clear()
            after = tracking_snapshot(task)
            changes = {key: {'before': value, 'after': after[key]} for key, value in before.items() if value != after[key]}
            if changes:
                TaskChange.objects.create(task=task, actor=request.user, summary='Seguimiento actualizado', changes=changes)
        messages.success(request, 'Seguimiento de la tarea actualizado.')
        return redirect('task-detail', pk=task.pk)
    return render(request, 'tasks/form.html', {
        'form': form, 'heading': 'Actualizar seguimiento', 'button': 'Guardar cambios', 'task': task,
    })


@login_required
@require_http_methods(['GET'])
def dashboard(request):
    if not request.user.can_supervise:
        raise PermissionDenied
    return render(request, 'tasks/dashboard.html', {
        'alerts': deadline_alerts(request.user),
        'personal_tasks': hub_tasks(request.user, personal=True), 'show_dismiss': True,
        'recent_changes': TaskChange.objects.select_related('task', 'actor')[:20],
    })


def deadline_alerts(user):
    tasks = [task for task in hub_tasks(user) if task.status != Task.Status.COMPLETED]
    now = timezone.now()
    return sorted([t for t in tasks if t.urgency_at(now) in ('yellow', 'red', 'overdue')], key=lambda t: t.ends_at)


@login_required
@require_http_methods(['GET'])
def task_alerts(request):
    response = render(request, 'tasks/alerts.html', {'alerts': deadline_alerts(request.user)})
    response['X-Turno-Fragment'] = 'alerts'
    response['Cache-Control'] = 'no-store'
    return response


@login_required
@require_http_methods(['GET'])
def tv_dashboard(request):
    if not request.user.can_supervise:
        raise PermissionDenied
    from django.core.paginator import Paginator
    tasks = list(visible_tasks(request.user).exclude(status=Task.Status.COMPLETED))
    tasks.sort(key=lambda task: (task.ends_at, task.pk))
    now = timezone.now()
    page = Paginator(tasks, 6).get_page(request.GET.get('page', 1))
    context = {
        'page': page, 'active_count': len(tasks),
        'urgent_count': sum(t.urgency_at(now) in ('red', 'overdue') for t in tasks),
        'warning_count': sum(t.urgency_at(now) == 'yellow' for t in tasks),
        'updated_at': now,
    }
    fragment = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    response = render(request, 'tasks/tv_content.html' if fragment else 'tasks/tv.html', context)
    response['X-Turno-Fragment'] = 'tv'
    response['Vary'] = 'X-Requested-With'
    response['Cache-Control'] = 'no-store'
    return response


def hub_tasks(user, personal=False):
    queryset = visible_tasks(user)
    if personal:
        queryset = queryset.filter(Q(assignees=user) | Q(created_by=user)).distinct()
    hidden = set(user.hidden_tasks.values_list('pk', flat=True))
    return [task for task in queryset if task.pk not in hidden or not task.can_hide]


@login_required
@require_http_methods(['GET'])
def task_history(request):
    from django.core.paginator import Paginator
    tasks = visible_tasks(request.user, include_deleted=True).filter(
        Q(status=Task.Status.COMPLETED) | Q(hidden_by=request.user) | Q(deleted_at__isnull=False)
    ).distinct().order_by('-created_at', '-pk')
    page = Paginator(tasks, 24).get_page(request.GET.get('page'))
    return render(request, 'tasks/history.html', {'page': page})


@login_required
@require_http_methods(['POST'])
@transaction.atomic
def task_hide(request, pk):
    task = get_object_or_404(visible_tasks(request.user).select_for_update(), pk=pk)
    if not task.can_hide:
        raise PermissionDenied('Solo puedes ocultar tareas vencidas o finalizadas que no estén en proceso.')
    task.hidden_by.add(request.user)
    messages.success(request, 'Tarea oculta en tu hub. Puedes consultarla en Historial.')
    return redirect('task-list')


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def task_delete(request, pk):
    if not request.user.can_supervise:
        raise PermissionDenied
    task = get_object_or_404(Task.objects.select_for_update(), pk=pk, deleted_at__isnull=True)
    if request.method == 'POST':
        if request.POST.get('confirm') != 'yes':
            return render(request, 'tasks/delete.html', {'task': task, 'error': 'Confirma la eliminación.'}, status=400)
        task.deleted_at = timezone.now()
        task.deleted_by = request.user
        task.save(update_fields=['deleted_at', 'deleted_by'])
        TaskChange.objects.create(task=task, actor=request.user, summary='Tarea eliminada (conservada en historial)')
        messages.success(request, 'Tarea eliminada de las vistas activas y conservada en Historial.')
        return redirect('task-history')
    return render(request, 'tasks/delete.html', {'task': task})


@require_http_methods(['GET'])
def server_time(request):
    from django.http import JsonResponse
    from django.conf import settings
    response = JsonResponse({'timestamp': timezone.now().timestamp() * 1000, 'timezone': settings.TIME_ZONE})
    response['Cache-Control'] = 'no-store'
    return response
