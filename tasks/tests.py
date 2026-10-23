from datetime import timedelta
from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from .models import AssignmentChange, Task, Zone, TaskChange
from .services import reassign_task


@override_settings(SECURE_SSL_REDIRECT=False)
class TaskPermissionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.base = User.objects.create_user(username='base', first_name='Ana', area=Zone.objects.get(code='bodega'))
        cls.worker = User.objects.create_user(username='worker', first_name='Juan', area=Zone.objects.get(code='bodega'))
        cls.other = User.objects.create_user(username='other', first_name='Otro', area=Zone.objects.get(code='bodega'))
        cls.supervisor = User.objects.create_user(username='supervisor', is_supervisor=True, area=Zone.objects.get(code='bodega'))
        cls.inactive = User.objects.create_user(username='inactive', is_active=False, area=Zone.objects.get(code='bodega'))
        cls.task = Task.objects.create(title='Inventario', created_by=cls.base,
                                      deadline=timezone.localdate() + timedelta(days=4))
        cls.task.assignees.add(cls.worker)
        cls.zone = Zone.objects.get(code='bodega')
        cls.task.zones.add(cls.zone)

    def setUp(self):
        self.client.force_login(self.base)

    def test_base_creates_task_with_multiple_assignees(self):
        response = self.client.post(reverse('task-create'), {
            'start_date': timezone.localdate().isoformat(), 'zones': [self.zone.pk], 'priority': 'medium', 'title': 'Contar cajas', 'description': 'Bodega',
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
                data = {'start_date': timezone.localdate().isoformat(), 'zones': [self.zone.pk], 'priority': 'medium', 'title': 'No crear', 'deadline': timezone.localdate().isoformat(),
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
        self.assertEqual(self.client.get(reverse('gantt')).status_code, 200)
        self.client.force_login(self.supervisor)
        response = self.client.get(reverse('gantt'))
        self.assertContains(response, 'Inventario')
        self.assertContains(response, 'Otro')
        self.assertContains(response, 'Gantt general')
        self.assertNotContains(response, 'id="personal-title"')
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
        with patch('tasks.models.timezone.now', return_value=self.task.ends_at - timedelta(seconds=1)):
            self.assertFalse(self.task.is_overdue)
        with patch('tasks.models.timezone.now', return_value=self.task.ends_at + timedelta(seconds=1)):
            self.assertTrue(self.task.is_overdue)



    def test_base_updates_only_status_with_audit(self):
        for user, status in [(self.base, 'in_progress'), (self.worker, 'completed')]:
            self.client.force_login(user)
            url = reverse('task-tracking', args=[self.task.pk])
            self.assertEqual(list(self.client.get(url).context['form'].fields), ['status'])
            self.assertEqual(self.client.post(url, {'status': status, 'priority': 'high',
                'assignees': [self.other.pk], 'supervisor': self.supervisor.pk, 'deadline': '2099-01-01'}).status_code, 302)
            self.assertEqual(TaskChange.objects.filter(task=self.task).latest('pk').actor, user)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.COMPLETED)
        self.assertEqual(self.task.priority, Task.Priority.MEDIUM)
        self.assertIsNone(self.task.supervisor)
        self.assertNotEqual(self.task.deadline.year, 2099)
        self.assertSetEqual(set(self.task.assignees.all()), {self.worker})

    def test_base_status_rejects_other_tasks_and_invalid_status(self):
        url = reverse('task-tracking', args=[self.task.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'status': 'completed'}).status_code, 404)
        self.client.force_login(self.worker)
        self.assertIn('status', self.client.post(url, {'status': 'invalid'}).context['form'].errors)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.PENDING)

    def test_supervisor_updates_tracking_only(self):
        self.client.force_login(self.supervisor)
        response = self.client.post(reverse('task-tracking', args=[self.task.pk]), {
            'priority': 'high', 'status': 'in_review', 'supervisor': self.supervisor.pk,
            'start_date': self.task.start_date.isoformat(), 'deadline': self.task.deadline.isoformat(), 'zones': [self.zone.pk],
            'title': 'Tampered', 'assignees': [self.other.pk],
        })
        self.assertRedirects(response, reverse('task-detail', args=[self.task.pk]))
        self.task.refresh_from_db()
        self.assertEqual(self.task.priority, 'high')
        self.assertEqual(self.task.status, 'in_review')
        self.assertEqual(self.task.supervisor, self.supervisor)
        self.assertEqual(self.task.title, 'Inventario')
        self.assertSetEqual(set(self.task.assignees.all()), {self.worker})

    def test_tracking_rejects_invalid_supervisor_and_choices(self):
        self.client.force_login(self.supervisor)
        for extra in [{'supervisor': self.base.pk}, {'status': 'invalid'}, {'priority': 'urgent'}]:
            data = {'priority': 'medium', 'status': 'pending', 'supervisor': self.supervisor.pk}
            data.update(extra)
            response = self.client.post(reverse('task-tracking', args=[self.task.pk]), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)

    def test_completed_task_not_counted_as_overdue(self):
        self.task.deadline = timezone.localdate() - timedelta(days=1)
        self.task.status = Task.Status.COMPLETED
        self.task.save()
        self.assertFalse(self.task.is_overdue)
        self.client.force_login(self.supervisor)
        self.assertEqual(self.client.get(reverse('gantt')).context['overdue_count'], 0)

    def test_management_can_supervise(self):
        self.other.is_superuser = True
        self.other.save()
        self.client.force_login(self.other)
        self.assertEqual(self.other.role_label, 'Gerencia')
        self.assertEqual(self.client.get(reverse('gantt')).status_code, 200)
        self.assertEqual(self.client.get(reverse('task-tracking', args=[self.task.pk])).status_code, 200)


@override_settings(SECURE_SSL_REDIRECT=False)
class HubTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.supervisor = User.objects.create_user(username='boss', is_supervisor=True, area=Zone.objects.get(code='bodega'))
        cls.ana = User.objects.create_user(username='ana', area=Zone.objects.get(code='bodega'))
        cls.juan = User.objects.create_user(username='juan', area=Zone.objects.get(code='bodega'))
        cls.bodega = Zone.objects.get(code='bodega')
        cls.postventas = Zone.objects.get(code='postventas')
        cls.today = timezone.localdate()
        cls.shared = Task.objects.create(title='Inventario cruzado', created_by=cls.ana,
            start_date=cls.today - timedelta(days=3), deadline=cls.today + timedelta(days=4), priority='high')
        cls.shared.assignees.add(cls.ana, cls.juan)
        cls.shared.zones.add(cls.bodega, cls.postventas)
        cls.single = Task.objects.create(title='Venta individual', created_by=cls.juan,
            start_date=cls.today, deadline=cls.today + timedelta(days=2), priority='low')
        cls.single.assignees.add(cls.ana)
        cls.single.zones.add(Zone.objects.get(code='ventas'))

    def setUp(self):
        self.client.force_login(self.supervisor)

    def test_home_routes_supervisor_to_hub(self):
        self.assertRedirects(self.client.get(reverse('task-list')), reverse('dashboard'))

    def test_general_deduplicates_and_zones_repeat_shared_task(self):
        response = self.client.get(reverse('gantt'))
        self.assertEqual(response.context['task_count'], 2)
        self.assertEqual(len(response.context['timeline']['rows']), 2)
        groups = {g['name']: g['rows'] for g in response.context['zone_groups']}
        self.assertEqual(groups['Bodega'][0]['task'], self.shared)
        self.assertEqual(groups['Postventas'][0]['task'], self.shared)
        hub = self.client.get(reverse('dashboard'))
        self.assertEqual(list(hub.context['personal_tasks']), [])

    def test_combined_worker_zone_priority_multiple_filters(self):
        response = self.client.get(reverse('gantt'), {
            'worker': self.ana.pk, 'zone': self.bodega.pk, 'priority': 'high', 'multiple': 'on',
        })
        self.assertEqual(response.context['task_count'], 1)
        self.assertEqual(response.context['timeline']['rows'][0]['task'], self.shared)
        # Count must use all assignees, not just the worker selected in the filter.
        self.assertEqual(response.context['worker_count'], 2)

    def test_month_overlap_and_inclusive_boundary(self):
        for day in [self.shared.start_date, self.today, self.shared.deadline]:
            response = self.client.get(reverse('gantt'), {'month':day.month, 'year':day.year})
            tasks = [row['task'] for row in response.context['timeline']['rows']]
            self.assertIn(self.shared, tasks)
            self.assertEqual(response.context['timeline']['start'].day,1)

    def test_bad_dates_and_missing_results(self):
        for data in [
            {'year': 'wrong'},
            {'month': '13', 'year': '2026'},
            {'zone': '99999'},
        ]:
            response = self.client.get(reverse('gantt'), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['filter_form'].errors)
            self.assertEqual(response.context['task_count'], 0)
        response = self.client.get(reverse('gantt'), {'priority': 'medium'})
        self.assertContains(response, 'No hay tareas para esta selección.')

    def test_personal_section_is_in_hub_only(self):
        self.shared.assignees.add(self.supervisor)
        response = self.client.get(reverse('dashboard'), {'priority': 'low'})
        self.assertIn(self.shared, response.context['personal_tasks'])
        self.assertContains(response, 'Últimos cambios en tareas')
        self.assertNotContains(response, 'id="gantt-filters"')

    def test_dates_and_zones_validated_at_creation(self):
        self.client.force_login(self.ana)
        data = {'title': 'Nuevo', 'priority': 'medium', 'start_date': self.today.isoformat(),
                'deadline': (self.today + timedelta(days=4)).isoformat(),
                'assignees': [self.ana.pk], 'zones': [self.bodega.pk, self.postventas.pk]}
        response = self.client.post(reverse('task-create'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Task.objects.get(title='Nuevo').zones.count(), 2)
        data['start_date'] = (self.today + timedelta(days=5)).isoformat()
        response = self.client.post(reverse('task-create'), data)
        self.assertIn('deadline', response.context['form'].errors)
        data['start_date'] = self.today.isoformat()
        data['zones'] = []
        response = self.client.post(reverse('task-create'), data)
        self.assertIn('zones', response.context['form'].errors)

    def test_long_range_has_bounded_columns(self):
        from .gantt import build_timeline
        timeline = build_timeline([], self.today, self.today + timedelta(days=3000))
        self.assertLessEqual(len(timeline['ticks']), 90)



    def test_supervisor_and_status_filters_and_fragment(self):
        self.shared.supervisor = self.supervisor
        self.shared.status = 'in_review'
        self.shared.save()
        response = self.client.get(reverse('gantt'), {'supervisor': self.supervisor.pk, 'status': 'in_review'},
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.context['task_count'], 1)
        self.assertContains(response, 'Inventario cruzado')
        self.assertNotContains(response, '<!doctype html>')
        self.assertEqual(response['X-Turno-Fragment'], 'gantt')
        response = self.client.get(reverse('gantt'), {'status': 'nonsense'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.context['filter_form'].errors)

    def test_base_can_get_own_gantt_fragment(self):
        self.client.force_login(self.ana)
        response = self.client.get(reverse('gantt'), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

    def test_tracking_logs_changes_and_ignores_noop(self):
        data = {'priority': 'low', 'status': 'in_review', 'supervisor': self.supervisor.pk,
                'start_date': self.shared.start_date.isoformat(), 'deadline': self.shared.deadline.isoformat(),
                'zones': [self.bodega.pk]}
        response = self.client.post(reverse('task-tracking', args=[self.shared.pk]), data)
        self.assertEqual(response.status_code, 302)
        event = TaskChange.objects.get(task=self.shared)
        self.assertEqual(event.actor, self.supervisor)
        self.assertEqual(event.changes['Prioridad'], {'before': 'Alta', 'after': 'Baja'})
        self.assertIn('Zonas', event.changes)
        self.client.post(reverse('task-tracking', args=[self.shared.pk]), data)
        self.assertEqual(TaskChange.objects.filter(task=self.shared).count(), 1)

    def test_recent_changes_respect_visibility(self):
        TaskChange.objects.create(task=self.shared, actor=self.supervisor, summary='Evento visible')
        outsider = User.objects.create_user(username='outsider', area=Zone.objects.get(code='bodega'))
        hidden = Task.objects.create(title='Privada', created_by=outsider, deadline=self.today)
        TaskChange.objects.create(task=hidden, actor=self.supervisor, summary='Evento privado')
        self.client.force_login(self.ana)
        response = self.client.get(reverse('task-list'))
        self.assertContains(response, 'Evento visible')
        self.assertNotContains(response, 'Evento privado')
        self.client.force_login(self.supervisor)
        self.assertNotContains(self.client.get(reverse('dashboard')), 'Evento privado')

    def test_reassignment_creates_feed_event(self):
        reassign_task(actor=self.supervisor, task_id=self.shared.pk, assignees=[self.ana])
        event = TaskChange.objects.get(task=self.shared)
        self.assertEqual(event.summary, 'Responsables actualizados')
        self.assertIn('Responsables', event.changes)

@override_settings(SECURE_SSL_REDIRECT=False)
class UrgencyTests(TestCase):
    def task_for_hours(self, hours):
        from datetime import datetime
        self.start = timezone.make_aware(datetime(2026, 10, 5, 9, 0))
        end = self.start + timedelta(hours=hours)
        return Task(title='Temporal', start_date=self.start.date(), start_time=self.start.time(),
                    deadline=end.date(), deadline_time=end.time())

    def test_nine_hour_task_warns_after_75_percent(self):
        task = self.task_for_hours(9)
        for hours, expected in [(0, 'green'), (6.74, 'green'), (6.75, 'yellow'),
                                (8.99, 'yellow'), (9, 'overdue')]:
            self.assertEqual(task.urgency_at(self.start + timedelta(hours=hours)), expected)

    def test_long_task_exact_thresholds(self):
        task = self.task_for_hours(96)
        end = task.ends_at
        for hours, expected in [(49, 'green'), (48, 'green'), (24.01, 'green'), (24, 'yellow'),
                                (23.99, 'yellow'), (0, 'overdue'), (-1, 'overdue')]:
            self.assertEqual(task.urgency_at(end - timedelta(hours=hours)), expected)

    def test_completed_and_not_started(self):
        task = self.task_for_hours(9)
        self.assertEqual(task.urgency_at(self.start - timedelta(hours=1)), 'green')
        task.status = Task.Status.COMPLETED
        self.assertEqual(task.urgency_at(self.start + timedelta(days=3)), 'completed')

    def test_twenty_four_hour_task_is_short(self):
        task = self.task_for_hours(24)
        self.assertEqual(task.urgency_at(self.start + timedelta(hours=8)), 'green')
        self.assertEqual(task.urgency_at(self.start + timedelta(hours=16)), 'green')
        self.assertEqual(task.urgency_at(self.start + timedelta(hours=18)), 'yellow')

    def test_alert_visibility_and_completed_exclusion(self):
        owner = User.objects.create_user(username='alert-owner', area=Zone.objects.get(code='bodega'))
        stranger = User.objects.create_user(username='stranger', area=Zone.objects.get(code='bodega'))
        boss = User.objects.create_user(username='alert-boss', is_supervisor=True, area=Zone.objects.get(code='bodega'))
        task = self.task_for_hours(9)
        task.created_by = owner
        task.save()
        task.assignees.add(owner)
        with patch('tasks.models.timezone.now', return_value=self.start + timedelta(hours=7)):
            self.client.force_login(owner)
            self.assertNotContains(self.client.get(reverse('task-alerts')), 'Temporal')
        with patch('tasks.models.timezone.now', return_value=self.start + timedelta(hours=9)):
            self.client.force_login(owner)
            self.assertContains(self.client.get(reverse('task-alerts')), 'Temporal')
            self.client.force_login(stranger)
            self.assertNotContains(self.client.get(reverse('task-alerts')), 'Temporal')
            self.client.force_login(boss)
            self.assertContains(self.client.get(reverse('task-alerts')), 'Temporal')
            task.status = Task.Status.COMPLETED
            task.save()
            self.assertNotContains(self.client.get(reverse('task-alerts')), 'Temporal')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('task-alerts')).status_code, 302)

    def test_form_accepts_hours_and_rejects_reverse_times(self):
        from .forms import TaskTrackingForm
        task = self.task_for_hours(9)
        user = User.objects.create_user(username='time-owner', area=Zone.objects.get(code='bodega'))
        task.created_by = user
        task.save()
        zone = Zone.objects.get(code='bodega')
        data = {'priority':'medium', 'status':'pending', 'start_date':'2026-10-05',
                'deadline':'2026-10-05', 'start_time':'09:00', 'deadline_time':'18:00', 'zones':[zone.pk]}
        form = TaskTrackingForm(data, instance=task)
        self.assertTrue(form.is_valid(), form.errors)
        data['deadline_time'] = '08:00'
        form = TaskTrackingForm(data, instance=task)
        self.assertFalse(form.is_valid())
        self.assertIn('deadline_time', form.errors)


@override_settings(SECURE_SSL_REDIRECT=False)
class TVTests(TestCase):
    def setUp(self):
        self.worker = User.objects.create_user(username='tv-worker', area=Zone.objects.get(code='bodega'))
        self.boss = User.objects.create_user(username='tv-supervisor', is_supervisor=True, area=Zone.objects.get(code='bodega'))
        for index in range(8):
            task = Task.objects.create(title=f'TV tarea {index}', created_by=self.worker,
                deadline=timezone.localdate()+timedelta(days=index+1))
            task.assignees.add(self.worker)
        Task.objects.create(title='No mostrar finalizada', created_by=self.worker,
            deadline=timezone.localdate(), status=Task.Status.COMPLETED)

    def test_only_supervisors_and_management(self):
        self.assertEqual(self.client.get(reverse('tv-dashboard')).status_code, 302)
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(reverse('tv-dashboard')).status_code, 403)
        self.worker.is_superuser = True
        self.worker.save()
        self.assertEqual(self.client.get(reverse('tv-dashboard')).status_code, 200)

    def test_tv_pagination_and_completed_exclusion(self):
        self.client.force_login(self.boss)
        response = self.client.get(reverse('tv-dashboard'))
        self.assertEqual(response.context['active_count'], 8)
        self.assertEqual(len(response.context['page']), 6)
        self.assertContains(response, 'Pantalla completa')
        self.assertNotContains(response, 'No mostrar finalizada')
        response = self.client.get(reverse('tv-dashboard'), {'page': 2}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(len(response.context['page']), 2)
        self.assertEqual(response['X-Turno-Fragment'], 'tv')
        self.assertNotContains(response, '<!doctype html>')
        self.assertEqual(self.client.get(reverse('tv-dashboard'), {'page': 'invalid'}).status_code, 200)

    def test_empty_screen(self):
        Task.objects.update(status=Task.Status.COMPLETED)
        self.client.force_login(self.boss)
        self.assertContains(self.client.get(reverse('tv-dashboard')), 'Sin tareas activas')


@override_settings(SECURE_SSL_REDIRECT=False)
class TaskHistoryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', area=Zone.objects.get(code='bodega'))
        self.worker = User.objects.create_user(username='worker', area=Zone.objects.get(code='bodega'))
        self.other = User.objects.create_user(username='other', area=Zone.objects.get(code='bodega'))
        self.supervisor = User.objects.create_user(username='supervisor', is_supervisor=True, area=Zone.objects.get(code='bodega'))
        self.manager = User.objects.create_user(username='manager', is_superuser=True, area=Zone.objects.get(code='bodega'))
        self.task = Task.objects.create(title='Historic task', created_by=self.owner,
            start_date=timezone.localdate()-timedelta(days=3),
            deadline=timezone.localdate()-timedelta(days=1))
        self.task.assignees.add(self.worker)
        self.client.force_login(self.owner)

    def test_hide_is_personal_and_preserves_task(self):
        url = reverse('task-hide', args=[self.task.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertNotIn(self.task, self.client.get(reverse('task-list')).context['tasks'])
        self.assertIn(self.task, self.client.get(reverse('task-history')).context['page'])
        self.task.refresh_from_db()
        self.assertIsNone(self.task.deleted_at)
        self.assertEqual(self.task.assignees.count(), 1)
        self.client.force_login(self.worker)
        self.assertIn(self.task, self.client.get(reverse('task-list')).context['tasks'])
        self.assertIn(self.task, self.client.get(reverse('task-history')).context['page'])

    def test_completed_automatically_in_history_and_can_hide(self):
        self.task.status = Task.Status.COMPLETED
        self.task.save()
        self.assertIn(self.task, self.client.get(reverse('task-history')).context['page'])
        self.assertIn(self.task, self.client.get(reverse('task-list')).context['tasks'])
        self.assertEqual(self.client.post(reverse('task-hide', args=[self.task.pk])).status_code, 302)

    def test_active_and_in_progress_cannot_hide(self):
        self.task.status = Task.Status.IN_PROGRESS
        self.task.save()
        self.assertEqual(self.client.post(reverse('task-hide', args=[self.task.pk])).status_code, 403)
        self.task.status = Task.Status.PENDING
        self.task.deadline = timezone.localdate()+timedelta(days=3)
        self.task.save()
        self.assertEqual(self.client.post(reverse('task-hide', args=[self.task.pk])).status_code, 403)
        self.assertFalse(self.task.hidden_by.exists())

    def test_base_cannot_delete_and_unrelated_cannot_see_or_hide(self):
        self.assertEqual(self.client.post(f'/tareas/{self.task.pk}/eliminar/', {'confirm':'yes'}).status_code,404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('task-hide', args=[self.task.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('task-detail', args=[self.task.pk])).status_code,404)
        self.assertNotIn(self.task,self.client.get(reverse('task-history')).context['page'])

    def test_no_role_can_delete_tasks(self):
        pk = self.task.pk
        TaskChange.objects.create(task=self.task, actor=self.owner, summary='Created')
        for user in (self.owner, self.worker, self.supervisor, self.manager):
            self.client.force_login(user)
            self.assertEqual(self.client.get(f'/tareas/{pk}/eliminar/').status_code,404)
            self.assertEqual(self.client.post(f'/tareas/{pk}/eliminar/',{'confirm':'yes'}).status_code,404)
            self.assertTrue(Task.objects.filter(pk=pk).exists())
            self.assertTrue(TaskChange.objects.filter(task_id=pk).exists())
            self.assertNotContains(self.client.get(reverse('task-detail',args=[pk])),'Eliminar tarea')

    def test_hide_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('task-hide',args=[self.task.pk])).status_code,403)

    def test_reopened_task_returns_to_hub(self):
        self.task.status = Task.Status.COMPLETED
        self.task.save()
        self.task.hidden_by.add(self.owner)
        self.client.force_login(self.supervisor)
        response = self.client.post(reverse('task-tracking',args=[self.task.pk]),{
            'status':'in_progress','priority':'medium',
            'start_date':timezone.localdate().isoformat(),
            'deadline':(timezone.localdate()+timedelta(days=3)).isoformat(),
            'zones':[Zone.objects.get(code='bodega').pk],
        })
        self.assertEqual(response.status_code,302)
        self.assertFalse(self.task.hidden_by.exists())
        self.client.force_login(self.owner)
        self.assertIn(self.task,self.client.get(reverse('task-list')).context['tasks'])

@override_settings(SECURE_SSL_REDIRECT=False)
class GanttMonthTests(TestCase):
    def test_month_range_and_overdue_filter(self):
        from datetime import date
        from calendar import monthrange
        supervisor = User.objects.create_user(username='month-supervisor', is_supervisor=True, area=Zone.objects.get(code='bodega'))
        today = timezone.localdate()
        first = today.replace(day=1)
        last = today.replace(day=monthrange(today.year, today.month)[1])
        active = Task.objects.create(title='Current', created_by=supervisor, start_date=first, deadline=last)
        old = Task.objects.create(title='Old', created_by=supervisor, start_date=date(2020,1,1), deadline=date(2020,1,5))
        self.client.force_login(supervisor)
        response = self.client.get(reverse('gantt'))
        self.assertEqual(response.context['timeline']['start'],first)
        self.assertEqual(response.context['timeline']['end'],last)
        self.assertEqual(response.context['task_count'],1)
        response = self.client.get(reverse('gantt'),{'overdue':'1','month':'1','year':'2020'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response['X-Turno-Fragment'],'gantt')
        self.assertEqual([row['task'] for row in response.context['timeline']['rows']],[old])
        self.assertContains(response,'name="overdue" value="1"')
        old.status = Task.Status.COMPLETED
        old.save()
        response = self.client.get(reverse('gantt'),{'overdue':'1','month':'1','year':'2020'})
        self.assertEqual(response.context['task_count'],0)


@override_settings(SECURE_SSL_REDIRECT=False)
class HistoryRevisionTests(TestCase):
    def test_all_states_newest_first_creation_month_and_permissions(self):
        user = User.objects.create_user(username='history-reader', area=Zone.objects.get(code='bodega'))
        other = User.objects.create_user(username='other-reader', area=Zone.objects.get(code='bodega'))
        tasks = [Task.objects.create(title=status, status=status, created_by=user,
            deadline=timezone.localdate()+timedelta(days=4)) for status in Task.Status.values]
        private = Task.objects.create(title='Private', created_by=other, deadline=timezone.localdate())
        self.client.force_login(user)
        page = self.client.get(reverse('task-history')).context['page']
        self.assertEqual(list(page), list(reversed(tasks)))
        self.assertNotIn(private,page)
        earlier = timezone.now()-timedelta(days=400)
        Task.objects.filter(pk=tasks[0].pk).update(created_at=earlier)
        local = timezone.localtime(earlier)
        result = self.client.get(reverse('task-history'),{'month':local.month,'year':local.year})
        self.assertEqual(list(result.context['page']),[tasks[0]])
        result = self.client.get(reverse('task-history'),{'month':'1'})
        self.assertTrue(result.context['filter_form'].errors)
        self.assertEqual(result.context['page'].paginator.count,0)
        self.assertContains(self.client.get(reverse('task-list')), 'hub-layout')

    def test_latest_actor_and_full_detail_log(self):
        user = User.objects.create_user(username='history-owner', area=Zone.objects.get(code='bodega'))
        supervisor = User.objects.create_user(username='history-supervisor',first_name='Roberto',is_supervisor=True, area=Zone.objects.get(code='bodega'))
        task = Task.objects.create(title='Audit task',created_by=user,deadline=timezone.localdate())
        TaskChange.objects.create(task=task,actor=user,summary='Tarea creada')
        event = TaskChange.objects.create(task=task,actor=supervisor,summary='Seguimiento actualizado',changes={'Estado':{'before':'Pendiente','after':'En proceso'}})
        self.client.force_login(user)
        response = self.client.get(reverse('task-detail',args=[task.pk]))
        self.assertContains(response,'Modificado por: Roberto')
        self.assertContains(response,'Historial de modificaciones')
        self.assertContains(response,'Pendiente → En proceso')
        self.assertEqual(response.context['task'].last_modification,event)
        self.client.force_login(User.objects.create_user(username='unrelated-reader', area=Zone.objects.get(code='bodega')))
        self.assertEqual(self.client.get(reverse('task-detail',args=[task.pk])).status_code,404)

@override_settings(SECURE_SSL_REDIRECT=False)
class MonthlyGoalTests(TestCase):
    def test_creation_permissions_and_visibility(self):
        from .models import MonthlyGoal
        base = User.objects.create_user(username='goal-base', area=Zone.objects.get(code='bodega'))
        supervisor = User.objects.create_user(username='goal-supervisor',is_supervisor=True, area=Zone.objects.get(code='bodega'))
        manager = User.objects.create_user(username='goal-manager',is_superuser=True, area=Zone.objects.get(code='bodega'))
        data = {'title':'Objetivo mensual de prueba','month':timezone.localdate().strftime('%Y-%m'),
                'zones':list(Zone.objects.values_list('pk',flat=True)[:2]),'created_by':base.pk}
        self.client.force_login(base)
        for method in ('get','post'):
            self.assertEqual(getattr(self.client,method)(reverse('monthly-goal-create'),data).status_code,403)
        self.assertEqual(MonthlyGoal.objects.count(),0)
        for creator in (supervisor,manager):
            self.client.force_login(creator)
            self.assertEqual(self.client.post(reverse('monthly-goal-create'),data).status_code,302)
            goal = MonthlyGoal.objects.latest('pk')
            self.assertEqual(goal.created_by,creator)
            self.assertEqual(goal.month.day,1)
            self.assertEqual(goal.zones.count(),2)
        for user,url in ((base,'task-list'),(supervisor,'dashboard'),(manager,'dashboard')):
            self.client.force_login(user)
            self.assertContains(self.client.get(reverse(url)),data['title'])
        MonthlyGoal.objects.update(month=timezone.localdate().replace(year=2020,month=1,day=1))
        self.assertNotContains(self.client.get(reverse('dashboard')),data['title'])

    def test_invalid_input_does_not_create_goal(self):
        from .models import MonthlyGoal
        self.client.force_login(User.objects.create_user(username='goal-validator',is_supervisor=True, area=Zone.objects.get(code='bodega')))
        for month,zones in [('2026-13',[Zone.objects.first().pk]),('2026-10',[]),('bad',[99999])]:
            response=self.client.post(reverse('monthly-goal-create'),{'title':'Invalid','month':month,'zones':zones})
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.context['form'].errors)
        self.assertEqual(MonthlyGoal.objects.count(),0)
