# Generated by Django 4.2.17 on 2024-12-25 19:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sales', '0002_alter_sale_sale_date'),
        ('inventory', '0006_alter_product_delivery_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='MiscellaneousExpense',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('description', models.TextField()),
                ('cost', models.DecimalField(decimal_places=2, max_digits=10)),
                ('date', models.DateField(auto_now_add=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ShippingExpense',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cost', models.DecimalField(decimal_places=2, max_digits=10)),
                ('description', models.TextField(blank=True, null=True)),
                ('date', models.DateField(auto_now_add=True)),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shipping_expenses', to='sales.sale')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ServicingExpense',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cost', models.DecimalField(decimal_places=2, max_digits=10)),
                ('description', models.TextField(blank=True, null=True)),
                ('date', models.DateField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='servicing_expenses', to='inventory.product')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
