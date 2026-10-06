from datetime import datetime, time, timezone as dt_timezone
from django.conf import settings
from django.db import models
from django.utils import timezone


class Zone(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField('Nombre', max_length=40)

    class Meta:
        ordering = ['pk']

    def __str__(self):
        return self.name


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = 'low', 'Baja'
        MEDIUM = 'medium', 'Media'
        HIGH = 'high', 'Alta'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        IN_PROGRESS = 'in_progress', 'En proceso'
        IN_REVIEW = 'in_review', 'En revisión'
        COMPLETED = 'completed', 'Finalizada'

    priority = models.CharField('Prioridad', max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField('Estado', max_length=20, choices=Status.choices, default=Status.PENDING)
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name='supervised_tasks', verbose_name='Supervisor a cargo',
        limit_choices_to={'is_supervisor': True, 'is_active': True})

    title = models.CharField('Título', max_length=160)
    description = models.TextField('Descripción', blank=True)
    start_date = models.DateField('Fecha de inicio', default=timezone.localdate)
    deadline = models.DateField('Fecha límite')
    start_time = models.TimeField('Hora de inicio', default=time(0, 0))
    deadline_time = models.TimeField('Hora límite', default=time(23, 59, 59))
    zones = models.ManyToManyField(Zone, related_name='tasks', verbose_name='Zonas')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name='created_tasks', verbose_name='Creada por')
    assignees = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='assigned_tasks',
                                      verbose_name='Responsables')
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='deleted_tasks')
    hidden_by = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='hidden_tasks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['deadline', '-created_at']

    @property
    def last_modification(self):
        if hasattr(self, 'modifications'):
            return next(iter(self.modifications), None)
        return self.changes.exclude(changes={}).select_related('actor').first()

    @property
    def starts_at(self):
        return timezone.make_aware(datetime.combine(self.start_date, self.start_time))

    @property
    def ends_at(self):
        return timezone.make_aware(datetime.combine(self.deadline, self.deadline_time))

    def urgency_at(self, now=None):
        if self.status == self.Status.COMPLETED:
            return 'completed'
        now = now or timezone.now()
        end = self.ends_at.astimezone(dt_timezone.utc)
        start = self.starts_at.astimezone(dt_timezone.utc)
        remaining = (end - now.astimezone(dt_timezone.utc)).total_seconds()
        duration = (end - start).total_seconds()
        if remaining <= 0:
            return 'overdue'
        if 0 < duration <= 86400:
            if remaining > duration * 2 / 3:
                return 'green'
            return 'yellow' if remaining > duration / 3 else 'red'
        if remaining < 86400:
            return 'red'
        return 'yellow' if remaining <= 172800 else 'green'

    @property
    def urgency(self):
        return self.urgency_at()

    @property
    def urgency_label(self):
        return {'green': 'En plazo', 'yellow': 'Próxima a vencer', 'red': 'Por vencer',
                'overdue': 'Vencida', 'completed': 'Finalizada'}[self.urgency]

    @property
    def is_overdue(self):
        return self.urgency == 'overdue'

    @property
    def can_hide(self):
        return not self.deleted_at and self.status != self.Status.IN_PROGRESS and (self.status == self.Status.COMPLETED or self.is_overdue)

    def __str__(self):
        return self.title


class AssignmentChange(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='assignment_changes')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    previous_assignees = models.JSONField(default=list)
    new_assignees = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']



class TaskChange(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='changes')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    summary = models.CharField(max_length=240)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
