from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import AssignmentChange, Task


def snapshot(users):
    return [{'id': user.pk, 'name': user.display_name} for user in sorted(users, key=lambda u: u.pk)]


@transaction.atomic
def reassign_task(*, actor, task_id, assignees):
    if not actor.is_active or not actor.is_supervisor:
        raise PermissionDenied('Solo un supervisor puede reasignar tareas.')
    assignees = list(assignees)
    if not assignees or any(not user.is_active for user in assignees):
        raise ValidationError('Selecciona al menos un responsable activo.')
    task = Task.objects.select_for_update().get(pk=task_id)
    previous = snapshot(task.assignees.all())
    current = snapshot(assignees)
    if previous != current:
        task.assignees.set(assignees)
        AssignmentChange.objects.create(task=task, actor=actor,
                                        previous_assignees=previous, new_assignees=current)
    return task

