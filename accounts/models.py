from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    area = models.ForeignKey('tasks.Zone', null=True, blank=True, on_delete=models.PROTECT,
                             related_name='members', verbose_name='Área')
    must_complete_profile = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    onboarding_nonce = models.CharField(max_length=64, blank=True, editable=False)

    def issue_temporary_password(self):
        import secrets
        from django.utils.crypto import salted_hmac
        self.onboarding_nonce = secrets.token_hex(32)
        password = salted_hmac('turno.onboarding', self.onboarding_nonce, algorithm='sha256').hexdigest()[:24]
        self.set_password(password)
        return password

    @property
    def temporary_password(self):
        from django.conf import settings
        from django.utils.crypto import salted_hmac
        if not (self.must_complete_profile or self.must_change_password) or not self.onboarding_nonce or not self.is_active or self.deletion_due_at or self.deleted_at:
            return None
        for key in [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]:
            candidate = salted_hmac('turno.onboarding', self.onboarding_nonce, secret=key, algorithm='sha256').hexdigest()[:24]
            if self.check_password(candidate):
                return candidate
        return None
    deletion_due_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_was_active = models.BooleanField(default=True)
    deletion_requested_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='requested_deletions')

    @property
    def can_cancel_deletion(self):
        from django.utils import timezone
        return self.deletion_due_at is not None and self.deleted_at is None and timezone.now() < self.deletion_due_at

    is_supervisor = models.BooleanField('Es supervisor', default=False)


    @property
    def can_supervise(self):
        return self.is_supervisor or self.is_superuser

    @property
    def role_label(self):
        return 'Gerencia' if self.is_superuser else ('Supervisor' if self.is_supervisor else 'Usuario base')

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return self.display_name

