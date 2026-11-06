from datetime import timedelta

from django.contrib.auth import authenticate
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tasks.models import Zone
from .forms import ManagedUserForm
from .models import User


@override_settings(SECURE_SSL_REDIRECT=False)
class EmailLoginTests(TestCase):
    def setUp(self):
        self.area = Zone.objects.get(code='ventas')
        self.worker = User.objects.create_user(
            username='robe.perez', email='roberto@example.com', password='worker-123', area=self.area)
        self.boss = User.objects.create_superuser(username='boss', password='boss-123')

    def enable_email(self):
        self.worker.allow_email_login = True
        self.worker.save(update_fields=['allow_email_login'])

    def test_username_remains_available_and_email_is_opt_in(self):
        self.assertFalse(self.worker.allow_email_login)
        self.assertEqual(authenticate(username='robe.perez', password='worker-123'), self.worker)
        self.assertIsNone(authenticate(username='roberto@example.com', password='worker-123'))
        self.enable_email()
        self.assertEqual(authenticate(username='robe.perez', password='worker-123'), self.worker)
        self.assertEqual(authenticate(username='ROBERTO@EXAMPLE.COM', password='worker-123'), self.worker)
        self.assertIsNone(authenticate(username='roberto@example.com', password='wrong'))

    def test_login_form_accepts_email_with_spaces_and_case(self):
        self.enable_email()
        response = self.client.post(reverse('login'), {
            'username': '  ROBERTO@example.com  ', 'password': 'worker-123'})
        self.assertRedirects(response, reverse('task-list'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.worker.pk)

    def test_only_management_can_enable_the_option(self):
        self.client.force_login(self.boss)
        response = self.client.post(reverse('user-edit', args=[self.worker.pk]), {
            'area': self.area.pk, 'role': 'base', 'allow_email_login': 'on',
            'email': 'tampered@example.com', 'is_superuser': 'on'})
        self.assertRedirects(response, reverse('users-manage'))
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.allow_email_login)
        self.assertEqual(self.worker.email, 'roberto@example.com')
        self.assertFalse(self.worker.is_superuser)

    def test_worker_and_supervisor_cannot_change_the_option(self):
        supervisor = User.objects.create_user(username='supervisor', is_supervisor=True)
        for actor in [self.worker, supervisor]:
            self.client.force_login(actor)
            response = self.client.post(reverse('user-edit', args=[self.worker.pk]), {
                'area': self.area.pk, 'role': 'base', 'allow_email_login': 'on'})
            self.assertEqual(response.status_code, 404)
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.allow_email_login)

    def test_disabling_email_keeps_username_access(self):
        self.enable_email()
        self.client.force_login(self.boss)
        self.client.post(reverse('user-edit', args=[self.worker.pk]), {'area': self.area.pk, 'role': 'base'})
        self.assertIsNone(authenticate(username='roberto@example.com', password='worker-123'))
        self.assertEqual(authenticate(username='robe.perez', password='worker-123'), self.worker)

    def test_email_must_be_valid_and_unique_before_enabling(self):
        for email in ['', 'not-an-email']:
            self.worker.email = email
            form = ManagedUserForm({'area': self.area.pk, 'role': 'base', 'allow_email_login': 'on'}, instance=self.worker)
            self.assertFalse(form.is_valid())
            self.assertIn('allow_email_login', form.errors)
        self.worker.email = 'roberto@example.com'
        User.objects.create_user(username='legacy', email='ROBERTO@example.com')
        form = ManagedUserForm({'area': self.area.pk, 'role': 'base', 'allow_email_login': 'on'}, instance=self.worker)
        self.assertFalse(form.is_valid())
        self.assertIn('allow_email_login', form.errors)

    def test_legacy_ambiguous_email_does_not_choose_a_user(self):
        self.enable_email()
        User.objects.create_user(username='legacy', email='ROBERTO@example.com',
                                 password='legacy-123', allow_email_login=True)
        for password in ['worker-123', 'legacy-123']:
            self.assertIsNone(authenticate(username='roberto@example.com', password=password))
        self.assertEqual(authenticate(username='robe.perez', password='worker-123'), self.worker)

    def test_legacy_email_and_username_collision_does_not_choose_a_user(self):
        self.enable_email()
        User.objects.create_user(username='roberto@example.com', password='other-123')
        self.assertIsNone(authenticate(username='roberto@example.com', password='worker-123'))
        form = ManagedUserForm({'area': self.area.pk, 'role': 'base', 'allow_email_login': 'on'}, instance=self.worker)
        self.assertFalse(form.is_valid())

    def test_inactive_or_pending_deletion_stays_disabled_for_both_identifiers(self):
        self.enable_email()
        for state in [{'is_active': False}, {'is_active': True, 'deletion_due_at': timezone.now() + timedelta(days=5)}]:
            User.objects.filter(pk=self.worker.pk).update(**state)
            for identifier in ['robe.perez', 'ROBERTO@example.com']:
                self.assertIsNone(authenticate(username=identifier, password='worker-123'))
                response = self.client.post(reverse('login'), {'username': identifier, 'password': 'worker-123'})
                self.assertContains(response, 'Cuenta desactivada')
                self.assertNotIn('_auth_user_id', self.client.session)

    def test_email_login_preserves_forced_password_change(self):
        self.enable_email()
        self.worker.must_change_password = True
        self.worker.save(update_fields=['must_change_password'])
        response = self.client.post(reverse('login'), {'username': self.worker.email, 'password': 'worker-123'}, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse('password-change'))

    def test_profile_change_updates_login_email_without_enabling_it(self):
        self.client.force_login(self.worker)
        self.client.post(reverse('profile'), {'first_name': 'Roberto', 'last_name': 'Pérez',
            'email': 'new@example.com', 'current_password': 'worker-123', 'allow_email_login': 'on'})
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.allow_email_login)
        self.enable_email()
        self.assertEqual(authenticate(username='NEW@example.com', password='worker-123'), self.worker)
        self.assertIsNone(authenticate(username='roberto@example.com', password='worker-123'))

    def test_management_and_login_labels_explain_email_access(self):
        self.client.force_login(self.boss)
        self.assertContains(self.client.get(reverse('user-edit', args=[self.worker.pk])),
                            'Permitir ingresar con correo electrónico')
        self.client.logout()
        self.assertContains(self.client.get(reverse('login')), 'Nombre de usuario o correo electrónico')

    def test_management_can_enable_own_email_without_changing_privileges(self):
        self.boss.email = 'boss@example.com'
        self.boss.save(update_fields=['email'])
        self.client.force_login(self.boss)
        response = self.client.post(reverse('user-email-access', args=[self.boss.pk]), {
            'allow_email_login': 'on', 'role': 'base', 'is_superuser': '', 'email': 'tampered@example.com'})
        self.assertRedirects(response, reverse('users-manage'))
        self.boss.refresh_from_db()
        self.assertTrue(self.boss.allow_email_login)
        self.assertTrue(self.boss.is_superuser)
        self.assertTrue(self.boss.is_staff)
        self.assertEqual(self.boss.email, 'boss@example.com')
        self.assertEqual(authenticate(username='BOSS@example.com', password='boss-123'), self.boss)
        self.assertEqual(self.client.get(reverse('user-edit', args=[self.boss.pk])).status_code, 404)

    def test_management_can_configure_another_management_account(self):
        other = User.objects.create_superuser(username='other-boss', email='other@example.com', password='other-123')
        self.client.force_login(self.boss)
        self.assertContains(self.client.get(reverse('users-manage')), reverse('user-email-access', args=[other.pk]))
        self.client.post(reverse('user-email-access', args=[other.pk]), {'allow_email_login': 'on', 'is_supervisor': 'on'})
        other.refresh_from_db()
        self.assertTrue(other.allow_email_login)
        self.assertTrue(other.is_superuser)
        self.assertFalse(other.is_supervisor)

    def test_workers_cannot_use_the_separate_access_settings_view(self):
        self.client.force_login(self.worker)
        response = self.client.post(reverse('user-email-access', args=[self.worker.pk]), {'allow_email_login': 'on'})
        self.assertEqual(response.status_code, 404)
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.allow_email_login)

    def test_access_settings_rejects_accounts_pending_deletion(self):
        self.worker.deletion_due_at = timezone.now() + timedelta(days=5)
        self.worker.save(update_fields=['deletion_due_at'])
        self.client.force_login(self.boss)
        response = self.client.post(reverse('user-email-access', args=[self.worker.pk]), {'allow_email_login': 'on'})
        self.assertEqual(response.status_code, 404)
