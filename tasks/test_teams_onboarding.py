from datetime import timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from tasks.models import Task, Zone
from tasks.views import visible_tasks
from tasks.forms import TaskForm

@override_settings(SECURE_SSL_REDIRECT=False)
class TeamSharingTests(TestCase):
    def setUp(self):
        self.sales = Zone.objects.get(code='ventas')
        self.storage = Zone.objects.get(code='bodega')
        self.worker = User.objects.create_user('worker', area=self.sales)
        self.other = User.objects.create_user('other', area=self.storage)
        self.sup = User.objects.create_user('supervisor', is_supervisor=True, area=self.sales)
        self.manager = User.objects.create_superuser('manager', password='Test-pass-9417!')
        self.task = Task.objects.create(title='Sales task', created_by=self.worker, deadline=timezone.localdate()+timedelta(days=1))
        self.task.assignees.add(self.worker)
        self.foreign = Task.objects.create(title='Storage task', created_by=self.other, deadline=timezone.localdate()+timedelta(days=1))
        self.foreign.assignees.add(self.other)

    def test_team_scope_and_no_area(self):
        self.assertIn(self.task, visible_tasks(self.sup))
        self.assertNotIn(self.foreign, visible_tasks(self.sup))
        self.sup.area = None
        self.sup.save()
        self.assertFalse(visible_tasks(self.sup).exists())
        self.task.supervisor = self.sup
        self.task.save()
        self.assertIn(self.task, visible_tasks(self.sup))
        self.assertEqual(visible_tasks(self.manager).count(), 2)

    def test_spectator_is_read_only_even_for_supervisor(self):
        self.foreign.spectators.add(self.sup)
        self.client.force_login(self.sup)
        self.assertEqual(self.client.get(reverse('task-detail',args=[self.foreign.pk])).status_code,200)
        for route in ('task-tracking','task-reassign','task-delete','task-audience','subtask-create'):
            self.assertEqual(self.client.post(reverse(route,args=[self.foreign.pk]),{}).status_code,403,route)

    def test_area_access_changes_with_membership_and_management_stays_private(self):
        self.foreign.spectator_areas.add(self.sales)
        self.assertIn(self.foreign, visible_tasks(self.worker))
        self.worker.area = None
        self.worker.save()
        self.assertNotIn(self.foreign, visible_tasks(self.worker))
        self.foreign.assignees.set([self.manager])
        self.foreign.spectators.add(self.worker)
        self.assertNotIn(self.foreign, visible_tasks(self.worker))

    def test_base_gantt_history_and_direct_urls_respect_access(self):
        self.client.force_login(self.worker)
        for route in ('gantt','task-history'):
            response=self.client.get(reverse(route))
            self.assertContains(response,self.task.title)
            self.assertNotContains(response,self.foreign.title)
        self.assertEqual(self.client.get(reverse('task-detail',args=[self.foreign.pk])).status_code,404)

    def test_share_and_audit(self):
        self.client.force_login(self.worker)
        response=self.client.post(reverse('task-audience',args=[self.task.pk]),{'spectators':[self.other.pk]})
        self.assertEqual(response.status_code,302)
        self.assertIn(self.task,visible_tasks(self.other))
        self.assertEqual(self.task.changes.get().actor,self.worker)

    def test_area_assignment_excludes_inactive(self):
        inactive=User.objects.create_user('inactive',area=self.sales,is_active=False)
        data={'title':'Grouped','start_date':timezone.localdate(),'deadline':timezone.localdate()+timedelta(days=1),'priority':'medium','zones':[self.sales.pk],'assignee_areas':[self.sales.pk]}
        form=TaskForm(data)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertSetEqual(set(form.cleaned_data['assignees']),{self.worker,self.sup})
        self.assertNotIn(inactive,form.cleaned_data['assignees'])

    def test_subtask_independent_visibility_and_parent_delete(self):
        self.client.force_login(self.worker)
        response=self.client.post(reverse('subtask-create',args=[self.task.pk]),{'title':'Child','start_date':timezone.localdate(),'deadline':timezone.localdate()+timedelta(days=1),'priority':'medium','zones':[self.sales.pk],'assignees':[self.other.pk],'parent':self.foreign.pk})
        self.assertEqual(response.status_code,302)
        child=Task.objects.get(title='Child')
        self.assertEqual(child.parent,self.task)
        self.client.force_login(self.other)
        page=self.client.get(reverse('task-detail',args=[child.pk]))
        self.assertEqual(page.status_code,200)
        self.assertIsNone(page.context['visible_parent'])
        self.assertNotIn(child,visible_tasks(self.sup))
        self.task.delete()
        child.refresh_from_db()
        self.assertIsNone(child.parent)

@override_settings(SECURE_SSL_REDIRECT=False)
class ManagedOnboardingTests(TestCase):
    def setUp(self):
        self.area=Zone.objects.get(code='ventas')
        self.manager=User.objects.create_superuser('boss',password='Test-pass-9417!')
        self.worker=User.objects.create_user('robin',first_name='Robin',password='Temporary-9417!',area=self.area,must_complete_profile=True)

    def test_only_management_creates_with_generated_password_and_no_injected_role(self):
        self.client.force_login(self.manager)
        result=self.client.post(reverse('user-create'),{'first_name':'Roberto','last_name':'Perez','area':self.area.pk,'is_superuser':'on','role':'management'})
        self.assertEqual(result.status_code,200)
        created=result.context['created_user']
        self.assertTrue(created.check_password(result.context['temporary_password']))
        self.assertTrue(created.must_complete_profile)
        self.assertFalse(created.is_superuser)
        self.assertIn('no-store',result['Cache-Control'])
        self.worker.must_complete_profile=False
        self.worker.save()
        self.client.force_login(self.worker)
        self.assertEqual(self.client.post(reverse('user-create'),{}).status_code,404)

    def test_first_login_requires_completion_and_new_password(self):
        self.client.login(username='robin',password='Temporary-9417!')
        for route in ('task-list','gantt','task-create','profile'):
            response=self.client.post(reverse(route),{})
            self.assertRedirects(response,reverse('complete-profile'))
        response=self.client.post(reverse('complete-profile'),{'email':'robin@example.com','new_password1':'Temporary-9417!','new_password2':'Temporary-9417!'})
        self.assertTrue(response.context['form'].errors)
        response=self.client.post(reverse('complete-profile'),{'email':'robin@example.com','new_password1':'Changed-85745!','new_password2':'Changed-85745!'})
        self.assertRedirects(response,reverse('task-list'))
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.must_complete_profile)
        self.assertEqual(self.worker.email,'robin@example.com')
        self.assertTrue(self.worker.check_password('Changed-85745!'))
        self.assertIn('_auth_user_id',self.client.session)

    def test_pending_deletion_cannot_sign_in(self):
        self.worker.is_active=False
        self.worker.deletion_due_at=timezone.now()+timedelta(days=5)
        self.worker.save()
        result=self.client.post(reverse('login'),{'username':'robin','password':'Temporary-9417!'})
        self.assertContains(result,'Cuenta desactivada')
        self.assertNotIn('_auth_user_id',self.client.session)

    def test_management_promotion_and_live_name_search(self):
        self.worker.must_complete_profile=False
        self.worker.save()
        self.client.force_login(self.manager)
        response=self.client.post(reverse('user-edit',args=[self.worker.pk]),{'first_name':'Robin','last_name':'Perez','email':'','area':self.area.pk,'role':'management'})
        self.assertEqual(response.status_code,302)
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.is_superuser)
        response=self.client.get(reverse('users-manage'),{'q':'rob'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response,'Robin')
        self.assertNotContains(response,'boss')
        self.assertEqual(response['X-Turno-Fragment'],'users')
