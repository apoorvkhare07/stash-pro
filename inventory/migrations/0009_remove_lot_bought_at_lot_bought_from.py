# Generated by Django 4.2.17 on 2025-03-14 08:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0008_lot_product_lot'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lot',
            name='bought_at',
        ),
        migrations.AddField(
            model_name='lot',
            name='bought_from',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
