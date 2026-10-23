from django.test import TestCase, override_settings
from django.urls import reverse
from accounts.models import User
from tasks.models import Zone

@override_settings(SECURE_SSL_REDIRECT=False)
class CredentialDeliveryTests(TestCase):
    def setUp(self):
        self.manager=User.objects.create_superuser('manager',password='Manager-94-pass!')
        self.area=Zone.objects.get(code='ventas')
        self.client.force_login(self.manager)
        response=self.client.post(reverse('user-create'),{'first_name':'Juan','last_name':'Perez','area':self.area.pk})
        self.worker=response.context['created_user']
        self.password=response.context['temporary_password']

    def test_management_can_revisit_same_credentials_until_completion(self):
        page=self.client.get(reverse('user-edit',args=[self.worker.pk]))
        self.assertContains(page,self.password)
        self.assertContains(page,self.worker.username)
        self.assertNotContains(page,'name="role"')
        self.assertIn('no-store',page['Cache-Control'])
        self.worker.refresh_from_db()
        self.assertNotEqual(self.worker.onboarding_nonce,self.password)
        self.assertNotIn(self.password,self.worker.password)
        self.client.logout()
        self.client.login(username=self.worker.username,password=self.password)
        response=self.client.post(reverse('complete-profile'),{'email':'juan@example.com','new_password1':'Changed-85745!','new_password2':'Changed-85745!'})
        self.assertEqual(response.status_code,302)
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.onboarding_nonce,'')
        self.assertIsNone(self.worker.temporary_password)
        self.client.force_login(self.manager)
        self.assertNotContains(self.client.get(reverse('user-edit',args=[self.worker.pk])),self.password)

    def test_pending_account_cannot_be_edited_or_exposed_by_another_worker(self):
        self.client.post(reverse('user-edit',args=[self.worker.pk]),{'role':'management','area':self.area.pk})
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.is_superuser)
        other=User.objects.create_user('other')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('user-edit',args=[self.worker.pk])).status_code,404)

    def test_role_edit_cannot_change_identity_or_password(self):
        self.worker.must_complete_profile=False
        self.worker.onboarding_nonce=''
        self.worker.save()
        response=self.client.post(reverse('user-edit',args=[self.worker.pk]),{'role':'supervisor','area':self.area.pk,'first_name':'Injected','email':'injected@example.com','password':'injected'})
        self.assertEqual(response.status_code,302)
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.is_supervisor)
        self.assertEqual(self.worker.first_name,'Juan')
        self.assertEqual(self.worker.email,'')
        self.assertTrue(self.worker.check_password(self.password))

    def test_legacy_pending_requires_explicit_password_renewal(self):
        self.worker.onboarding_nonce=''
        self.worker.save()
        response=self.client.get(reverse('user-edit',args=[self.worker.pk]))
        self.assertIsNone(response.context['temporary_password'])
        self.assertTrue(self.worker.check_password(self.password))
        self.client.post(reverse('user-edit',args=[self.worker.pk]),{'action':'renew-temporary'})
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password(self.worker.temporary_password))
        self.assertFalse(self.worker.check_password(self.password))

    def test_deactivation_clears_delivery_secret(self):
        from accounts.deletion import schedule_deletion
        schedule_deletion(actor=self.manager,target_id=self.worker.pk)
        self.worker.refresh_from_db()
        self.assertIsNone(self.worker.temporary_password)
        self.assertEqual(self.worker.onboarding_nonce,'')
