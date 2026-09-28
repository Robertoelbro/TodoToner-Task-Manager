from django.conf import settings
from django.db import models
from django.utils import timezone


class Task(models.Model):
    title = models.CharField('Título', max_length=160)
    description = models.TextField('Descripción', blank=True)
    deadline = models.DateField('Fecha límite')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name='created_tasks', verbose_name='Creada por')
    assignees = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='assigned_tasks',
                                      verbose_name='Responsables')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['deadline', '-created_at']

    @property
    def is_overdue(self):
        return self.deadline < timezone.localdate()

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

