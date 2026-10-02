from django.db import migrations


def add_zone(apps, schema_editor):
    apps.get_model('tasks', 'Zone').objects.using(schema_editor.connection.alias).get_or_create(
        code='administracion', defaults={'name': 'Administración'})


class Migration(migrations.Migration):
    dependencies = [('tasks', '0007_task_deadline_time_task_start_time')]
    operations = [migrations.RunPython(add_zone, migrations.RunPython.noop)]

