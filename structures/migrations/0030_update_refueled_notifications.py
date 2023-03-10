# Generated by Django 3.1.13 on 2021-08-17 14:08

import multiselectfield.db.fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0029_custom_fuel_notifications"),
    ]

    operations = [
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
                    ("StructureFuelAlert", "Upwell structure fuel alert"),
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
                    "StructureFuelAlert",
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
                max_length=962,
            ),
        ),
    ]
