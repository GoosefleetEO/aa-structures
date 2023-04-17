"""Squashed migrations based on a new migration from scratch to get a clean basis."""

import multiselectfield.db.fields

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

import structures.webhooks.core


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("eveonline", "0015_factions"),
        ("authentication", "0019_merge_20211026_0919"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("eveuniverse", "0007_evetype_description"),
    ]

    operations = [
        migrations.CreateModel(
            name="General",
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
            ],
            options={
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
                "managed": False,
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="EveSovereigntyMap",
            fields=[
                (
                    "solar_system_id",
                    models.PositiveIntegerField(primary_key=True, serialize=False),
                ),
                (
                    "alliance_id",
                    models.PositiveIntegerField(
                        blank=True,
                        db_index=True,
                        help_text="alliance who holds sov for this system",
                        null=True,
                    ),
                ),
                (
                    "corporation_id",
                    models.PositiveIntegerField(
                        blank=True,
                        db_index=True,
                        help_text="corporation who holds sov for this system",
                        null=True,
                    ),
                ),
                (
                    "faction_id",
                    models.PositiveIntegerField(
                        blank=True,
                        db_index=True,
                        help_text="faction who holds sov for this system",
                        null=True,
                    ),
                ),
                (
                    "last_updated",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        default=None,
                        help_text="When this object was last updated from ESI",
                        null=True,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="FuelAlertConfig",
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
                        help_text="Context color of these notification on Discord",
                        null=True,
                    ),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=True,
                        help_text="Disabled configurations will not create any new alerts.",
                    ),
                ),
                (
                    "end",
                    models.PositiveIntegerField(
                        help_text="End of alerts in hours before fuel expires"
                    ),
                ),
                (
                    "repeat",
                    models.PositiveIntegerField(
                        help_text="Notifications will be repeated every x hours. Set to 0 for no repeats"
                    ),
                ),
                (
                    "start",
                    models.PositiveIntegerField(
                        help_text="Start of alerts in hours before fuel expires"
                    ),
                ),
            ],
            options={
                "verbose_name": "structure fuel alert config",
            },
        ),
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
                        help_text="Context color of these notification on Discord",
                        null=True,
                    ),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=True,
                        help_text="Disabled configurations will not create any new alerts.",
                    ),
                ),
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
        migrations.CreateModel(
            name="Owner",
            fields=[
                (
                    "corporation",
                    models.OneToOneField(
                        help_text="Corporation owning structures",
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="structure_owner",
                        serialize=False,
                        to="eveonline.evecorporationinfo",
                    ),
                ),
                (
                    "are_pocos_public",
                    models.BooleanField(
                        default=False,
                        help_text="whether pocos of this owner are shown on public POCO page",
                    ),
                ),
                (
                    "assets_last_update_at",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="when the last successful update happened",
                        null=True,
                    ),
                ),
                (
                    "forwarding_last_update_at",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="when the last successful update happened",
                        null=True,
                    ),
                ),
                (
                    "has_default_pings_enabled",
                    models.BooleanField(
                        default=True,
                        help_text="to enable or disable pinging of notifications for this owner e.g. with @everyone and @here",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="whether this owner is currently included in the sync process",
                    ),
                ),
                (
                    "is_alliance_main",
                    models.BooleanField(
                        default=False,
                        help_text="whether alliance wide notifications are forwarded for this owner (e.g. sov notifications)",
                    ),
                ),
                (
                    "is_included_in_service_status",
                    models.BooleanField(
                        default=True,
                        help_text="whether the sync status of this owner is included in the overall status of this services",
                    ),
                ),
                (
                    "is_up",
                    models.BooleanField(
                        default=None,
                        editable=False,
                        help_text="whether all services for this owner are currently up",
                        null=True,
                    ),
                ),
                (
                    "notifications_last_update_at",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="when the last successful update happened",
                        null=True,
                    ),
                ),
                (
                    "structures_last_update_at",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="when the last successful update happened",
                        null=True,
                    ),
                ),
                (
                    "character_ownership",
                    models.ForeignKey(
                        blank=True,
                        default=None,
                        help_text="OUTDATED. Has been replaced by OwnerCharacter",
                        null=True,
                        on_delete=django.db.models.deletion.SET_DEFAULT,
                        related_name="+",
                        to="authentication.characterownership",
                    ),
                ),
                (
                    "ping_groups",
                    models.ManyToManyField(
                        blank=True,
                        default=None,
                        help_text="Groups to be pinged for each notification. ",
                        related_name="+",
                        to="auth.group",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="StarbaseDetail",
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
                ("allow_alliance_members", models.BooleanField()),
                ("allow_corporation_members", models.BooleanField()),
                (
                    "anchor_role",
                    models.CharField(
                        choices=[
                            ("AL", "alliance member"),
                            ("CE", "config starbase equipment role"),
                            ("CO", "corporation member"),
                            ("FT", "starbase fuel technician role"),
                        ],
                        max_length=2,
                    ),
                ),
                ("attack_if_at_war", models.BooleanField()),
                ("attack_if_other_security_status_dropping", models.BooleanField()),
                (
                    "attack_security_status_threshold",
                    models.FloatField(default=None, null=True),
                ),
                (
                    "attack_standing_threshold",
                    models.FloatField(default=None, null=True),
                ),
                (
                    "fuel_bay_take_role",
                    models.CharField(
                        choices=[
                            ("AL", "alliance member"),
                            ("CE", "config starbase equipment role"),
                            ("CO", "corporation member"),
                            ("FT", "starbase fuel technician role"),
                        ],
                        max_length=2,
                    ),
                ),
                (
                    "fuel_bay_view_role",
                    models.CharField(
                        choices=[
                            ("AL", "alliance member"),
                            ("CE", "config starbase equipment role"),
                            ("CO", "corporation member"),
                            ("FT", "starbase fuel technician role"),
                        ],
                        max_length=2,
                    ),
                ),
                (
                    "last_modified_at",
                    models.DateTimeField(
                        help_text="When data was modified on the server."
                    ),
                ),
                (
                    "offline_role",
                    models.CharField(
                        choices=[
                            ("AL", "alliance member"),
                            ("CE", "config starbase equipment role"),
                            ("CO", "corporation member"),
                            ("FT", "starbase fuel technician role"),
                        ],
                        max_length=2,
                    ),
                ),
                (
                    "online_role",
                    models.CharField(
                        choices=[
                            ("AL", "alliance member"),
                            ("CE", "config starbase equipment role"),
                            ("CO", "corporation member"),
                            ("FT", "starbase fuel technician role"),
                        ],
                        max_length=2,
                    ),
                ),
                (
                    "unanchor_role",
                    models.CharField(
                        choices=[
                            ("AL", "alliance member"),
                            ("CE", "config starbase equipment role"),
                            ("CO", "corporation member"),
                            ("FT", "starbase fuel technician role"),
                        ],
                        max_length=2,
                    ),
                ),
                ("use_alliance_standings", models.BooleanField()),
            ],
        ),
        migrations.CreateModel(
            name="Structure",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        help_text="The Item ID of the structure",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        help_text="date this structure was received from ESI for the first time",
                    ),
                ),
                (
                    "fuel_expires_at",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="Date on which the structure will run out of fuel",
                        null=True,
                    ),
                ),
                (
                    "has_fitting",
                    models.BooleanField(
                        blank=True,
                        db_index=True,
                        default=None,
                        help_text="bool indicating if the structure has a fitting",
                        null=True,
                    ),
                ),
                (
                    "has_core",
                    models.BooleanField(
                        blank=True,
                        db_index=True,
                        default=None,
                        help_text="bool indicating if the structure has a quantum core",
                        null=True,
                    ),
                ),
                (
                    "last_online_at",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="date this structure had any of it's services online",
                        null=True,
                    ),
                ),
                (
                    "last_updated_at",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="date this structure was last updated from the EVE server",
                        null=True,
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="The full name of the structure", max_length=255
                    ),
                ),
                (
                    "next_reinforce_hour",
                    models.PositiveIntegerField(
                        blank=True,
                        default=None,
                        help_text="The requested change to reinforce_hour that will take effect at the time shown by next_reinforce_apply",
                        null=True,
                        validators=[django.core.validators.MaxValueValidator(23)],
                    ),
                ),
                (
                    "next_reinforce_apply",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="The requested change to reinforce_hour that will take effect at the time shown by next_reinforce_apply",
                        null=True,
                    ),
                ),
                (
                    "reinforce_hour",
                    models.PositiveIntegerField(
                        blank=True,
                        default=None,
                        help_text="The hour of day that determines the four hour window when the structure will randomly exit its reinforcement periods and become vulnerable to attack against its armor and/or hull. The structure will become vulnerable at a random time that is +/- 2 hours centered on the value of this property",
                        null=True,
                        validators=[django.core.validators.MaxValueValidator(23)],
                    ),
                ),
                (
                    "position_x",
                    models.FloatField(
                        blank=True,
                        default=None,
                        help_text="x position in the solar system",
                        null=True,
                    ),
                ),
                (
                    "position_y",
                    models.FloatField(
                        blank=True,
                        default=None,
                        help_text="y position in the solar system",
                        null=True,
                    ),
                ),
                (
                    "position_z",
                    models.FloatField(
                        blank=True,
                        default=None,
                        help_text="z position in the solar system",
                        null=True,
                    ),
                ),
                (
                    "state",
                    models.IntegerField(
                        blank=True,
                        choices=[
                            (1, "anchor vulnerable"),
                            (2, "anchoring"),
                            (3, "armor reinforce"),
                            (4, "armor vulnerable"),
                            (5, "deploy vulnerable"),
                            (6, "fitting invulnerable"),
                            (7, "hull reinforce"),
                            (8, "hull vulnerable"),
                            (9, "online deprecated"),
                            (10, "onlining vulnerable"),
                            (11, "shield vulnerable"),
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
                (
                    "state_timer_end",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="Date at which the structure entered it’s current state",
                        null=True,
                    ),
                ),
                (
                    "state_timer_start",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="Date at which the structure will move to it’s next state",
                        null=True,
                    ),
                ),
                (
                    "unanchors_at",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="Date at which the structure will unanchor",
                        null=True,
                    ),
                ),
                (
                    "eve_moon",
                    models.ForeignKey(
                        blank=True,
                        default=None,
                        help_text="Moon next to this structure - if any",
                        null=True,
                        on_delete=django.db.models.deletion.SET_DEFAULT,
                        to="eveuniverse.evemoon",
                    ),
                ),
                (
                    "eve_planet",
                    models.ForeignKey(
                        blank=True,
                        default=None,
                        help_text="Planet next to this structure - if any",
                        null=True,
                        on_delete=django.db.models.deletion.SET_DEFAULT,
                        to="eveuniverse.eveplanet",
                    ),
                ),
                (
                    "eve_solar_system",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="eveuniverse.evesolarsystem",
                    ),
                ),
                (
                    "eve_type",
                    models.ForeignKey(
                        help_text="type of the structure",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="eveuniverse.evetype",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        help_text="Corporation that owns the structure",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="structures",
                        to="structures.owner",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="StructureTag",
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
                    "name",
                    models.CharField(
                        help_text="name of the tag - must be unique",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default=None,
                        help_text="description for this tag",
                        null=True,
                    ),
                ),
                (
                    "style",
                    models.CharField(
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
                        help_text="color style of tag",
                        max_length=16,
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        blank=True,
                        default=100,
                        help_text="number defining the order tags are shown. custom tags can not have an order below 100",
                        validators=[django.core.validators.MinValueValidator(100)],
                    ),
                ),
                (
                    "is_default",
                    models.BooleanField(
                        default=False,
                        help_text="if true this custom tag will automatically be added to new structures",
                    ),
                ),
                (
                    "is_user_managed",
                    models.BooleanField(
                        default=True,
                        help_text="if False this tag is created and managed by the system and can not be modified by users",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Webhook",
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
                    "name",
                    models.CharField(
                        help_text="short name to identify this webhook",
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "url",
                    models.CharField(
                        help_text="URL of this webhook, e.g. https://discordapp.com/api/webhooks/123456/abcdef",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        default=None,
                        help_text="you can add notes about this webhook here if you want",
                        null=True,
                    ),
                ),
                (
                    "webhook_type",
                    models.IntegerField(
                        choices=[(1, "Discord Webhook")],
                        default=1,
                        help_text="type of this webhook",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="whether notifications are currently sent to this webhook",
                    ),
                ),
                (
                    "notification_types",
                    multiselectfield.db.fields.MultiSelectField(
                        choices=[
                            ("StructureAnchoring", "Upwell structure anchoring"),
                            ("StructureOnline", "Upwell structure went online"),
                            (
                                "StructureServicesOffline",
                                "Upwell structure services went offline",
                            ),
                            (
                                "StructureWentHighPower",
                                "Upwell structure went high power",
                            ),
                            (
                                "StructureWentLowPower",
                                "Upwell structure went low power",
                            ),
                            ("StructureUnanchoring", "Upwell structure unanchoring"),
                            ("StructureFuelAlert", "Upwell structure fuel alert"),
                            ("StructureRefueledExtra", "Upwell structure refueled"),
                            (
                                "StructureJumpFuelAlert",
                                "Upwell structure jump fuel alert",
                            ),
                            (
                                "StructureUnderAttack",
                                "Upwell structure is under attack",
                            ),
                            ("StructureLostShields", "Upwell structure lost shields"),
                            ("StructureLostArmor", "Upwell structure lost armor"),
                            ("StructureDestroyed", "Upwell structure destroyed"),
                            (
                                "StructuresReinforcementChanged",
                                "Upwell structure reinforcement time changed",
                            ),
                            (
                                "OwnershipTransferred",
                                "Upwell structure ownership transferred",
                            ),
                            ("OrbitalAttacked", "Customs office attacked"),
                            ("OrbitalReinforced", "Customs office reinforced"),
                            ("TowerAlertMsg", "Starbase attacked"),
                            ("TowerResourceAlertMsg", "Starbase fuel alert"),
                            ("TowerRefueledExtra", "Starbase refueled (BETA)"),
                            ("TowerReinforcedExtra", "Starbase reinforced (BETA)"),
                            (
                                "MoonminingExtractionStarted",
                                "Moonmining extraction started",
                            ),
                            ("MoonminingLaserFired", "Moonmining laser fired"),
                            (
                                "MoonminingExtractionCancelled",
                                "Moonmining extraction cancelled",
                            ),
                            (
                                "MoonminingExtractionFinished",
                                "Moonmining extraction finished",
                            ),
                            (
                                "MoonminingAutomaticFracture",
                                "Moonmining automatic fracture triggered",
                            ),
                            (
                                "SovStructureReinforced",
                                "Sovereignty structure reinforced",
                            ),
                            (
                                "SovStructureDestroyed",
                                "Sovereignty structure destroyed",
                            ),
                            (
                                "EntosisCaptureStarted",
                                "Sovereignty entosis capture started",
                            ),
                            (
                                "SovCommandNodeEventStarted",
                                "Sovereignty command node event started",
                            ),
                            (
                                "SovAllClaimAquiredMsg",
                                "Sovereignty claim acknowledgment",
                            ),
                            ("SovAllClaimLostMsg", "Sovereignty lost"),
                            (
                                "AllAnchoringMsg",
                                "Structure anchoring in alliance space",
                            ),
                            ("WarDeclared", "War declared"),
                            ("AllyJoinedWarAggressorMsg", "War ally joined aggressor"),
                            ("AllyJoinedWarAllyMsg", "War ally joined ally"),
                            ("AllyJoinedWarDefenderMsg", "War ally joined defender"),
                            ("WarAdopted", "War adopted"),
                            ("WarInherited", "War inherited"),
                            ("CorpWarSurrenderMsg", "War party surrendered"),
                            ("WarRetractedByConcord", "War retracted by Concord"),
                            (
                                "CorpBecameWarEligible",
                                "War corporation became eligible",
                            ),
                            (
                                "CorpNoLongerWarEligible",
                                "War corporation no longer eligible",
                            ),
                            ("WarSurrenderOfferMsg", "War surrender offered"),
                            ("CorpAppNewMsg", "Character submitted application"),
                            (
                                "CorpAppInvitedMsg",
                                "Character invited to join corporation",
                            ),
                            ("CorpAppRejectCustomMsg", "Corp application rejected"),
                            ("CharAppWithdrawMsg", "Character withdrew application"),
                            ("CharAppAcceptMsg", "Character joins corporation"),
                            ("CharLeftCorpMsg", "Character leaves corporation"),
                            ("BillOutOfMoneyMsg", "Bill out of money"),
                            (
                                "InfrastructureHubBillAboutToExpire",
                                "I-HUB bill about to expire",
                            ),
                            (
                                "IHubDestroyedByBillFailure",
                                "I_HUB destroyed by bill failure",
                            ),
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
                        max_length=1123,
                    ),
                ),
                (
                    "language_code",
                    models.CharField(
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
                        help_text="language of notifications send to this webhook",
                        max_length=8,
                        null=True,
                        verbose_name="language",
                    ),
                ),
                (
                    "is_default",
                    models.BooleanField(
                        default=False,
                        help_text="whether owners have this webhook automatically pre-set when created",
                    ),
                ),
                (
                    "has_default_pings_enabled",
                    models.BooleanField(
                        default=True,
                        help_text="to enable or disable pinging of notifications for this webhook e.g. with @everyone and @here",
                    ),
                ),
                (
                    "ping_groups",
                    models.ManyToManyField(
                        blank=True,
                        default=None,
                        help_text="Groups to be pinged for each notification - ",
                        related_name="+",
                        to="auth.group",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=(structures.webhooks.core.DiscordWebhookMixin, models.Model),
        ),
        migrations.CreateModel(
            name="StructureItem",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        help_text="The Eve item ID", primary_key=True, serialize=False
                    ),
                ),
                ("is_singleton", models.BooleanField()),
                ("last_updated_at", models.DateTimeField(auto_now=True)),
                ("location_flag", models.CharField(max_length=255)),
                ("quantity", models.IntegerField()),
                (
                    "eve_type",
                    models.ForeignKey(
                        help_text="eve type of the item",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="eveuniverse.evetype",
                    ),
                ),
                (
                    "structure",
                    models.ForeignKey(
                        help_text="Structure this item is located in",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="structures.structure",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="structure",
            name="tags",
            field=models.ManyToManyField(
                blank=True,
                default=None,
                help_text="List of tags for this structure. ",
                related_name="structures",
                to="structures.structuretag",
            ),
        ),
        migrations.AddField(
            model_name="structure",
            name="webhooks",
            field=models.ManyToManyField(
                blank=True,
                default=None,
                help_text="Webhooks for sending notifications to. If any webhook is enabled, these will be used instead of the webhooks defined for the respective owner. If no webhook is enabled the owner's setting will be used. ",
                related_name="structures",
                to="structures.webhook",
            ),
        ),
        migrations.CreateModel(
            name="StarbaseDetailFuel",
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
                ("quantity", models.IntegerField()),
                (
                    "detail",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fuels",
                        to="structures.starbasedetail",
                    ),
                ),
                (
                    "eve_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="eveuniverse.evetype",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="starbasedetail",
            name="structure",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="starbase_detail",
                to="structures.structure",
            ),
        ),
        migrations.CreateModel(
            name="PocoDetails",
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
                ("alliance_tax_rate", models.FloatField(default=None, null=True)),
                ("allow_access_with_standings", models.BooleanField()),
                ("allow_alliance_access", models.BooleanField()),
                ("bad_standing_tax_rate", models.FloatField(default=None, null=True)),
                ("corporation_tax_rate", models.FloatField(default=None, null=True)),
                (
                    "excellent_standing_tax_rate",
                    models.FloatField(default=None, null=True),
                ),
                ("good_standing_tax_rate", models.FloatField(default=None, null=True)),
                (
                    "neutral_standing_tax_rate",
                    models.FloatField(default=None, null=True),
                ),
                ("reinforce_exit_end", models.PositiveIntegerField()),
                ("reinforce_exit_start", models.PositiveIntegerField()),
                (
                    "standing_level",
                    models.IntegerField(
                        choices=[
                            (-99, "none"),
                            (-10, "terrible"),
                            (-5, "bad"),
                            (0, "neutral"),
                            (5, "good"),
                            (10, "excellent"),
                        ],
                        default=-99,
                    ),
                ),
                (
                    "terrible_standing_tax_rate",
                    models.FloatField(default=None, null=True),
                ),
                (
                    "structure",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="poco_details",
                        to="structures.structure",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OwnerCharacter",
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
                    "structures_last_used_at",
                    models.DateTimeField(
                        db_index=True,
                        default=None,
                        editable=False,
                        help_text="when this character was last used for syncing structures",
                        null=True,
                    ),
                ),
                (
                    "notifications_last_used_at",
                    models.DateTimeField(
                        db_index=True,
                        default=None,
                        editable=False,
                        help_text="when this character was last used for syncing notifications",
                        null=True,
                    ),
                ),
                (
                    "error_count",
                    models.PositiveIntegerField(
                        default=0,
                        editable=False,
                        help_text="Count of ESI errors which happened with this character.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "character_ownership",
                    models.ForeignKey(
                        help_text="character used for syncing",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="authentication.characterownership",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="characters",
                        to="structures.owner",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="owner",
            name="webhooks",
            field=models.ManyToManyField(
                blank=True,
                default=None,
                help_text="Notifications are sent to these webhooks. ",
                related_name="owners",
                to="structures.webhook",
            ),
        ),
        migrations.CreateModel(
            name="Notification",
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
                    "is_sent",
                    models.BooleanField(
                        default=False,
                        help_text="True when this notification has been forwarded to Discord",
                    ),
                ),
                (
                    "is_timer_added",
                    models.BooleanField(
                        default=False,
                        help_text="True when a timer has been added for this notification",
                        null=True,
                    ),
                ),
                (
                    "notif_type",
                    models.CharField(
                        db_index=True,
                        default="",
                        help_text="type of this notification",
                        max_length=100,
                        verbose_name="type",
                    ),
                ),
                ("notification_id", models.PositiveBigIntegerField(verbose_name="id")),
                (
                    "created",
                    models.DateTimeField(
                        default=None,
                        help_text="Date when this notification was first received from ESI",
                        null=True,
                    ),
                ),
                (
                    "is_read",
                    models.BooleanField(
                        default=None,
                        help_text="True when this notification has read in the eve client",
                        null=True,
                    ),
                ),
                (
                    "last_updated",
                    models.DateTimeField(
                        help_text="Date when this notification has last been updated from ESI"
                    ),
                ),
                (
                    "text",
                    models.TextField(
                        blank=True,
                        default=None,
                        help_text="Notification details in YAML",
                        null=True,
                    ),
                ),
                ("timestamp", models.DateTimeField(db_index=True)),
                (
                    "owner",
                    models.ForeignKey(
                        help_text="Corporation that owns this notification",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.owner",
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="eveuniverse.eveentity",
                    ),
                ),
                (
                    "structures",
                    models.ManyToManyField(
                        help_text="Structures this notification is about (if any)",
                        to="structures.structure",
                    ),
                ),
            ],
            options={
                "verbose_name": "eve notification",
            },
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
        migrations.CreateModel(
            name="GeneratedNotification",
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
                    "is_sent",
                    models.BooleanField(
                        default=False,
                        help_text="True when this notification has been forwarded to Discord",
                    ),
                ),
                (
                    "is_timer_added",
                    models.BooleanField(
                        default=False,
                        help_text="True when a timer has been added for this notification",
                        null=True,
                    ),
                ),
                (
                    "notif_type",
                    models.CharField(
                        db_index=True,
                        default="",
                        help_text="type of this notification",
                        max_length=100,
                        verbose_name="type",
                    ),
                ),
                ("details", models.JSONField(default=dict)),
                ("last_updated", models.DateTimeField(auto_now=True)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        help_text="Corporation that owns this notification",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.owner",
                    ),
                ),
                (
                    "structures",
                    models.ManyToManyField(
                        help_text="Structures this notification is about (if any)",
                        to="structures.structure",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="FuelAlert",
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
                    "hours",
                    models.PositiveIntegerField(
                        db_index=True,
                        help_text="number of hours before fuel expiration this alert was sent",
                    ),
                ),
                (
                    "config",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="structure_fuel_alerts",
                        to="structures.fuelalertconfig",
                    ),
                ),
                (
                    "structure",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="structure_fuel_alerts",
                        to="structures.structure",
                    ),
                ),
            ],
            options={
                "verbose_name": "structure fuel alert",
            },
        ),
        migrations.CreateModel(
            name="StructureService",
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
                    "name",
                    models.CharField(help_text="Name of the service", max_length=100),
                ),
                (
                    "state",
                    models.IntegerField(
                        choices=[(1, "offline"), (2, "online")],
                        help_text="Current state of this service",
                    ),
                ),
                (
                    "structure",
                    models.ForeignKey(
                        help_text="Structure this service is installed to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="services",
                        to="structures.structure",
                    ),
                ),
            ],
            options={
                "unique_together": {("structure", "name")},
            },
        ),
        migrations.AddConstraint(
            model_name="ownercharacter",
            constraint=models.UniqueConstraint(
                fields=("owner", "character_ownership"), name="functional_pk_ownertoken"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="notification",
            unique_together={("notification_id", "owner")},
        ),
        migrations.AddConstraint(
            model_name="fuelalert",
            constraint=models.UniqueConstraint(
                fields=("structure", "config", "hours"), name="functional_pk_fuelalert"
            ),
        ),
    ]
