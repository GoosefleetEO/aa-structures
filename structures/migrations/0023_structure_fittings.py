# Generated by Django 3.1.6 on 2021-04-29 21:48

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0017_remove_fleetup_permission"),
        ("eveonline", "0014_auto_20210105_1413"),
        ("structures", "0022_add_corp_app_notification_types"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="general",
            options={
                "default_permissions": (),
                "managed": False,
                "permissions": (
                    ("basic_access", "Can access this app and view public pages"),
                    ("view_corporation_structures", "Can view corporation structures"),
                    ("view_alliance_structures", "Can view alliance structures"),
                    ("view_all_structures", "Can view all structures"),
                    ("add_structure_owner", "Can add new structure owner"),
                    (
                        "view_all_unanchoring_status",
                        "Can view unanchoring timers for all structures the user can see",
                    ),
                    ("view_structure_fit", "Can view structure fit"),
                ),
            },
        ),
        migrations.AddField(
            model_name="owner",
            name="assets_last_error",
            field=models.IntegerField(
                choices=[
                    (0, "No error"),
                    (1, "Invalid token"),
                    (2, "Expired token"),
                    (3, "Insufficient permissions"),
                    (4, "No character set for fetching data from ESI"),
                    (5, "ESI API is currently unavailable"),
                    (6, "Operaton mode does not match with current setting"),
                    (99, "Unknown error"),
                ],
                default=0,
                help_text="error that occurred at the last sync atttempt (if any)",
            ),
        ),
        migrations.AddField(
            model_name="owner",
            name="assets_last_sync",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="when the last sync happened",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="structure",
            name="has_core",
            field=models.BooleanField(
                blank=True,
                db_index=True,
                default=None,
                help_text="bool indicating if the structure has a quantum core",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="structure",
            name="has_fitting",
            field=models.BooleanField(
                blank=True,
                db_index=True,
                default=None,
                help_text="bool indicating if the structure has a fitting",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="eveconstellation",
            name="eve_region",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eve_constellations",
                to="structures.everegion",
            ),
        ),
        migrations.AlterField(
            model_name="evegroup",
            name="eve_category",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                related_name="eve_groups",
                to="structures.evecategory",
            ),
        ),
        migrations.AlterField(
            model_name="evemoon",
            name="eve_solar_system",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eve_moons",
                to="structures.evesolarsystem",
            ),
        ),
        migrations.AlterField(
            model_name="eveplanet",
            name="eve_solar_system",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eve_planets",
                to="structures.evesolarsystem",
            ),
        ),
        migrations.AlterField(
            model_name="evesolarsystem",
            name="eve_constellation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eve_solar_systems",
                to="structures.eveconstellation",
            ),
        ),
        migrations.AlterField(
            model_name="evetype",
            name="eve_group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eve_types",
                to="structures.evegroup",
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="owner",
            field=models.ForeignKey(
                help_text="Corporation that received this notification",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notifications",
                to="structures.owner",
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="character",
            field=models.ForeignKey(
                blank=True,
                default=None,
                help_text="character used for syncing structures",
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                related_name="+",
                to="authentication.characterownership",
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="corporation",
            field=models.OneToOneField(
                help_text="Corporation owning structures",
                on_delete=django.db.models.deletion.CASCADE,
                primary_key=True,
                related_name="structure_owner",
                serialize=False,
                to="eveonline.evecorporationinfo",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="owner",
            field=models.ForeignKey(
                help_text="Corporation that owns the structure",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="structures",
                to="structures.owner",
            ),
        ),
        migrations.AlterField(
            model_name="structureservice",
            name="structure",
            field=models.ForeignKey(
                help_text="Structure this service is installed to",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="services",
                to="structures.structure",
            ),
        ),
        migrations.CreateModel(
            name="OwnerAsset",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        help_text="The Item ID of the assets",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_singleton", models.BooleanField()),
                ("location_flag", models.CharField(max_length=255)),
                ("location_id", models.BigIntegerField(db_index=True)),
                ("location_type", models.CharField(max_length=255)),
                ("quantity", models.IntegerField()),
                ("last_updated_at", models.DateTimeField(auto_now=True)),
                (
                    "eve_type",
                    models.ForeignKey(
                        help_text="type of the assets",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="structures.evetype",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        help_text="Corporation that owns the assets",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assets",
                        to="structures.owner",
                    ),
                ),
            ],
        ),
    ]
