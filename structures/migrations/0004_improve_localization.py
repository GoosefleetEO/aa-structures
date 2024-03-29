# Generated by Django 4.0.10 on 2023-10-30 17:26

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("eveuniverse", "0010_alter_eveindustryactivityduration_eve_type_and_more"),
        ("authentication", "0021_alter_userprofile_language"),
        ("structures", "0003_add_localization_and_unique_key"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fuelalert",
            name="hours",
            field=models.PositiveIntegerField(
                db_index=True,
                help_text="Number of hours before fuel expiration this alert was sent",
                verbose_name="hours",
            ),
        ),
        migrations.AlterField(
            model_name="generatednotification",
            name="notif_type",
            field=models.CharField(
                db_index=True,
                default="",
                help_text="Type of this notification",
                max_length=100,
                verbose_name="type",
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="notif_type",
            field=models.CharField(
                db_index=True,
                default="",
                help_text="Type of this notification",
                max_length=100,
                verbose_name="type",
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="forwarding_last_update_at",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="When the last successful update happened",
                null=True,
                verbose_name="forwarding last update at",
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="has_default_pings_enabled",
            field=models.BooleanField(
                default=True,
                help_text="To enable or disable pinging of notifications for this owner e.g. with @everyone and @here",
                verbose_name="has default pings enabled",
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="is_active",
            field=models.BooleanField(
                default=True,
                help_text="Whether this owner is currently included in the sync process",
                verbose_name="is active",
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="is_alliance_main",
            field=models.BooleanField(
                default=False,
                help_text="Whether alliance wide notifications are forwarded for this owner (e.g. sov notifications)",
                verbose_name="is alliance main",
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="is_included_in_service_status",
            field=models.BooleanField(
                default=True,
                help_text="Whether the sync status of this owner is included in the overall status of this services",
                verbose_name="is included in service status",
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="is_up",
            field=models.BooleanField(
                default=None,
                editable=False,
                help_text="Whether all services for this owner are currently up",
                null=True,
                verbose_name="is up",
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="notifications_last_update_at",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="When the last successful update happened",
                null=True,
                verbose_name="notifications last update at",
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="structures_last_update_at",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="When the last successful update happened",
                null=True,
                verbose_name="structures last update at",
            ),
        ),
        migrations.AlterField(
            model_name="ownercharacter",
            name="character_ownership",
            field=models.ForeignKey(
                help_text="Character used for syncing",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="authentication.characterownership",
                verbose_name="character_ownership",
            ),
        ),
        migrations.AlterField(
            model_name="ownercharacter",
            name="notifications_last_used_at",
            field=models.DateTimeField(
                db_index=True,
                default=None,
                editable=False,
                help_text="When this character was last used for syncing notifications",
                null=True,
                verbose_name="notifications last used at",
            ),
        ),
        migrations.AlterField(
            model_name="ownercharacter",
            name="structures_last_used_at",
            field=models.DateTimeField(
                db_index=True,
                default=None,
                editable=False,
                help_text="When this character was last used for syncing structures",
                null=True,
                verbose_name="structures last used at",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="created_at",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                help_text="Date this structure was received from ESI for the first time",
                verbose_name="created at",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="has_core",
            field=models.BooleanField(
                blank=True,
                db_index=True,
                default=None,
                help_text="Whether the structure has a quantum core",
                null=True,
                verbose_name="has core",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="has_fitting",
            field=models.BooleanField(
                blank=True,
                db_index=True,
                default=None,
                help_text="Whether the structure has a fitting",
                null=True,
                verbose_name="has fitting",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="last_online_at",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="Date this structure had any of it's services online",
                null=True,
                verbose_name="last online at",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="last_updated_at",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="Date this structure was last updated from the EVE server",
                null=True,
                verbose_name="last updated at",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="position_x",
            field=models.FloatField(
                blank=True,
                default=None,
                help_text="X coordinate of position in the solar system",
                null=True,
                verbose_name="position x",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="position_y",
            field=models.FloatField(
                blank=True,
                default=None,
                help_text="Y coordinate of position in the solar system",
                null=True,
                verbose_name="position y",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="position_z",
            field=models.FloatField(
                blank=True,
                default=None,
                help_text="Z coordinate of position in the solar system",
                null=True,
                verbose_name="position z",
            ),
        ),
        migrations.AlterField(
            model_name="structureitem",
            name="eve_type",
            field=models.ForeignKey(
                help_text="Type of the item",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="eveuniverse.evetype",
                verbose_name="type",
            ),
        ),
        migrations.AlterField(
            model_name="structuretag",
            name="description",
            field=models.TextField(
                blank=True,
                default=None,
                help_text="Description for this tag",
                null=True,
                verbose_name="description",
            ),
        ),
        migrations.AlterField(
            model_name="structuretag",
            name="is_default",
            field=models.BooleanField(
                default=False,
                help_text="When enabled this custom tag will automatically be added to new structures",
                verbose_name="is default",
            ),
        ),
        migrations.AlterField(
            model_name="structuretag",
            name="is_user_managed",
            field=models.BooleanField(
                default=True,
                help_text="When disabled this tag is created and managed by the system and can not be modified by users",
                verbose_name="is user managed",
            ),
        ),
        migrations.AlterField(
            model_name="structuretag",
            name="name",
            field=models.CharField(
                help_text="Name of the tag, which must be unique",
                max_length=255,
                unique=True,
                verbose_name="name",
            ),
        ),
        migrations.AlterField(
            model_name="structuretag",
            name="order",
            field=models.PositiveIntegerField(
                blank=True,
                default=100,
                help_text="Number defining the order tags are shown. custom tags can not have an order below 100",
                validators=[django.core.validators.MinValueValidator(100)],
                verbose_name="order",
            ),
        ),
        migrations.AlterField(
            model_name="structuretag",
            name="style",
            field=models.CharField(
                blank=True,
                choices=[
                    ("default", "grey"),
                    ("primary", "dark blue"),
                    ("success", "green"),
                    ("info", "light blue"),
                    ("warning", "orange"),
                    ("danger", "red"),
                ],
                default="default",
                help_text="Color style of tag",
                max_length=16,
                verbose_name="style",
            ),
        ),
        migrations.AlterField(
            model_name="webhook",
            name="is_active",
            field=models.BooleanField(
                default=True,
                help_text="Whether notifications are currently sent to this webhook",
                verbose_name="is active",
            ),
        ),
        migrations.AlterField(
            model_name="webhook",
            name="language_code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("en", "English"),
                    ("de", "German"),
                    ("es", "Spanish"),
                    ("zh-hans", "Chinese Simplified"),
                    ("ru", "Russian"),
                    ("ko", "Korean"),
                ],
                default=None,
                help_text="Language of notifications send to this webhook",
                max_length=8,
                null=True,
                verbose_name="language",
            ),
        ),
        migrations.AlterField(
            model_name="webhook",
            name="name",
            field=models.CharField(
                help_text="Short name to identify this webhook",
                max_length=64,
                unique=True,
                verbose_name="name",
            ),
        ),
        migrations.AlterField(
            model_name="webhook",
            name="notes",
            field=models.TextField(
                blank=True,
                default=None,
                help_text="Notes regarding this webhook",
                null=True,
                verbose_name="notes",
            ),
        ),
        migrations.AlterField(
            model_name="webhook",
            name="url",
            field=models.CharField(
                help_text="URL of this webhook, e.g. https://discordapp.com/api/webhooks/123456/abcdef",
                max_length=255,
                unique=True,
                verbose_name="url",
            ),
        ),
        migrations.AlterField(
            model_name="webhook",
            name="webhook_type",
            field=models.IntegerField(
                choices=[(1, "Discord Webhook")],
                default=1,
                help_text="Type of this webhook",
                verbose_name="webhook type",
            ),
        ),
    ]
