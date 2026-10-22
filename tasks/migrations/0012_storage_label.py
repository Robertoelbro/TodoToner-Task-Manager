from django.db import migrations


def forwards(apps, schema_editor):
    apps.get_model('tasks', 'Zone').objects.filter(code='bodega').update(name='Storage')


def backwards(apps, schema_editor):
    apps.get_model('tasks', 'Zone').objects.filter(code='bodega').update(name='Bodega')


class Migration(migrations.Migration):
    dependencies = [('tasks', '0011_task_parent_task_spectator_areas_task_spectators')]
    operations = [migrations.RunPython(forwards, backwards)]
