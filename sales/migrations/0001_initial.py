# Generated by Django 4.2.17 on 2024-12-25 19:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('inventory', '0004_alter_product_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='Sale',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quantity_sold', models.PositiveIntegerField()),
                ('sale_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('customer', models.CharField(blank=True, max_length=255, null=True)),
                ('payment_status', models.CharField(choices=[('Pending', 'Pending'), ('Completed', 'Completed')], default='Pending', max_length=10)),
                ('sale_date', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sales', to='inventory.product')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
