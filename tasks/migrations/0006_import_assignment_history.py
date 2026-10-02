from django.db import migrations


def import_assignments(apps, schema_editor):
    AssignmentChange = apps.get_model('tasks', 'AssignmentChange')
    TaskChange = apps.get_model('tasks', 'TaskChange')
    alias = schema_editor.connection.alias
    for old in AssignmentChange.objects.using(alias).all().iterator():
        previous = ', '.join(u['name'] for u in old.previous_assignees)
        current = ', '.join(u['name'] for u in old.new_assignees)
        event = TaskChange.objects.using(alias).create(
            task_id=old.task_id, actor_id=old.actor_id,
            summary='Responsables actualizados' if old.previous_assignees else 'Asignación inicial',
            changes={'Responsables': {'before': previous or 'Sin asignar', 'after': current}},
        )
        TaskChange.objects.using(alias).filter(pk=event.pk).update(created_at=old.created_at)


class Migration(migrations.Migration):
    dependencies = [('tasks', '0005_taskchange')]
    operations = [migrations.RunPython(import_assignments, migrations.RunPython.noop)]

