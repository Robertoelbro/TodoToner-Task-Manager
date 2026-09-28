from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from accounts.models import User
from .forms import ReassignmentForm, TaskForm
from .models import AssignmentChange, Task
from .services import reassign_task, snapshot


def visible_tasks(user):
    queryset = Task.objects.select_related('created_by').prefetch_related('assignees')
    if user.is_supervisor:
        return queryset
    return queryset.filter(Q(assignees=user) | Q(created_by=user)).distinct()


@login_required
@require_http_methods(['GET'])
def task_list(request):
    return render(request, 'tasks/list.html', {'tasks': visible_tasks(request.user)})


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
            AssignmentChange.objects.create(task=task, actor=request.user,
                                            new_assignees=snapshot(task.assignees.all()))
        messages.success(request, 'Tarea creada y responsables asignados.')
        return redirect('task-detail', pk=task.pk)
    return render(request, 'tasks/form.html', {'form': form, 'heading': 'Nueva tarea', 'button': 'Crear tarea'})


@login_required
@require_http_methods(['GET'])
def task_detail(request, pk):
    task = get_object_or_404(visible_tasks(request.user), pk=pk)
    return render(request, 'tasks/detail.html', {'task': task,
                  'changes': task.assignment_changes.select_related('actor')})


@login_required
@require_http_methods(['GET', 'POST'])
def task_reassign(request, pk):
    if not request.user.is_supervisor:
        raise PermissionDenied
    task = get_object_or_404(Task, pk=pk)
    form = ReassignmentForm(request.POST if request.method == 'POST' else None, instance=task)
    if request.method == 'POST' and form.is_valid():
        reassign_task(actor=request.user, task_id=task.pk, assignees=form.cleaned_data['assignees'])
        messages.success(request, 'Responsables actualizados.')
        return redirect('task-detail', pk=task.pk)
    return render(request, 'tasks/form.html', {'form': form, 'heading': 'Cambiar responsables',
                  'button': 'Guardar responsables', 'task': task})


@login_required
@require_http_methods(['GET'])
def dashboard(request):
    if not request.user.is_supervisor:
        raise PermissionDenied
    tasks = Task.objects.prefetch_related('assignees')
    workers = User.objects.order_by('-is_active', 'first_name', 'username').prefetch_related(
        Prefetch('assigned_tasks', queryset=tasks))
    return render(request, 'tasks/dashboard.html', {
        'workers': workers, 'worker_count': workers.count(), 'task_count': tasks.count(),
        'overdue_count': tasks.filter(deadline__lt=timezone.localdate()).count(),
    })

