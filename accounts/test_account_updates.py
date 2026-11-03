from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.deletion import cancel_deletion, delete_now, schedule_deletion
from accounts.models import User
from tasks.models import Task, Zone


@override_settings(SECURE_SSL_REDIRECT=False)
class AccountUpdateTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser('manager', password='Management-password-91!')
        self.worker = User.objects.create_user('existing-login', first_name='Roberto', last_name='Orrego', password='Worker-password-91!')
        self.area = Zone.objects.get(code='ventas')
        self.client.force_login(self.manager)

    def create_worker(self, first_name='Roberto', last_name='Orrego'):
        response = self.client.post(reverse('user-create'), {'first_name': first_name, 'last_name': last_name, 'area': self.area.pk})
        self.assertEqual(response.status_code, 200)
        user = response.context['created_user']
        self.assertTrue(user.check_password(response.context['temporary_password']))
        return user

    def test_generated_usernames_are_readable_unique_and_do_not_rename_accounts(self):
        self.assertEqual(self.create_worker().username, 'robe.orrego')
        self.assertEqual(self.create_worker().username, 'robe.orrego2')
        self.assertEqual(self.create_worker().username, 'robe.orrego3')
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.username, 'existing-login')

    def test_names_with_accents_short_names_and_multiple_surnames(self):
        self.assertEqual(self.create_worker('María José', 'Pérez González').username, 'mari.perez-gonzalez')
        self.assertEqual(self.create_worker('Ana', 'Ríos').username, 'ana.rios')
        self.assertLessEqual(len(self.create_worker('Roberto', 'A' * 150).username), 150)

    def test_creation_retries_when_another_request_takes_the_same_username(self):
        original_save = User.save
        taken = False

        def save_with_competing_insert(user, *args, **kwargs):
            nonlocal taken
            if user.username == 'robe.orrego' and not taken:
                taken = True
                # Existing account represents an insert committed before this savepoint.
                from django.db import IntegrityError
                raise IntegrityError('username collision')
            return original_save(user, *args, **kwargs)

        User.objects.create_user('robe.orrego')
        # A stale availability check is followed by a uniqueness failure at INSERT.
        with patch('accounts.views.User.objects.filter') as filtered, patch.object(User, 'save', save_with_competing_insert):
            filtered.return_value.exists.side_effect = [False, True, False]
            self.assertEqual(self.create_worker().username, 'robe.orrego2')

    def test_immediate_deletion_requires_pending_account_and_password(self):
        url = reverse('user-delete-now', args=[self.worker.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        schedule_deletion(actor=self.manager, target_id=self.worker.pk)
        self.assertContains(self.client.get(reverse('users-manage')), 'Eliminar ahora')
        page = self.client.get(url)
        self.assertContains(page, 'ya no se podrá cancelar')
        self.worker.refresh_from_db()
        self.assertIsNone(self.worker.deleted_at)
        self.client.post(url, {'password': 'incorrect'})
        self.worker.refresh_from_db()
        self.assertIsNone(self.worker.deleted_at)
        task = Task.objects.create(title='Conservar historial', created_by=self.worker, deadline=timezone.localdate())
        task.assignees.add(self.worker)
        self.assertRedirects(self.client.post(url, {'password': 'Management-password-91!'}), reverse('users-manage'))
        self.worker.refresh_from_db()
        self.assertIsNotNone(self.worker.deleted_at)
        self.assertFalse(self.worker.is_active)
        self.assertEqual(task.assignees.get(), self.worker)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())
        self.assertNotContains(self.client.get(reverse('users-manage')), 'Roberto Orrego')
        with self.assertRaises(ValidationError):
            cancel_deletion(actor=self.manager, target_id=self.worker.pk)
        self.assertEqual(self.client.post(url, {'password': 'Management-password-91!'}).status_code, 404)
        self.client.logout()
        self.assertFalse(self.client.login(username=self.worker.username, password='Worker-password-91!'))

    def test_immediate_deletion_enforces_role_csrf_and_protected_accounts(self):
        schedule_deletion(actor=self.manager, target_id=self.worker.pk)
        url = reverse('user-delete-now', args=[self.worker.pk])
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        self.assertEqual(client.post(url, {'password': 'Management-password-91!'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('user-delete-now', args=[self.manager.pk]), {'password': 'Management-password-91!'}).status_code, 404)
        for supervisor in (False, True):
            outsider = User.objects.create_user(f'outsider-{supervisor}', is_supervisor=supervisor)
            self.client.force_login(outsider)
            self.assertEqual(self.client.post(url, {'password': 'Management-password-91!'}).status_code, 404)
        self.worker.refresh_from_db()
        self.assertIsNone(self.worker.deleted_at)

    def test_cancelled_schedule_cannot_be_completed_from_a_stale_page(self):
        schedule_deletion(actor=self.manager, target_id=self.worker.pk)
        cancel_deletion(actor=self.manager, target_id=self.worker.pk)
        with self.assertRaises(ValidationError):
            delete_now(actor=self.manager, target_id=self.worker.pk)
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.is_active)

    def test_avatar_is_part_of_the_profile_link(self):
        page = self.client.get(reverse('profile'))
        self.assertContains(page, 'class="profile-avatar"')
        self.assertContains(page, 'aria-label="Editar mi perfil:')
