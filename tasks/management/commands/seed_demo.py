"""Reemplaza los datos de la aplicación por una demostración reproducible."""
import gzip
import json
import os
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tasks.models import AssignmentChange, MonthlyGoal, Task, TaskChange, Zone


class Command(BaseCommand):
    help = 'Respalda y reemplaza datos por 10 colaboradores, gerencia, tareas y metas de demostración.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true')
        parser.add_argument('--confirm-reset')
        parser.add_argument('--backup', required=True, help='Ruta nueva para respaldo JSON comprimido.')
        parser.add_argument('--seed', type=int, default=27102026)

    def handle(self, *args, **options):
        if not options['reset'] or options['confirm_reset'] != 'REEMPLAZAR_DATOS_DEMO':
            raise CommandError('Requiere --reset --confirm-reset REEMPLAZAR_DATOS_DEMO. Borra usuarios, tareas, metas y sesiones actuales.')
        password = os.environ.get('DEMO_PASSWORD', 'contraseña')
        validate_password(password)
        backup = Path(options['backup']).resolve()
        if backup.exists():
            raise CommandError('El respaldo ya existe. Usa una ruta nueva.')
        backup.parent.mkdir(parents=True, exist_ok=True)
        rng = random.Random(options['seed'])
        User = get_user_model()
        today = timezone.localdate()
        roster = [('ventas', 'Ventas', 'Roberto', 'Pérez', 'Camila', 'Soto'),
                  ('postventas', 'Postventas', 'Daniela', 'Rojas', 'Felipe', 'Díaz'),
                  ('storage', 'Storage', 'Martín', 'Silva', 'Antonia', 'Vega'),
                  ('administracion', 'Administración', 'Valentina', 'Torres', 'Javier', 'Muñoz'),
                  ('bodega', 'Bodega', 'Nicolás', 'Castro', 'Sofía', 'Morales')]
        # El respaldo se completa antes de borrar. La transacción revierte todo si falla la carga.
        with transaction.atomic():
            models = [Zone, User, Task, AssignmentChange, TaskChange, MonthlyGoal, Session, LogEntry]
            snapshot = []
            for model in models:
                snapshot.extend(json.loads(serializers.serialize('json', model.objects.all())))
            with backup.open('xb') as raw:
                if os.name != 'nt':
                    os.chmod(backup, 0o600)
                with gzip.GzipFile(fileobj=raw, mode='wb') as compressed:
                    compressed.write(json.dumps(snapshot, ensure_ascii=False).encode('utf-8'))
            with gzip.open(backup, 'rt', encoding='utf-8') as source:
                assert len(json.load(source)) == len(snapshot)
            Task.objects.all().delete()
            MonthlyGoal.objects.all().delete()
            LogEntry.objects.all().delete()
            Session.objects.all().delete()
            User.objects.update(deletion_requested_by=None)
            User.objects.all().delete()
            Zone.objects.all().delete()
            zones = [Zone.objects.create(code=row[0], name=row[1]) for row in roster]
            manager = User.objects.create_superuser(username='agerente', password=password,
                first_name='Andrea', last_name='Gerente', email='agerente@example.invalid', area=zones[3])
            users, supervisors = [], []
            for zone, row in zip(zones, roster):
                for supervisor, first, last in [(True, row[2], row[3]), (False, row[4], row[5])]:
                    user = User.objects.create_user(username=f'{"supervisor" if supervisor else "usuario"}_{zone.code}',
                        password=password, first_name=first, last_name=last,
                        email=f'{"supervisor" if supervisor else "usuario"}_{zone.code}@example.invalid',
                        area=zone, is_supervisor=supervisor,
                        must_complete_profile=False, must_change_password=False)
                    users.append(user)
                    if supervisor:
                        supervisors.append(user)

            def create_task(title, start, end, status, zone, parent=None):
                start_at = timezone.make_aware(datetime.combine(start, time(9)))
                end_at = timezone.make_aware(datetime.combine(end, time(18)))
                task = Task.objects.create(title=title,
                    description='Datos ficticios para probar seguimiento, visibilidad y planificación.',
                    start_date=start_at.date(), deadline=end_at.date(), start_time=start_at.time(),
                    deadline_time=end_at.time(), status=status, priority=rng.choice(Task.Priority.values),
                    supervisor=supervisors[zones.index(zone)], created_by=rng.choice([manager, *supervisors]), parent=parent)
                task.zones.set(rng.sample(zones, rng.randint(1, 2)) + [zone])
                own = [u for u in users if u.area_id == zone.pk]
                responsible = rng.sample(own, rng.randint(1, 2))
                if rng.random() < .4:
                    responsible.append(rng.choice(users))
                task.assignees.set(responsible)
                task.spectators.set(rng.sample(users, rng.randint(0, 4)))
                task.spectator_areas.set(rng.sample(zones, rng.randint(0, 2)))
                Task.objects.filter(pk=task.pk).update(created_at=min(start_at, timezone.now()))
                event = TaskChange.objects.create(task=task, actor=task.created_by,
                    summary='Tarea de demostración creada', changes={})
                TaskChange.objects.filter(pk=event.pk).update(created_at=min(start_at, timezone.now()))
                if status != Task.Status.PENDING:
                    TaskChange.objects.create(task=task, actor=task.supervisor, summary='Estado actualizado',
                        changes={'Estado': {'before': 'Pendiente', 'after': task.get_status_display()}})
                return task

            titles = ['Preparar cotizaciones', 'Revisar solicitudes de garantía', 'Ordenar ubicaciones',
                      'Conciliar documentos', 'Inventariar existencias', 'Confirmar pedidos',
                      'Contactar clientes', 'Revisar despachos', 'Actualizar indicadores', 'Verificar recepción',
                      'Planificar campaña', 'Resolver devoluciones', 'Auditar reservas',
                      'Preparar cierre mensual', 'Etiquetar productos', 'Seguimiento comercial',
                      'Revisar casos pendientes', 'Optimizar almacenamiento', 'Revisar facturación', 'Preparar entregas']
            for index, title in enumerate(titles):
                zone = zones[index % 5]
                # Vencidas, activas, finalizadas y futuras; intervalos también cruzan meses.
                offset, length = [(-8, 3), (-3, 6), (-7, 5), (2, 7)][index % 4]
                status = Task.Status.values[index % 4]
                task = create_task(title, today + timedelta(days=offset), today + timedelta(days=offset + length), status, zone)
                if index % 2 == 0:
                    create_task(f'Validar avance: {title.lower()}', task.start_date, task.deadline,
                                rng.choice(Task.Status.values), zone, parent=task)
            for advance in range(3):
                absolute_month = today.year * 12 + today.month - 1 + advance
                month = date(absolute_month // 12, absolute_month % 12 + 1, 1)
                for zone in [*zones, None]:
                    goal = MonthlyGoal.objects.create(title=f'Meta {zone.name if zone else "general"}: mejora mensual',
                        description='Completar el plan mensual y revisar los indicadores del equipo.',
                        month=month, created_by=manager)
                    goal.zones.set([zone] if zone else zones)
            assert User.objects.count() == 11
            assert Task.objects.filter(parent=None).count() == 20
            assert Task.objects.exclude(parent=None).count() == 10
            assert MonthlyGoal.objects.count() == 18
            assert all(user.check_password(password) for user in User.objects.all())
        self.stdout.write(self.style.SUCCESS('Demostración creada: 11 cuentas (agerente + 10 colaboradores), 20 tareas, 10 subtareas, 18 metas.'))
        self.stdout.write(f'Respaldo previo: {backup}')
        for user in User.objects.select_related('area').order_by('pk'):
            self.stdout.write(f'{user.username} | {user.role_label} | {user.area}')
