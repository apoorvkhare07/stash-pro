from django.db import migrations


def seed_default_org(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    UserOrganization = apps.get_model('accounts', 'UserOrganization')
    User = apps.get_model('auth', 'User')
    Product = apps.get_model('inventory', 'Product')
    Lot = apps.get_model('inventory', 'Lot')
    Sale = apps.get_model('sales', 'Sale')
    Expenses = apps.get_model('expense', 'Expenses')

    # Create default org
    org, _ = Organization.objects.get_or_create(
        slug='apoorv-personal',
        defaults={'name': 'Apoorv Personal'}
    )

    # Assign all existing users as owners of default org
    for user in User.objects.all():
        UserOrganization.objects.get_or_create(
            user=user,
            organization=org,
            defaults={'role': 'owner'}
        )

    # Assign all existing data to default org
    Product.objects.filter(organization__isnull=True).update(organization=org)
    Lot.objects.filter(organization__isnull=True).update(organization=org)
    Sale.objects.filter(organization__isnull=True).update(organization=org)
    Expenses.objects.filter(organization__isnull=True).update(organization=org)


def reverse(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    Organization.objects.filter(slug='apoorv-personal').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_initial'),
        ('inventory', '0014_lot_organization_product_organization'),
        ('sales', '0010_sale_organization'),
        ('expense', '0004_expenses_organization'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(seed_default_org, reverse),
    ]
