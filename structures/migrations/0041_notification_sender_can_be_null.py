# Generated by Django 4.0.7 on 2022-08-17 17:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("structures", "0040_add_generated_notifications"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="sender",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="structures.eveentity",
            ),
        ),
    ]
