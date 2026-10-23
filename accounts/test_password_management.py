from django.test import TestCase, Client, override_settings
from django.urls import reverse
from accounts.models import User
from tasks.models import Zone

@override_settings(SECURE_SSL_REDIRECT=False)
class PasswordManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager=User.objects.create_superuser('manager',password='Manager-94-pass!')
        cls.worker=User.objects.create_user('worker','worker@example.com','Worker-94-pass!',area=Zone.objects.get(code='ventas'))
        cls.supervisor=User.objects.create_user('sup',password='Supervisor-94-pass!',is_supervisor=True)

    def reset(self):
        self.client.force_login(self.manager)
        return self.client.post(reverse('user-password-reset',args=[self.worker.pk]),{'password':'Manager-94-pass!'})

    def test_reset_generates_new_password_each_time_and_invalidates_old_sessions(self):
        old_session=Client()
        old_session.login(username='worker',password='Worker-94-pass!')
        self.assertEqual(self.reset().status_code,302)
        self.worker.refresh_from_db()
        first=self.worker.temporary_password
        self.assertTrue(self.worker.check_password(first))
        self.assertFalse(self.worker.check_password('Worker-94-pass!'))
        self.assertRedirects(old_session.get(reverse('profile')),reverse('login')+'?next='+reverse('profile'))
        self.assertEqual(self.reset().status_code,302)
        self.worker.refresh_from_db()
        second=self.worker.temporary_password
        self.assertNotEqual(first,second)
        self.assertFalse(self.worker.check_password(first))
        self.assertTrue(self.worker.must_change_password)

    def test_only_management_with_correct_confirmation_can_reset_active_workers(self):
        url=reverse('user-password-reset',args=[self.worker.pk])
        for actor in (self.worker,self.supervisor):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(url).status_code,404)
            self.assertEqual(self.client.post(url,{'password':'Manager-94-pass!'}).status_code,404)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(url,{'password':'wrong'}).status_code,200)
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password('Worker-94-pass!'))
        self.assertEqual(self.client.post(reverse('user-password-reset',args=[self.manager.pk]),{'password':'Manager-94-pass!'}).status_code,404)
        self.worker.is_active=False
        self.worker.save()
        self.assertEqual(self.client.post(url,{'password':'Manager-94-pass!'}).status_code,404)

    def test_temporary_login_forces_password_change_without_recollecting_email(self):
        self.reset()
        self.worker.refresh_from_db()
        temp=self.worker.temporary_password
        self.client.logout()
        self.assertTrue(self.client.login(username='worker',password=temp))
        for route in ('task-list','gantt','profile','task-create'):
            self.assertRedirects(self.client.get(reverse(route)),reverse('password-change'))
        self.assertEqual(self.client.post(reverse('password-change'),{'new_password1':temp,'new_password2':temp}).status_code,200)
        data={'new_password1':'New-personal-974!','new_password2':'New-personal-974!'}
        self.assertRedirects(self.client.post(reverse('password-change'),data),reverse('task-list'))
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.must_change_password)
        self.assertEqual(self.worker.email,'worker@example.com')
        self.assertEqual(self.worker.onboarding_nonce,'')
        self.assertIsNone(self.worker.temporary_password)
        self.assertTrue(self.worker.check_password(data['new_password1']))
        self.assertIn('_auth_user_id',self.client.session)

    def test_authenticated_change_requires_current_password_and_preserves_session(self):
        self.client.login(username='worker',password='Worker-94-pass!')
        url=reverse('password-change')
        data={'old_password':'wrong','new_password1':'User-personal-984!','new_password2':'User-personal-984!','is_superuser':'on'}
        self.assertEqual(self.client.post(url,data).status_code,200)
        data['old_password']='Worker-94-pass!'
        self.assertRedirects(self.client.post(url,data),reverse('profile'))
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password('User-personal-984!'))
        self.assertFalse(self.worker.is_superuser)
        self.assertIn('_auth_user_id',self.client.session)

    def test_pending_first_login_still_requires_profile_completion_after_reset(self):
        self.worker.must_complete_profile=True
        self.worker.email=''
        self.worker.save()
        self.reset()
        self.worker.refresh_from_db()
        self.client.logout()
        self.client.login(username='worker',password=self.worker.temporary_password)
        self.assertRedirects(self.client.get(reverse('password-change')),reverse('complete-profile'))
        data={'email':'new@example.com','new_password1':'New-worker-974!','new_password2':'New-worker-974!'}
        self.assertRedirects(self.client.post(reverse('complete-profile'),data),reverse('task-list'))
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.must_change_password)
        self.assertFalse(self.worker.must_complete_profile)

    def test_reset_requires_csrf_and_plain_get_does_not_change_credentials(self):
        csrf_client=Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.manager)
        url=reverse('user-password-reset',args=[self.worker.pk])
        self.assertEqual(csrf_client.post(url,{'password':'Manager-94-pass!'}).status_code,403)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(url).status_code,200)
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password('Worker-94-pass!'))
