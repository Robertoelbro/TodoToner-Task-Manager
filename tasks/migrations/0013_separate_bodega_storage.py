from django.db import migrations


def separate_areas(apps, schema_editor):
    zones = apps.get_model('tasks', 'Zone').objects.using(schema_editor.connection.alias)
    # Keep the current Storage row and its user/task relationships intact.
    if not zones.filter(code='storage').exists():
        zones.filter(code='bodega', name='Storage').update(code='storage')
    zones.get_or_create(code='storage', defaults={'name': 'Storage'})
    zones.get_or_create(code='bodega', defaults={'name': 'Bodega'})


class Migration(migrations.Migration):
    dependencies = [('tasks', '0012_storage_label')]
    # Do not remove areas on rollback: they may already have assigned users/tasks.
    operations = [migrations.RunPython(separate_areas, migrations.RunPython.noop)]
