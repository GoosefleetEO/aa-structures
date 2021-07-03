# Generated by Django 3.1.12 on 2021-07-03 19:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0025_add_poco_details"),
    ]

    operations = [
        migrations.RenameField(
            model_name="owner",
            old_name="character",
            new_name="character_ownership",
        ),
        migrations.RenameField(
            model_name="owner",
            old_name="forwarding_last_sync",
            new_name="forwarding_last_update_at",
        ),
        migrations.RenameField(
            model_name="owner",
            old_name="notifications_last_sync",
            new_name="notifications_last_update_at",
        ),
        migrations.RenameField(
            model_name="owner",
            old_name="structures_last_sync",
            new_name="structures_last_update_at",
        ),
        migrations.RemoveField(
            model_name="owner",
            name="assets_last_error",
        ),
        migrations.RemoveField(
            model_name="owner",
            name="assets_last_sync",
        ),
        migrations.RemoveField(
            model_name="owner",
            name="forwarding_last_error",
        ),
        migrations.RemoveField(
            model_name="owner",
            name="notifications_last_error",
        ),
        migrations.RemoveField(
            model_name="owner",
            name="structures_last_error",
        ),
        migrations.AddField(
            model_name="owner",
            name="assets_last_update_at",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="when the last update happened",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="owner",
            name="assets_last_update_ok",
            field=models.BooleanField(
                default=None,
                help_text="True if the last update was successful",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="owner",
            name="forwarding_last_update_ok",
            field=models.BooleanField(
                default=None,
                help_text="True if the last update was successful",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="owner",
            name="notifications_last_update_ok",
            field=models.BooleanField(
                default=None,
                help_text="True if the last update was successful",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="owner",
            name="structures_last_update_ok",
            field=models.BooleanField(
                default=None,
                help_text="True if the last update was successful",
                null=True,
            ),
        ),
    ]
