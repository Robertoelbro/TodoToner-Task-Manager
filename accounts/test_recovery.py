import re
from datetime import timedelta
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import User, RecoveryRequest


@override_settings(SECURE_SSL_REDIRECT=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', 'ana@example.com', 'Old-pass-9417!')

    def request_code(self):
        self.client.post(reverse('recover-password'), {'email': self.user.email})
        return re.search(r'\b\d{6}\b', mail.outbox[-1].body).group()

    def test_full_flow_and_single_use(self):
        code = self.request_code()
        self.assertNotEqual(RecoveryRequest.objects.get().code_hash, code)
        self.assertRedirects(self.client.get(reverse('recovery-password')), reverse('recover-password'))
        self.assertRedirects(self.client.post(reverse('recovery-code'), {'code': code}), reverse('recovery-password'))
        self.assertEqual(self.client.post(reverse('recovery-password'), {'new_password1': '123', 'new_password2': '123'}).status_code, 200)
        self.assertRedirects(self.client.post(reverse('recovery-password'), {
            'new_password1': 'New-pass-6824!', 'new_password2': 'New-pass-6824!'}), reverse('login'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-pass-6824!'))
        self.assertTrue(RecoveryRequest.objects.get().consumed)
        self.assertRedirects(self.client.get(reverse('recovery-password')), reverse('recover-password'))

    def test_attempts_expiry_and_session_binding(self):
        from django.test import Client
        code = self.request_code()
        self.assertContains(Client().post(reverse('recovery-code'), {'code': code}), 'Código inválido')
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.client.post(reverse('recovery-code'), {'code': wrong})
        self.assertContains(self.client.post(reverse('recovery-code'), {'code': code}), 'Código inválido')
        RecoveryRequest.objects.update(attempts=0, expires_at=timezone.now()-timedelta(seconds=1))
        self.assertContains(self.client.post(reverse('recovery-code'), {'code': code}), 'Código inválido')

    def test_unknown_inactive_and_duplicate_emails_not_recovered(self):
        from django.test import Client
        for email in ('missing@example.com', 'inactive@example.com', 'duplicate@example.com'):
            if email.startswith('inactive'):
                User.objects.create_user('inactive', email, 'password', is_active=False)
            if email.startswith('duplicate'):
                User.objects.create_user('dup1', email, 'password')
                User.objects.create_user('dup2', email, 'password')
            response = Client().post(reverse('recover-password'), {'email': email})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_username_recovery_and_throttling_across_sessions(self):
        from django.test import Client
        self.client.post(reverse('recover-username'), {'email': self.user.email})
        self.assertIn('ana', mail.outbox[0].body)
        Client().post(reverse('recover-username'), {'email': self.user.email.upper()})
        self.assertEqual(len(mail.outbox), 1)

    def test_email_change_invalidates_code_and_duplicate_profile_email_rejected(self):
        code = self.request_code()
        self.user.email = 'changed@example.com'
        self.user.save()
        self.assertContains(self.client.post(reverse('recovery-code'), {'code': code}), 'Código inválido')
        other = User.objects.create_user('other', 'other@example.com', 'Old-pass-9417!')
        self.client.force_login(self.user)
        response = self.client.post(reverse('profile'), {'first_name': 'Ana', 'last_name': '',
            'email': other.email.upper(), 'current_password': 'Old-pass-9417!'})
        self.assertContains(response, 'Este correo ya está asociado')

    def test_delivery_failure_does_not_crash_or_leave_usable_code(self):
        from unittest.mock import patch
        with patch('accounts.recovery.send_mail', side_effect=OSError('SMTP unavailable')):
            with self.assertLogs('accounts.recovery', level='ERROR'):
                response = self.client.post(reverse('recover-password'), {'email': self.user.email})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(RecoveryRequest.objects.get().consumed)

    def test_profile_does_not_escalate_and_email_needs_password(self):
        self.client.force_login(self.user)
        data = {'first_name': 'Ana', 'last_name': 'Pérez', 'email': 'new@example.com', 'is_superuser': 'on'}
        self.client.post(reverse('profile'), data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'ana@example.com')
        data['current_password'] = 'Old-pass-9417!'
        self.assertRedirects(self.client.post(reverse('profile'), data), reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new@example.com')
        self.assertFalse(self.user.is_superuser)

    def test_attendance_permission_and_demo_label(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('attendance')).status_code, 404)
        self.user.is_supervisor = True
        self.user.save()
        self.assertContains(self.client.get(reverse('attendance')), 'Datos ficticios')
