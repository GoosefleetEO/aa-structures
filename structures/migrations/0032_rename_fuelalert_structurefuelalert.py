# Generated by Django 3.2.9 on 2021-12-10 21:29

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('structures', '0031_add_service_up'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='FuelAlert',
            new_name='StructureFuelAlert',
        ),
    ]
