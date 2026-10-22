from django.db.models import Q


def involvement(user):
    return Q(created_by=user) | Q(assignees=user) | Q(supervisor=user)


def team_access(user):
    return Q(assignees__area_id=user.area_id) if user.is_supervisor and user.area_id else Q(pk__in=[])


def can_supervise_task(user, task):
    if user.is_superuser:
        return True
    if not user.is_supervisor:
        return False
    return type(task).objects.filter(pk=task.pk).filter(involvement(user) | team_access(user)).exists()


def can_work_task(user, task):
    return can_supervise_task(user, task) or task.created_by_id == user.pk or task.assignees.filter(pk=user.pk).exists()
