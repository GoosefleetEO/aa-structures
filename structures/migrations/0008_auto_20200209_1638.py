# Generated by Django 2.2.9 on 2020-02-09 16:38

import multiselectfield.db.fields

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import structures.models


class Migration(migrations.Migration):
    dependencies = [
        ("structures", "0007_auto_20200123_1429"),
    ]

    operations = [
        migrations.CreateModel(
            name="EveCategory",
            fields=[
                (
                    "id",
                    models.IntegerField(
                        help_text="Eve Online category ID",
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("name", models.CharField(max_length=100)),
            ],
        ),
        migrations.AddField(
            model_name="owner",
            name="is_active",
            field=models.BooleanField(
                default=True,
                help_text="whether this owner is currently included in the sync process",
            ),
        ),
        migrations.AddField(
            model_name="structure",
            name="eve_moon",
            field=models.ForeignKey(
                blank=True,
                default=None,
                help_text="Moon next to this structure - if any",
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                to="structures.EveMoon",
            ),
        ),
        migrations.AddField(
            model_name="structure",
            name="eve_planet",
            field=models.ForeignKey(
                blank=True,
                default=None,
                help_text="Planet next to this structure - if any",
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                to="structures.EvePlanet",
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.IntegerField(
                choices=[
                    (401, "MoonminingAutomaticFracture"),
                    (402, "MoonminingExtractionCancelled"),
                    (403, "MoonminingExtractionFinished"),
                    (404, "MoonminingExtractionStarted"),
                    (405, "MoonminingLaserFired"),
                    (513, "OwnershipTransferred"),
                    (501, "StructureAnchoring"),
                    (502, "StructureDestroyed"),
                    (503, "StructureFuelAlert"),
                    (504, "StructureLostArmor"),
                    (505, "StructureLostShields"),
                    (506, "StructureOnline"),
                    (507, "StructureServicesOffline"),
                    (508, "StructureUnanchoring"),
                    (509, "StructureUnderAttack"),
                    (510, "StructureWentHighPower"),
                    (511, "StructureWentLowPower"),
                    (601, "OrbitalAttacked"),
                    (602, "OrbitalReinforced"),
                    (701, "TowerAlertMsg"),
                    (702, "TowerResourceAlertMsg"),
                    (801, "EntosisCaptureStarted"),
                    (802, "SovCommandNodeEventStarted"),
                    (803, "SovAllClaimAquiredMsg"),
                    (804, "SovStructureReinforced"),
                    (805, "SovStructureDestroyed"),
                ]
            ),
        ),
        migrations.AlterField(
            model_name="owner",
            name="is_alliance_main",
            field=models.BooleanField(
                default=False,
                help_text="whether alliance wide notifications are forwarded for this owner (e.g. sov notifications)",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="state",
            field=models.IntegerField(
                blank=True,
                choices=[
                    (1, "anchor_vulnerable"),
                    (2, "anchoring"),
                    (3, "armor_reinforce"),
                    (4, "armor_vulnerable"),
                    (5, "deploy_vulnerable"),
                    (6, "fitting_invulnerable"),
                    (7, "hull_reinforce"),
                    (8, "hull_vulnerable"),
                    (9, "online_deprecated"),
                    (10, "onlining_vulnerable"),
                    (11, "shield_vulnerable"),
                    (12, "unanchored"),
                    (21, "offline"),
                    (22, "online"),
                    (23, "onlining"),
                    (24, "reinforced"),
                    (25, "unanchoring "),
                    (0, "N/A"),
                    (13, "unknown"),
                ],
                default=13,
                help_text="Current state of the structure",
            ),
        ),
        migrations.AlterField(
            model_name="webhook",
            name="notification_types",
            field=multiselectfield.db.fields.MultiSelectField(
                choices=[
                    (401, "MoonminingAutomaticFracture"),
                    (402, "MoonminingExtractionCancelled"),
                    (403, "MoonminingExtractionFinished"),
                    (404, "MoonminingExtractionStarted"),
                    (405, "MoonminingLaserFired"),
                    (513, "OwnershipTransferred"),
                    (501, "StructureAnchoring"),
                    (502, "StructureDestroyed"),
                    (503, "StructureFuelAlert"),
                    (504, "StructureLostArmor"),
                    (505, "StructureLostShields"),
                    (506, "StructureOnline"),
                    (507, "StructureServicesOffline"),
                    (508, "StructureUnanchoring"),
                    (509, "StructureUnderAttack"),
                    (510, "StructureWentHighPower"),
                    (511, "StructureWentLowPower"),
                    (601, "OrbitalAttacked"),
                    (602, "OrbitalReinforced"),
                    (701, "TowerAlertMsg"),
                    (702, "TowerResourceAlertMsg"),
                    (801, "EntosisCaptureStarted"),
                    (802, "SovCommandNodeEventStarted"),
                    (803, "SovAllClaimAquiredMsg"),
                    (804, "SovStructureReinforced"),
                    (805, "SovStructureDestroyed"),
                ],
                default=structures.models.get_default_notification_types,
                help_text="only notifications which selected types are sent to this webhook",
                max_length=103,
            ),
        ),
        migrations.AddField(
            model_name="evegroup",
            name="eve_category",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                to="structures.EveCategory",
            ),
        ),
    ]
