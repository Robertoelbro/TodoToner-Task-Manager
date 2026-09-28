from datetime import timedelta
from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from .models import AssignmentChange, Task
from .services import reassign_task


@override_settings(SECURE_SSL_REDIRECT=False)
class TaskPermissionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.base = User.objects.create_user(username='base', first_name='Ana')
        cls.worker = User.objects.create_user(username='worker', first_name='Juan')
        cls.other = User.objects.create_user(username='other', first_name='Otro')
        cls.supervisor = User.objects.create_user(username='supervisor', is_supervisor=True)
        cls.inactive = User.objects.create_user(username='inactive', is_active=False)
        cls.task = Task.objects.create(title='Inventario', created_by=cls.base,
                                      deadline=timezone.localdate() + timedelta(days=4))
        cls.task.assignees.add(cls.worker)

    def setUp(self):
        self.client.force_login(self.base)

    def test_base_creates_task_with_multiple_assignees(self):
        response = self.client.post(reverse('task-create'), {
            'title': 'Contar cajas', 'description': 'Bodega',
            'deadline': (timezone.localdate() + timedelta(days=4)).isoformat(),
            'assignees': [self.worker.pk, self.supervisor.pk], 'created_by': self.other.pk,
        })
        task = Task.objects.get(title='Contar cajas')
        self.assertRedirects(response, reverse('task-detail', args=[task.pk]))
        self.assertEqual(task.created_by, self.base)
        self.assertSetEqual(set(task.assignees.all()), {self.worker, self.supervisor})
        self.assertEqual(task.assignment_changes.count(), 1)

    def test_assignment_form_shows_active_users(self):
        response = self.client.get(reverse('task-create'))
        self.assertContains(response, f'value="{self.worker.pk}"')
        choices = response.context['form'].fields['assignees'].queryset
        self.assertNotIn(self.inactive, choices)

    def test_invalid_deadline_empty_or_inactive_assignees(self):
        for extra in [
            {'deadline': (timezone.localdate() - timedelta(days=1)).isoformat()},
            {'assignees': []}, {'assignees': [self.inactive.pk]},
            {'assignees': [999999]},
        ]:
            with self.subTest(extra=extra):
                data = {'title': 'No crear', 'deadline': timezone.localdate().isoformat(),
                        'assignees': [self.worker.pk]}
                data.update(extra)
                response = self.client.post(reverse('task-create'), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
        self.assertFalse(Task.objects.filter(title='No crear').exists())

    def test_base_cannot_reassign_even_own_created_or_assigned_tasks(self):
        url = reverse('task-reassign', args=[self.task.pk])
        for user in [self.base, self.worker, self.other]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {'assignees': [user.pk]}).status_code, 403)
        self.assertSetEqual(set(self.task.assignees.all()), {self.worker})
        self.assertEqual(self.task.assignment_changes.count(), 0)

    def test_service_also_rejects_non_supervisor(self):
        with self.assertRaises(PermissionDenied):
            reassign_task(actor=self.base, task_id=self.task.pk, assignees=[self.base])

    def test_supervisor_reassigns_without_altering_other_fields_and_logs_history(self):
        self.client.force_login(self.supervisor)
        response = self.client.post(reverse('task-reassign', args=[self.task.pk]), {
            'assignees': [self.other.pk, self.base.pk], 'title': 'Tampered',
            'created_by': self.supervisor.pk, 'deadline': '2099-01-01',
        })
        self.assertRedirects(response, reverse('task-detail', args=[self.task.pk]))
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Inventario')
        self.assertEqual(self.task.created_by, self.base)
        self.assertEqual(self.task.deadline, timezone.localdate() + timedelta(days=4))
        self.assertSetEqual(set(self.task.assignees.all()), {self.other, self.base})
        change = self.task.assignment_changes.get()
        self.assertEqual(change.actor, self.supervisor)
        self.assertEqual(change.previous_assignees[0]['id'], self.worker.pk)

    def test_supervisor_cannot_leave_task_unassigned(self):
        self.client.force_login(self.supervisor)
        response = self.client.post(reverse('task-reassign', args=[self.task.pk]), {'assignees': []})
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(set(self.task.assignees.all()), {self.worker})

    def test_unrelated_user_cannot_read_task(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('task-detail', args=[self.task.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('task-list')), 'Inventario')
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(reverse('task-detail', args=[self.task.pk])).status_code, 200)

    def test_dashboard_is_supervisor_only_and_includes_workers_without_tasks(self):
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 403)
        self.client.force_login(self.supervisor)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Inventario')
        self.assertContains(response, 'Otro')
        self.assertContains(response, 'Sin tareas asignadas.')
        self.assertEqual(response.context['task_count'], 1)

    def test_login_required_and_csrf_enforced(self):
        self.client.logout()
        for name in ['task-list', 'task-create', 'dashboard']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.supervisor)
        response = client.post(reverse('task-reassign', args=[self.task.pk]), {'assignees': [self.base.pk]})
        self.assertEqual(response.status_code, 403)

    def test_deadline_day_is_not_overdue(self):
        with patch('tasks.models.timezone.localdate', return_value=self.task.deadline):
            self.assertFalse(self.task.is_overdue)
        with patch('tasks.models.timezone.localdate', return_value=self.task.deadline + timedelta(days=1)):
            self.assertTrue(self.task.is_overdue)

