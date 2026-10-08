from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from .models import Task, TaskChange


@override_settings(SECURE_SSL_REDIRECT=False)
class ManagementPrivacyTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user('manager', is_superuser=True)
        self.supervisor = User.objects.create_user('supervisor', is_supervisor=True)
        self.base = User.objects.create_user('base')
        self.task = Task.objects.create(title='CONFIDENCIAL_GERENCIA', created_by=self.base, deadline=timezone.localdate())
        self.task.assignees.add(self.manager)
        TaskChange.objects.create(task=self.task, actor=self.manager, summary='Cambio privado')

    def test_private_task_absent_from_every_listing_and_direct_routes(self):
        for user in (self.supervisor, self.base):
            self.client.force_login(user)
            for route in ('task-list', 'task-history', 'task-alerts'):
                self.assertNotContains(self.client.get(reverse(route), follow=True), self.task.title)
            if user.can_supervise:
                for route in ('dashboard', 'gantt', 'tv-dashboard'):
                    self.assertNotContains(self.client.get(reverse(route)), self.task.title)
                for route in ('task-reassign', 'task-tracking', 'task-delete'):
                    self.assertEqual(self.client.get(reverse(route, args=[self.task.pk])).status_code, 404)
                    self.assertEqual(self.client.post(reverse(route, args=[self.task.pk]), {'confirm': 'yes'}).status_code, 404)
            self.assertEqual(self.client.get(reverse('task-detail', args=[self.task.pk])).status_code, 404)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_management_can_see_and_created_by_is_not_private_alone(self):
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(reverse('task-detail', args=[self.task.pk])), self.task.title)
        public = Task.objects.create(title='Encargo al equipo', created_by=self.manager, deadline=timezone.localdate())
        public.assignees.add(self.base)
        self.client.force_login(self.base)
        self.assertContains(self.client.get(reverse('task-detail', args=[public.pk])), public.title)

    def test_shared_management_tasks_keep_normal_visibility(self):
        self.task.assignees.add(self.base)
        for user in (self.base, self.supervisor):
            self.client.force_login(user)
            self.assertContains(self.client.get(reverse('task-detail', args=[self.task.pk])), self.task.title)
            self.assertContains(self.client.get(reverse('task-history')), self.task.title)
