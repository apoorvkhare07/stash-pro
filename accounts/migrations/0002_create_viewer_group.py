from django.db import migrations


def create_viewer_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    viewer_group, _ = Group.objects.get_or_create(name='Viewer')

    # Viewer gets view-only permissions on all apps
    view_perms = Permission.objects.filter(codename__startswith='view_')
    viewer_group.permissions.set(view_perms)


def remove_viewer_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='Viewer').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_create_default_groups'),
    ]

    operations = [
        migrations.RunPython(create_viewer_group, remove_viewer_group),
    ]
