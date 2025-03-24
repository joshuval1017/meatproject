# Generated by Django 5.0 on 2025-01-15 06:33

import django.db.models.deletion
import phonenumber_field.modelfields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DeliveryBoy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('phone', phonenumber_field.modelfields.PhoneNumberField(max_length=128, region=None, unique=True)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('address', models.TextField()),
                ('vehicle_type', models.CharField(choices=[('bike', 'Bike'), ('scooter', 'Scooter'), ('cycle', 'Cycle')], max_length=10)),
                ('vehicle_number', models.CharField(blank=True, max_length=20, null=True)),
                ('license_number', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_boys', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Delivery Boy',
                'verbose_name_plural': 'Delivery Boys',
                'ordering': ['-created_at'],
            },
        ),
    ]
