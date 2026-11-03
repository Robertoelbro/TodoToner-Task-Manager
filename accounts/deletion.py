from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .models import User


def after_business_days(now, days=5):
    local = timezone.localtime(now)
    while days:
        local += timedelta(days=1)
        if local.weekday() < 5:
            days -= 1
    return local


def finalize_due_deletions():
    now = timezone.now()
    return User.objects.filter(deletion_due_at__lte=now, deleted_at__isnull=True,
                               is_superuser=False).update(deleted_at=now, is_active=False)


def require_management(actor):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied


@transaction.atomic
def schedule_deletion(*, actor, target_id):
    require_management(actor)
    target = User.objects.select_for_update().get(pk=target_id)
    if target.is_superuser or target.pk == actor.pk:
        raise PermissionDenied
    if target.deleted_at or target.deletion_due_at:
        raise ValidationError('La cuenta ya tiene una eliminación programada o completada.')
    target.deletion_was_active = target.is_active
    target.deletion_requested_by = actor
    target.deletion_due_at = after_business_days(timezone.now())
    target.is_active = False
    target.onboarding_nonce = ''
    target.save(update_fields=['deletion_was_active', 'deletion_requested_by', 'deletion_due_at', 'is_active', 'onboarding_nonce'])
    return target


@transaction.atomic
def cancel_deletion(*, actor, target_id):
    require_management(actor)
    target = User.objects.select_for_update().get(pk=target_id)
    if target.is_superuser:
        raise PermissionDenied
    if not target.can_cancel_deletion:
        raise ValidationError('El plazo para cancelar terminó o no existe una eliminación pendiente.')
    target.is_active = target.deletion_was_active
    target.deletion_due_at = None
    target.deletion_requested_by = None
    target.save(update_fields=['is_active', 'deletion_due_at', 'deletion_requested_by'])
    return target


@transaction.atomic
def delete_now(*, actor, target_id):
    require_management(actor)
    target = User.objects.select_for_update().get(pk=target_id)
    if target.is_superuser or target.pk == actor.pk:
        raise PermissionDenied
    if not target.can_cancel_deletion:
        raise ValidationError('No existe una eliminación programada que se pueda adelantar.')
    now = timezone.now()
    target.deleted_at = now
    target.deletion_due_at = now
    target.deletion_requested_by = actor
    target.is_active = False
    target.onboarding_nonce = ''
    target.save(update_fields=['deleted_at', 'deletion_due_at', 'deletion_requested_by', 'is_active', 'onboarding_nonce'])
    return target


class FinalizeDeletionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        finalize_due_deletions()
        return self.get_response(request)

