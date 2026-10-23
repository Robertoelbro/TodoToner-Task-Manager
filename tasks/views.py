from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from accounts.models import User
from .forms import ReassignmentForm, TaskForm, TaskTrackingForm, DashboardFilterForm
from .models import AssignmentChange, Task, Zone, TaskChange, MonthlyGoal
from .services import reassign_task, snapshot, tracking_snapshot
from .permissions import involvement, team_access, can_work_task, can_supervise_task


def visible_tasks(user, include_deleted=False):
    queryset = Task.objects.select_related('created_by', 'supervisor').prefetch_related('assignees', 'zones', Prefetch('changes', queryset=TaskChange.objects.exclude(changes={}).select_related('actor'), to_attr='modifications'))
    if not include_deleted:
        queryset = queryset.filter(deleted_at__isnull=True)
    if not user.is_superuser:
        private_tasks = Task.objects.filter(assignees__is_superuser=True).exclude(assignees__is_superuser=False)
        queryset = queryset.exclude(pk__in=private_tasks.values('pk'))
    if user.is_superuser:
        return queryset
    shared = Q(spectators=user)
    if user.area_id:
        shared |= Q(spectator_areas=user.area_id)
    return queryset.filter(involvement(user) | team_access(user) | shared).distinct()


@login_required
@require_http_methods(['GET'])
def task_list(request):
    if request.user.can_supervise:
        return redirect('dashboard')
    return render(request, 'tasks/list.html', {'hub_zones': Zone.objects.all(), 'hub_items': hub_tasks(request.user), 'monthly_goals': current_goals(), 'goals_month': timezone.localdate(), 'tasks': hub_tasks(request.user), 'show_dismiss': True, 'alerts': deadline_alerts(request.user),
        'recent_changes': TaskChange.objects.filter(task__in=visible_tasks(request.user)).select_related('task', 'actor')[:20]})


@login_required
@require_http_methods(['GET', 'POST'])
def task_create(request, parent_pk=None):
    parent = get_object_or_404(visible_tasks(request.user), pk=parent_pk) if parent_pk else None
    if parent and not can_work_task(request.user, parent):
        raise PermissionDenied
    form = TaskForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            task = form.save(commit=False)
            task.created_by = request.user
            task.parent = parent
            task.save()
            form.save_m2m()
            TaskChange.objects.create(task=task, actor=request.user, summary='Tarea creada')
            AssignmentChange.objects.create(task=task, actor=request.user,
                                            new_assignees=snapshot(task.assignees.all()))
        messages.success(request, 'Tarea creada y responsables asignados.')
        return redirect('task-detail', pk=task.pk) if visible_tasks(request.user).filter(pk=task.pk).exists() else redirect('task-list')
    return render(request, 'tasks/form.html', {'form': form, 'heading': 'Nueva subtarea' if parent else 'Nueva tarea', 'button': 'Crear tarea', 'task': parent})


@login_required
@require_http_methods(['GET'])
def task_detail(request, pk):
    task = get_object_or_404(visible_tasks(request.user, include_deleted=True), pk=pk)
    return render(request, 'tasks/detail.html', {'task': task,
                  'can_work': can_work_task(request.user, task),
                  'can_manage': can_supervise_task(request.user, task),
                  'subtasks': visible_tasks(request.user).filter(parent=task),
                  'visible_parent': visible_tasks(request.user).filter(pk=task.parent_id).first() if task.parent_id else None,
                  'changes': task.assignment_changes.select_related('actor'),
                  'task_events': task.changes.select_related('actor')})


@login_required
@require_http_methods(['GET', 'POST'])
def task_reassign(request, pk):
    if not request.user.can_supervise:
        raise PermissionDenied
    task = get_object_or_404(visible_tasks(request.user), pk=pk)
    if not can_supervise_task(request.user, task):
        raise PermissionDenied
    form = ReassignmentForm(request.POST if request.method == 'POST' else None, instance=task)
    if request.method == 'POST' and form.is_valid():
        reassign_task(actor=request.user, task_id=task.pk, assignees=form.cleaned_data['assignees'])
        messages.success(request, 'Responsables actualizados.')
        return redirect('task-detail', pk=task.pk) if visible_tasks(request.user).filter(pk=task.pk).exists() else redirect('task-list')
    return render(request, 'tasks/form.html', {'form': form, 'heading': 'Cambiar responsables',
                  'button': 'Guardar responsables', 'task': task})


@login_required
@require_http_methods(['GET'])
def gantt_view(request):
    from .gantt import build_timeline
    period_params = request.GET.copy()
    if not period_params.get('month') and not period_params.get('year'):
        today = timezone.localdate()
        period_params['month'], period_params['year'] = str(today.month), str(today.year)
    form = DashboardFilterForm(period_params)
    queryset = visible_tasks(request.user).annotate(
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
    from calendar import monthrange
    from datetime import date
    today = timezone.localdate()
    year = filters.get('year') or today.year
    month = filters.get('month')
    date_from = date(year, month or 1, 1)
    date_to = date(year, month or 12, monthrange(year, month or 12)[1])
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
    task = get_object_or_404(visible_tasks(request.user), pk=pk)
    task = Task.objects.select_for_update().get(pk=task.pk, deleted_at__isnull=True)
    get_object_or_404(visible_tasks(request.user), pk=pk)
    if not can_work_task(request.user, task):
        raise PermissionDenied
    before = tracking_snapshot(task)
    from .forms import TaskStatusForm
    form_class = TaskTrackingForm if can_supervise_task(request.user, task) else TaskStatusForm
    form = form_class(request.POST if request.method == 'POST' else None, instance=task)
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
        'form': form, 'heading': 'Actualizar seguimiento' if can_supervise_task(request.user, task) else 'Actualizar estado', 'button': 'Guardar cambios', 'task': task,
    })


@login_required
@require_http_methods(['GET'])
def dashboard(request):
    if not request.user.can_supervise:
        raise PermissionDenied
    return render(request, 'tasks/dashboard.html', {
        'hub_zones': Zone.objects.all(), 'hub_items': hub_tasks(request.user),
        'monthly_goals': current_goals(), 'goals_month': timezone.localdate(),
        'alerts': deadline_alerts(request.user),
        'personal_tasks': hub_tasks(request.user, personal=True), 'show_dismiss': True,
        'recent_changes': TaskChange.objects.filter(task__in=visible_tasks(request.user)).select_related('task', 'actor')[:20],
    })


def deadline_alerts(user):
    tasks = [task for task in hub_tasks(user) if task.status != Task.Status.COMPLETED]
    now = timezone.now()
    return sorted([t for t in tasks if t.urgency_at(now) in ('yellow', 'overdue')], key=lambda t: t.ends_at)


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
        'urgent_count': sum(t.urgency_at(now) == 'overdue' for t in tasks),
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
    tasks = visible_tasks(request.user, include_deleted=True).order_by('-created_at', '-pk')
    from .forms import HistoryFilterForm
    form = HistoryFilterForm(request.GET)
    if form.is_valid():
        filters = form.cleaned_data
        if filters.get('worker'):
            tasks = tasks.filter(assignees=filters['worker'])
        if filters.get('zone'):
            tasks = tasks.filter(zones=filters['zone'])
        if filters.get('status'):
            tasks = tasks.filter(status=filters['status'])
        if filters.get('year'):
            tasks = tasks.filter(created_at__year=filters['year'])
        if filters.get('month'):
            tasks = tasks.filter(created_at__month=filters['month'])
    else:
        tasks = tasks.none()
    page = Paginator(tasks.distinct(), 50).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'tasks/history.html', {'page': page, 'filter_form': form,
        'filter_query': params.urlencode()})


@login_required
@require_http_methods(['POST'])
@transaction.atomic
def task_hide(request, pk):
    # Lock only the task row: PostgreSQL cannot lock a DISTINCT joined query.
    task = get_object_or_404(Task.objects.select_for_update(), pk=pk, deleted_at__isnull=True)
    if not visible_tasks(request.user).filter(pk=pk).exists():
        from django.http import Http404
        raise Http404
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
    get_object_or_404(visible_tasks(request.user, include_deleted=True), pk=pk)
    task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
    get_object_or_404(visible_tasks(request.user, include_deleted=True), pk=pk)
    if not can_supervise_task(request.user, task):
        raise PermissionDenied
    if request.method == 'POST':
        if request.POST.get('confirm') != 'yes':
            return render(request, 'tasks/delete.html', {'task': task, 'error': 'Confirma la eliminación.'}, status=400)
        task.delete()
        messages.success(request, 'Tarea eliminada definitivamente de la base de datos.')
        return redirect('task-history')
    return render(request, 'tasks/delete.html', {'task': task})


@require_http_methods(['GET'])
def server_time(request):
    from django.http import JsonResponse
    from django.conf import settings
    response = JsonResponse({'timestamp': timezone.now().timestamp() * 1000, 'timezone': settings.TIME_ZONE})
    response['Cache-Control'] = 'no-store'
    return response


def current_goals():
    return MonthlyGoal.objects.filter(month=timezone.localdate().replace(day=1)).select_related('created_by').prefetch_related('zones')


@login_required
@require_http_methods(['GET', 'POST'])
def monthly_goal_create(request):
    if not request.user.can_supervise:
        raise PermissionDenied
    from .forms import MonthlyGoalForm
    form = MonthlyGoalForm(request.POST if request.method == 'POST' else None,
                           initial={'month': timezone.localdate().replace(day=1)})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            goal = form.save(commit=False)
            goal.created_by = request.user
            goal.save()
            form.save_m2m()
        messages.success(request, 'Meta mensual creada. Se mostrará en el hub de todos durante el mes seleccionado.')
        return redirect('task-list')
    return render(request, 'tasks/goal_form.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def task_audience(request, pk):
    from .forms import TaskAudienceForm
    get_object_or_404(visible_tasks(request.user), pk=pk)
    task = get_object_or_404(Task.objects.select_for_update(), pk=pk, deleted_at__isnull=True)
    get_object_or_404(visible_tasks(request.user), pk=pk)
    if not can_work_task(request.user, task):
        raise PermissionDenied
    form = TaskAudienceForm(request.POST if request.method == 'POST' else None, instance=task)
    before_label = audience_label(task)
    before = (list(task.spectators.order_by('pk').values_list('pk', flat=True)),
              list(task.spectator_areas.order_by('pk').values_list('pk', flat=True)))
    if request.method == 'POST' and form.is_valid():
        form.save()
        after = (list(task.spectators.order_by('pk').values_list('pk', flat=True)),
                 list(task.spectator_areas.order_by('pk').values_list('pk', flat=True)))
        if before != after:
            TaskChange.objects.create(task=task, actor=request.user, summary='Espectadores actualizados',
                changes={'Visibilidad': {'before': before_label, 'after': audience_label(task)}})
        return redirect('task-detail', pk=task.pk)
    return render(request, 'tasks/form.html', {'form': form, 'heading': 'Quién puede visualizar mi tarea', 'button': 'Guardar espectadores', 'task': task})


def audience_label(task):
    return 'Personas: ' + (', '.join(str(u) for u in task.spectators.order_by('pk')) or 'Ninguna') + '; áreas: ' + (', '.join(str(a) for a in task.spectator_areas.order_by('pk')) or 'Ninguna')
