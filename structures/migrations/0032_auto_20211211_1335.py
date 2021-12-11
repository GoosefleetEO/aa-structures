# Generated by Django 3.2.9 on 2021-12-11 13:35

import multiselectfield.db.fields

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0031_add_service_up"),
    ]

    operations = [
        migrations.CreateModel(
            name="JumpFuelAlertConfig",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "channel_ping_type",
                    models.CharField(
                        choices=[("NO", "none"), ("HE", "here"), ("EV", "everyone")],
                        default="HE",
                        help_text="Option to ping every member of the channel. This setting can be overruled by the respective owner or webhook configuration",
                        max_length=2,
                        verbose_name="channel pings",
                    ),
                ),
                (
                    "color",
                    models.IntegerField(
                        blank=True,
                        choices=[
                            (14242639, "danger"),
                            (6013150, "info"),
                            (6076508, "success"),
                            (15773006, "warning"),
                        ],
                        default=15773006,
                        null=True,
                    ),
                ),
                ("is_enabled", models.BooleanField(default=True)),
                (
                    "threshold",
                    models.PositiveIntegerField(
                        help_text="Notifications will be sent once fuel level in units reaches this threshold"
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AlterModelOptions(
            name="fuelalert",
            options={"verbose_name": "StructureFuelAlert"},
        ),
        migrations.AlterModelOptions(
            name="fuelalertconfig",
            options={"verbose_name": "StructureFuelAlertConfig"},
        ),
        migrations.AlterField(
            model_name="fuelalert",
            name="config",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="structure_fuel_alerts",
                to="structures.fuelalertconfig",
            ),
        ),
        migrations.AlterField(
            model_name="fuelalert",
            name="structure",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="structure_fuel_alerts",
                to="structures.structure",
            ),
        ),
        migrations.AlterField(
            model_name="webhook",
            name="notification_types",
            field=multiselectfield.db.fields.MultiSelectField(
                choices=[
                    ("StructureAnchoring", "Upwell structure anchoring"),
                    ("StructureOnline", "Upwell structure went online"),
                    (
                        "StructureServicesOffline",
                        "Upwell structure services went offline",
                    ),
                    ("StructureWentHighPower", "Upwell structure went high power"),
                    ("StructureWentLowPower", "Upwell structure went low power"),
                    ("StructureUnanchoring", "Upwell structure unanchoring"),
                    ("FuelAlert", "Upwell structure fuel alert"),
                    ("StructureRefueledExtra", "Upwell structure refueled"),
                    ("StructureUnderAttack", "Upwell structure is under attack"),
                    ("StructureLostShields", "Upwell structure lost shields"),
                    ("StructureLostArmor", "Upwell structure lost armor"),
                    ("StructureDestroyed", "Upwell structure destroyed"),
                    (
                        "StructuresReinforcementChanged",
                        "Upwell structure reinforcement time changed",
                    ),
                    ("OwnershipTransferred", "Upwell structure ownership transferred"),
                    ("OrbitalAttacked", "Customs office attacked"),
                    ("OrbitalReinforced", "Customs office reinforced"),
                    ("TowerAlertMsg", "Starbase attacked"),
                    ("TowerResourceAlertMsg", "Starbase fuel alert"),
                    ("TowerRefueledExtra", "Starbase refueled"),
                    ("MoonminingExtractionStarted", "Moonmining extraction started"),
                    ("MoonminingLaserFired", "Moonmining laser fired"),
                    (
                        "MoonminingExtractionCancelled",
                        "Moonmining extraction cancelled",
                    ),
                    ("MoonminingExtractionFinished", "Moonmining extraction finished"),
                    (
                        "MoonminingAutomaticFracture",
                        "Moonmining automatic fracture triggered",
                    ),
                    ("SovStructureReinforced", "Sovereignty structure reinforced"),
                    ("SovStructureDestroyed", "Sovereignty structure destroyed"),
                    ("EntosisCaptureStarted", "Sovereignty entosis capture started"),
                    (
                        "SovCommandNodeEventStarted",
                        "Sovereignty command node event started",
                    ),
                    ("SovAllClaimAquiredMsg", "Sovereignty claim acknowledgment"),
                    ("SovAllClaimLostMsg", "Sovereignty lost"),
                    ("WarDeclared", "War declared"),
                    ("AllyJoinedWarAggressorMsg", "War ally joined aggressor"),
                    ("AllyJoinedWarAllyMsg", "War ally joined ally"),
                    ("AllyJoinedWarDefenderMsg", "War ally joined defender"),
                    ("WarAdopted", "War adopted"),
                    ("WarInherited", "War inherited"),
                    ("CorpWarSurrenderMsg", "War party surrendered"),
                    ("WarRetractedByConcord", "War retracted by Concord"),
                    ("CorpBecameWarEligible", "War corporation became eligable"),
                    ("CorpNoLongerWarEligible", "War corporation no longer eligable"),
                    ("CorpAppNewMsg", "Character submitted application"),
                    ("CorpAppInvitedMsg", "Character invited to join corporation"),
                    ("CorpAppRejectCustomMsg", "Corp application rejected"),
                    ("CharAppWithdrawMsg", "Character withdrew application"),
                    ("CharAppAcceptMsg", "Character joins corporation"),
                    ("CharLeftCorpMsg", "Character leaves corporation"),
                ],
                default=[
                    "StructureAnchoring",
                    "StructureDestroyed",
                    "FuelAlert",
                    "StructureLostArmor",
                    "StructureLostShields",
                    "StructureOnline",
                    "StructureServicesOffline",
                    "StructureUnderAttack",
                    "StructureWentHighPower",
                    "StructureWentLowPower",
                    "OrbitalAttacked",
                    "OrbitalReinforced",
                    "TowerAlertMsg",
                    "TowerResourceAlertMsg",
                    "SovStructureReinforced",
                    "SovStructureDestroyed",
                ],
                help_text="select which type of notifications should be forwarded to this webhook",
                max_length=953,
            ),
        ),
        migrations.CreateModel(
            name="JumpFuelAlert",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "config",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="jump_fuel_alerts",
                        to="structures.jumpfuelalertconfig",
                    ),
                ),
                (
                    "structure",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="jump_fuel_alerts",
                        to="structures.structure",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
