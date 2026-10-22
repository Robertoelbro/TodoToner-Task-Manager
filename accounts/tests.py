from django.test import TestCase, override_settings
from django.urls import reverse
from .models import User


@override_settings(SECURE_SSL_REDIRECT=False)
class AccountTests(TestCase):
    def test_public_registration_closed(self):
        response = self.client.post(reverse('register'), {'username': 'ana', 'is_superuser': 'on'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(User.objects.exists())

    def test_login_logout_and_inactive_account(self):
        user = User.objects.create_user(username='ana', password='Test-pass-9417!')
        response = self.client.post(reverse('login'), {'username': 'ana', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('login'), {'username': 'ana', 'password': 'Test-pass-9417!'})
        self.assertRedirects(response, reverse('task-list'))
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)
        user.is_active = False
        user.save()
        self.assertFalse(self.client.login(username='ana', password='Test-pass-9417!'))

    def test_external_login_redirect_rejected(self):
        User.objects.create_user(username='ana', password='Test-pass-9417!')
        response = self.client.post(reverse('login'), {
            'username': 'ana', 'password': 'Test-pass-9417!', 'next': 'https://example.com/',
        })
        self.assertRedirects(response, reverse('task-list'))


@override_settings(SECURE_SSL_REDIRECT=False)
class ManagementTests(TestCase):
    def setUp(self):
        from tasks.models import Zone
        self.area = Zone.objects.get(code='ventas')
        self.boss = User.objects.create_superuser(username='boss', password='Test-pass-9417!')
        self.worker = User.objects.create_user(username='roberto', first_name='Roberto', last_name='Pérez')
        self.supervisor = User.objects.create_user(username='sup', is_supervisor=True)

    def test_labels_only_show_registered_name(self):
        from tasks.forms import TaskForm, DashboardFilterForm
        self.assertEqual(str(self.worker), 'Roberto Pérez')
        choices = str(TaskForm()['assignees'])
        self.assertIn('Roberto Pérez', choices)
        self.assertNotIn('@roberto', choices)
        self.supervisor.first_name = 'Laura'
        self.supervisor.save()
        self.assertIn('Laura', str(DashboardFilterForm()['supervisor']))
        self.assertNotIn('@sup', str(DashboardFilterForm()['supervisor']))

    def test_only_management_can_edit_supervisor(self):
        for user in [self.worker, self.supervisor]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('users-manage')).status_code, 404)
            response = self.client.post(reverse('user-edit', args=[self.worker.pk]), {
                'first_name':'Changed', 'is_supervisor':'on',
            })
            self.assertEqual(response.status_code, 404)
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.is_supervisor)
        self.assertEqual(self.worker.first_name, 'Roberto')
        self.client.force_login(self.boss)
        response = self.client.post(reverse('user-edit', args=[self.worker.pk]), {
            'first_name':'Roberto', 'last_name':'Pérez', 'email':'roberto@example.com',
            'role':'supervisor', 'area': self.area.pk, 'is_superuser':'on', 'is_staff':'on', 'password':'tampered',
        })
        self.assertRedirects(response, reverse('users-manage'))
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.is_supervisor)
        self.assertFalse(self.worker.is_superuser)
        self.assertFalse(self.worker.is_staff)
        self.assertFalse(self.worker.check_password('tampered'))

    def test_management_can_remove_supervision_but_not_edit_management(self):
        self.client.force_login(self.boss)
        self.client.post(reverse('user-edit', args=[self.supervisor.pk]), {'first_name':'Laura','last_name':'Soto','email':'', 'role':'base', 'area': self.area.pk})
        self.supervisor.refresh_from_db()
        self.assertFalse(self.supervisor.is_supervisor)
        self.assertEqual(self.client.post(reverse('user-edit', args=[self.boss.pk]), {}).status_code, 404)

    def test_custom_404_and_disabled_admin_even_in_debug(self):
        for debug in [True, False]:
            with override_settings(DEBUG=debug):
                for path in ['/admin/', '/admin/login/', '/admin/accounts/user/', '/does-not-exist/', '/tareas/999999/']:
                    self.client.force_login(self.boss)
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 404)
                    self.assertContains(response, 'Página no encontrada', status_code=404)
                    self.assertNotContains(response, 'URLconf', status_code=404)
                    self.assertNotContains(response, 'tried these URL patterns', status_code=404)

    def test_management_requires_login_and_csrf(self):
        from django.test import Client
        self.assertEqual(self.client.get(reverse('users-manage')).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.boss)
        self.assertEqual(client.post(reverse('user-edit', args=[self.worker.pk]), {}).status_code, 403)

    def test_brand_in_login(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'brand/logo.png')
        self.assertContains(response, 'rel="icon"')


@override_settings(SECURE_SSL_REDIRECT=False)
class DeletionTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_superuser(username='delete-boss', password='Management-password-91!')
        self.worker = User.objects.create_user(username='delete-worker', password='Worker-password-91!')
        self.client.force_login(self.boss)

    def test_business_days_skip_weekend(self):
        from datetime import datetime
        from django.utils import timezone
        from .deletion import after_business_days
        friday = timezone.make_aware(datetime(2026, 10, 2, 12, 30))
        result = after_business_days(friday)
        self.assertEqual(result.date().isoformat(), '2026-10-09')
        self.assertEqual(result.hour, 12)
        saturday = friday + __import__('datetime').timedelta(days=1)
        self.assertEqual(after_business_days(saturday).date().isoformat(), '2026-10-09')

    def test_password_required_and_cancellation(self):
        self.client.post(reverse('user-delete', args=[self.worker.pk]), {'password':'wrong'})
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.is_active)
        self.assertIsNone(self.worker.deletion_due_at)
        self.client.post(reverse('user-delete', args=[self.worker.pk]), {'password':'Management-password-91!'})
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.is_active)
        self.assertIsNotNone(self.worker.deletion_due_at)
        self.client.post(reverse('user-delete-cancel', args=[self.worker.pk]), {'password':'Management-password-91!'})
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.is_active)
        self.assertIsNone(self.worker.deletion_due_at)

    def test_cannot_delete_management_or_as_base_user(self):
        self.assertEqual(self.client.post(reverse('user-delete', args=[self.boss.pk]), {'password':'Management-password-91!'}).status_code, 404)
        self.client.force_login(self.worker)
        self.assertEqual(self.client.post(reverse('user-delete', args=[self.worker.pk]), {}).status_code, 404)

    def test_expiration_preserves_tasks_and_prevents_cancellation(self):
        from django.utils import timezone
        from datetime import timedelta
        from tasks.models import Task
        from .deletion import schedule_deletion, finalize_due_deletions, cancel_deletion
        from django.core.exceptions import ValidationError
        task = Task.objects.create(title='Conservar', created_by=self.worker, deadline=timezone.localdate())
        task.assignees.add(self.worker)
        schedule_deletion(actor=self.boss, target_id=self.worker.pk)
        User.objects.filter(pk=self.worker.pk).update(deletion_due_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(finalize_due_deletions(), 1)
        self.worker.refresh_from_db()
        self.assertIsNotNone(self.worker.deleted_at)
        self.assertEqual(task.assignees.get(), self.worker)
        self.assertNotContains(self.client.get(reverse('users-manage')), 'delete-worker')
        with self.assertRaises(ValidationError):
            cancel_deletion(actor=self.boss, target_id=self.worker.pk)

    def test_inactive_user_stays_inactive_after_cancellation(self):
        from .deletion import schedule_deletion, cancel_deletion
        self.worker.is_active=False
        self.worker.save()
        schedule_deletion(actor=self.boss, target_id=self.worker.pk)
        cancel_deletion(actor=self.boss, target_id=self.worker.pk)
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.is_active)

