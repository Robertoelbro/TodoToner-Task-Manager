from django.test import TestCase, override_settings
from django.urls import reverse
from .models import User


@override_settings(SECURE_SSL_REDIRECT=False)
class AccountTests(TestCase):
    def test_registration_ignores_privileges_and_hashes_password(self):
        response = self.client.post(reverse('register'), {
            'username': 'ana', 'first_name': 'Ana', 'last_name': 'Pérez',
            'email': 'ana@example.com', 'password1': 'Test-pass-9417!',
            'password2': 'Test-pass-9417!', 'is_supervisor': 'on',
            'is_staff': 'on', 'is_superuser': 'on',
        })
        self.assertRedirects(response, reverse('login'))
        user = User.objects.get(username='ana')
        self.assertFalse(user.is_supervisor)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('Test-pass-9417!'))

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

    def test_duplicate_username_and_invalid_password(self):
        User.objects.create_user(username='ana', password='Test-pass-9417!')
        response = self.client.post(reverse('register'), {
            'username': 'ana', 'first_name': 'Ana', 'last_name': 'Pérez',
            'email': 'ana@example.com', 'password1': '123', 'password2': '123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertIn('password2', response.context['form'].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_external_login_redirect_rejected(self):
        User.objects.create_user(username='ana', password='Test-pass-9417!')
        response = self.client.post(reverse('login'), {
            'username': 'ana', 'password': 'Test-pass-9417!', 'next': 'https://example.com/',
        })
        self.assertRedirects(response, reverse('task-list'))

