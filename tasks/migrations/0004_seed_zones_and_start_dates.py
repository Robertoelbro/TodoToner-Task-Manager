from django.db import migrations
from zoneinfo import ZoneInfo


def populate(apps, schema_editor):
    Zone = apps.get_model('tasks', 'Zone')
    Task = apps.get_model('tasks', 'Task')
    alias = schema_editor.connection.alias
    for code, name in [('ventas', 'Ventas'), ('postventas', 'Postventas'), ('bodega', 'Bodega')]:
        Zone.objects.using(alias).get_or_create(code=code, defaults={'name': name})
    for task in Task.objects.using(alias).all().iterator():
        created_date = task.created_at.astimezone(ZoneInfo('America/Santiago')).date()
        task.start_date = min(created_date, task.deadline)
        task.save(using=alias, update_fields=['start_date'])


class Migration(migrations.Migration):
    dependencies = [('tasks', '0003_zone_task_start_date_task_zones')]
    operations = [migrations.RunPython(populate, migrations.RunPython.noop)]

