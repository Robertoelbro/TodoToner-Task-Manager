from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import AssignmentChange, Task, TaskChange


def snapshot(users):
    return [{'id': user.pk, 'name': user.display_name} for user in sorted(users, key=lambda u: u.pk)]


@transaction.atomic
def reassign_task(*, actor, task_id, assignees):
    if not actor.is_active or not actor.can_supervise:
        raise PermissionDenied('Solo un supervisor puede reasignar tareas.')
    assignees = list(assignees)
    if not assignees or any(not user.is_active for user in assignees):
        raise ValidationError('Selecciona al menos un responsable activo.')
    task = Task.objects.select_for_update().get(pk=task_id, deleted_at__isnull=True)
    from .permissions import can_supervise_task
    if not can_supervise_task(actor, task):
        raise PermissionDenied
    if (not actor.is_superuser and task.assignees.filter(is_superuser=True).exists()
            and not task.assignees.filter(is_superuser=False).exists()):
        raise PermissionDenied('Esta tarea es privada de gerencia.')
    previous = snapshot(task.assignees.all())
    current = snapshot(assignees)
    if previous != current:
        task.assignees.set(assignees)
        TaskChange.objects.create(task=task, actor=actor, summary='Responsables actualizados',
            changes={'Responsables': {'before': ', '.join(u['name'] for u in previous), 'after': ', '.join(u['name'] for u in current)}})
        AssignmentChange.objects.create(task=task, actor=actor,
                                        previous_assignees=previous, new_assignees=current)
    return task



def tracking_snapshot(task):
    return {
        'Prioridad': task.get_priority_display(), 'Estado': task.get_status_display(),
        'Supervisor': task.supervisor.display_name if task.supervisor else 'Sin asignar',
        'Inicio': task.starts_at.isoformat(), 'Fecha límite': task.ends_at.isoformat(),
        'Zonas': ', '.join(task.zones.order_by('pk').values_list('name', flat=True)) or 'Sin asignar',
    }
