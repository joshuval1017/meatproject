# Generated by Django 5.0 on 2025-01-15 08:44

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_orderdelivery'),
    ]

    operations = [
        migrations.DeleteModel(
            name='OrderDelivery',
        ),
    ]
