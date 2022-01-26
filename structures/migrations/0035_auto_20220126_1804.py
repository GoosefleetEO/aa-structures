# Generated by Django 3.2.11 on 2022-01-26 18:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0034_notification_structure"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="notification",
            name="structure",
        ),
        migrations.AddField(
            model_name="notification",
            name="structures",
            field=models.ManyToManyField(
                help_text="Structures this notification is about (if any)",
                related_name="notifications",
                to="structures.Structure",
            ),
        ),
    ]
