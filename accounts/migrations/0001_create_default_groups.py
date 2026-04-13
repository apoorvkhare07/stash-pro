from django.db import migrations


def create_default_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    owner_group, _ = Group.objects.get_or_create(name='Owner')
    staff_group, _ = Group.objects.get_or_create(name='Staff')

    all_perms = Permission.objects.all()
    owner_group.permissions.set(all_perms)

    staff_apps = ['inventory', 'sales']
    staff_perms = Permission.objects.filter(
        content_type__app_label__in=staff_apps
    )
    staff_group.permissions.set(staff_perms)


def remove_default_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['Owner', 'Staff']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(create_default_groups, remove_default_groups),
    ]
