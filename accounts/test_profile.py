from django.test import TestCase, override_settings
from django.urls import reverse
from .models import User

@override_settings(SECURE_SSL_REDIRECT=False)
class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana','ana@example.com','Old-pass-9417!')

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


    def test_duplicate_email_rejected(self):
        other=User.objects.create_user('other','other@example.com')
        self.client.force_login(self.user)
        response=self.client.post(reverse('profile'),{'first_name':'Ana','last_name':'','email':other.email.upper(),'current_password':'Old-pass-9417!'})
        self.assertContains(response,'Este correo ya está asociado')

    def test_retired_routes_and_navigation(self):
        self.user.is_supervisor=True
        self.user.save()
        self.client.force_login(self.user)
        for path in ('/asistencia/','/recuperar/usuario/','/recuperar/contrasena/','/recuperar/codigo/','/recuperar/nueva-contrasena/'):
            self.assertEqual(self.client.get(path).status_code,404)
            self.assertEqual(self.client.post(path,{}).status_code,404)
        response=self.client.get(reverse('dashboard'))
        self.assertNotContains(response,'pause-updates')
        self.assertNotContains(response,'href="/asistencia/"')
        from .attendance import demo_attendance
        self.assertTrue(all(type(person['present']) is bool and 'time' not in person for person in demo_attendance()))
