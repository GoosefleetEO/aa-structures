import datetime as dt
import os
import unittest
from unittest.mock import patch

import yaml

from django.test import TestCase, override_settings
from django.utils.timezone import now
from eveuniverse.models import EveSolarSystem

from app_utils.django import app_labels
from app_utils.esi import EsiStatus
from app_utils.esi_testing import EsiClientStub, EsiEndpoint

from .. import tasks
from ..models import NotificationType, Structure
from .testdata.factories_2 import (
    EveEntityAllianceFactory,
    EveEntityCorporationFactory,
    NotificationFactory,
    OwnerFactory,
    RawNotificationFactory,
    StarbaseFactory,
    StructureFactory,
    WebhookFactory,
    datetime_to_esi,
)
from .testdata.load_eveuniverse import load_eveuniverse

if "structuretimers" in app_labels():
    from structuretimers.models import Timer as StructureTimer
else:
    StructureTimer = None

if "timerboard" in app_labels():
    from allianceauth.timerboard.models import Timer as AuthTimer
else:
    AuthTimer = None

MANAGERS_PATH = "structures.managers"
OWNERS_PATH = "structures.models.owners"
NOTIFICATIONS_PATH = "structures.models.notifications"
TASKS_PATH = "structures.tasks"


@unittest.skipIf(
    os.environ.get("TOX_IS_ACTIVE"), reason="Test does not run with tox"
)  # TODO: Fix tox issue
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(OWNERS_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
@patch(OWNERS_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
@patch("structures.webhooks.core.dhooks_lite.Webhook.execute", spec=True)
@patch(TASKS_PATH + ".fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(MANAGERS_PATH + ".esi")
@patch(OWNERS_PATH + ".esi")
class TestTasks(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_fetch_new_upwell_structure_from_esi(
        self, mock_esi_2, mock_esi, mock_execute
    ):
        # given
        owner = OwnerFactory()
        structure = StructureFactory(owner=owner)
        corporation_id = owner.corporation.corporation_id
        endpoints = [
            EsiEndpoint(
                "Assets",
                "get_corporations_corporation_id_assets",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_names",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_locations",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_starbases",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_structures",
                "corporation_id",
                needs_token=True,
                data={
                    str(corporation_id): [
                        {
                            "corporation_id": corporation_id,
                            "fuel_expires": datetime_to_esi(
                                now() + dt.timedelta(days=3)
                            ),
                            "next_reinforce_apply": None,
                            "next_reinforce_hour": None,
                            "profile_id": 101853,
                            "reinforce_hour": 18,
                            "services": [{"name": "Clone Bay", "state": "online"}],
                            "state": "shield_vulnerable",
                            "state_timer_end": None,
                            "state_timer_start": None,
                            "structure_id": structure.id,
                            "system_id": structure.eve_solar_system.id,
                            "type_id": structure.eve_type.id,
                            "unanchors_at": None,
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Planetary_Interaction",
                "get_corporations_corporation_id_customs_offices",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Sovereignty",
                "get_sovereignty_map",
                needs_token=False,
                data=[],
            ),
            EsiEndpoint(
                "Universe",
                "get_universe_structures_structure_id",
                "structure_id",
                needs_token=True,
                data={
                    str(structure.id): {
                        "corporation_id": corporation_id,
                        "name": f"{structure.eve_solar_system} - {structure.name}",
                        "position": {
                            "x": 55028384780.0,
                            "y": 7310316270.0,
                            "z": -163686684205.0,
                        },
                        "solar_system_id": structure.eve_solar_system.id,
                        "type_id": structure.eve_type.id,
                    }
                },
            ),
        ]
        mock_esi.client = mock_esi_2.client = EsiClientStub.create_from_endpoints(
            endpoints
        )
        structure_id = structure.id
        structure.delete()
        # when
        tasks.update_all_structures.delay()
        # then
        self.assertTrue(owner.structures.filter(id=structure_id).exists())

    def test_should_fetch_new_starbase_from_esi(
        self, mock_esi_2, mock_esi, mock_execute
    ):
        # given
        owner = OwnerFactory()
        structure = StarbaseFactory(owner=owner)
        corporation_id = owner.corporation.corporation_id
        endpoints = [
            EsiEndpoint(
                "Assets",
                "get_corporations_corporation_id_assets",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_names",
                "corporation_id",
                needs_token=True,
                data={
                    str(corporation_id): [
                        {"item_id": structure.id, "name": structure.name}
                    ]
                },
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_locations",
                "corporation_id",
                needs_token=True,
                data={
                    str(corporation_id): [
                        {
                            "item_id": structure.id,
                            "position": {"x": 1.2, "y": 2.3, "z": -3.4},
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_starbases",
                "corporation_id",
                needs_token=True,
                data={
                    str(corporation_id): [
                        {
                            "moon_id": structure.eve_moon.id,
                            "starbase_id": structure.id,
                            "state": "online",
                            "system_id": structure.eve_solar_system.id,
                            "type_id": structure.eve_type.id,
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_starbases_starbase_id",
                ("corporation_id", "starbase_id"),
                needs_token=True,
                data={
                    str(corporation_id): {
                        str(structure.id): {
                            "allow_alliance_members": True,
                            "allow_corporation_members": True,
                            "anchor": "config_starbase_equipment_role",
                            "attack_if_at_war": False,
                            "attack_if_other_security_status_dropping": False,
                            "fuel_bay_take": "config_starbase_equipment_role",
                            "fuel_bay_view": "starbase_fuel_technician_role",
                            "fuels": [
                                {"quantity": 960, "type_id": 4051},
                                {"quantity": 11678, "type_id": 16275},
                            ],
                            "offline": "config_starbase_equipment_role",
                            "online": "config_starbase_equipment_role",
                            "unanchor": "config_starbase_equipment_role",
                            "use_alliance_standings": True,
                        }
                    }
                },
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_structures",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Planetary_Interaction",
                "get_corporations_corporation_id_customs_offices",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Sovereignty",
                "get_sovereignty_map",
                needs_token=False,
                data=[],
            ),
            EsiEndpoint(
                "Universe",
                "get_universe_structures_structure_id",
                "structure_id",
                needs_token=True,
                data={},
            ),
        ]
        mock_esi.client = mock_esi_2.client = EsiClientStub.create_from_endpoints(
            endpoints
        )
        structure_id = structure.id
        structure.delete()
        # when
        tasks.update_all_structures.delay()
        # then
        self.assertTrue(owner.structures.filter(id=structure_id).exists())

    def test_should_send_notification_and_create_timers_for_reinforced_starbase(
        self, mock_esi_2, mock_esi, mock_execute
    ):
        # given
        webhook = WebhookFactory(
            notification_types=[NotificationType.TOWER_REINFORCED_EXTRA]
        )
        owner = OwnerFactory(webhooks=[webhook])
        structure = StarbaseFactory(owner=owner, state=Structure.State.POS_REINFORCED)
        eve_character = owner.characters.first().character_ownership.character
        corporation_id = owner.corporation.corporation_id
        endpoints = [
            EsiEndpoint(
                "Assets",
                "get_corporations_corporation_id_assets",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_names",
                "corporation_id",
                needs_token=True,
                data={
                    str(corporation_id): [
                        {"item_id": structure.id, "name": structure.name}
                    ]
                },
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_locations",
                "corporation_id",
                needs_token=True,
                data={
                    str(corporation_id): [
                        {
                            "item_id": structure.id,
                            "position": {"x": 1.2, "y": 2.3, "z": -3.4},
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Character",
                "get_characters_character_id_notifications",
                "character_id",
                needs_token=True,
                data={str(eve_character.character_id): []},
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_starbases",
                "corporation_id",
                needs_token=True,
                data={
                    str(corporation_id): [
                        {
                            "moon_id": structure.eve_moon.id,
                            "starbase_id": structure.id,
                            "state": "reinforced",
                            "system_id": structure.eve_solar_system.id,
                            "type_id": structure.eve_type.id,
                            "reinforced_until": datetime_to_esi(
                                now() + dt.timedelta(days=3)
                            ),
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_starbases_starbase_id",
                ("corporation_id", "starbase_id"),
                needs_token=True,
                data={
                    str(corporation_id): {
                        str(structure.id): {
                            "allow_alliance_members": True,
                            "allow_corporation_members": True,
                            "anchor": "config_starbase_equipment_role",
                            "attack_if_at_war": False,
                            "attack_if_other_security_status_dropping": False,
                            "fuel_bay_take": "config_starbase_equipment_role",
                            "fuel_bay_view": "starbase_fuel_technician_role",
                            "fuels": [
                                {"quantity": 960, "type_id": 4051},
                                {"quantity": 11678, "type_id": 16275},
                            ],
                            "offline": "config_starbase_equipment_role",
                            "online": "config_starbase_equipment_role",
                            "unanchor": "config_starbase_equipment_role",
                            "use_alliance_standings": True,
                        }
                    }
                },
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_structures",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Planetary_Interaction",
                "get_corporations_corporation_id_customs_offices",
                "corporation_id",
                needs_token=True,
                data={str(corporation_id): []},
            ),
            EsiEndpoint(
                "Sovereignty",
                "get_sovereignty_map",
                needs_token=False,
                data=[],
            ),
            EsiEndpoint(
                "Universe",
                "get_universe_structures_structure_id",
                "structure_id",
                needs_token=True,
                data={},
            ),
        ]
        mock_esi.client = mock_esi_2.client = EsiClientStub.create_from_endpoints(
            endpoints
        )
        structure.delete()
        # when
        tasks.update_all_structures.delay()
        tasks.fetch_all_notifications.delay()
        # then
        self.assertTrue(mock_execute.called)
        embed = mock_execute.call_args[1]["embeds"][0]
        self.assertIn(structure.name, embed.description)

        if StructureTimer:
            self.assertTrue(StructureTimer.objects.exists())

        if AuthTimer:
            self.assertTrue(AuthTimer.objects.exists())

    def test_should_fetch_and_send_notification_when_enabled_for_webhook(
        self, mock_esi_2, mock_esi, mock_execute
    ):
        # given
        webhook = WebhookFactory(
            notification_types=[NotificationType.WAR_CORPORATION_BECAME_ELIGIBLE]
        )
        owner = OwnerFactory(webhooks=[webhook], is_alliance_main=True)
        eve_character = owner.characters.first().character_ownership.character
        # corporation_id = owner.corporation.corporation_id
        notif = RawNotificationFactory()
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_notifications",
                "character_id",
                needs_token=True,
                data={
                    str(eve_character.character_id): [notif],
                },
            ),
        ]
        mock_esi.client = mock_esi_2.client = EsiClientStub.create_from_endpoints(
            endpoints
        )
        # when
        tasks.fetch_all_notifications.delay()
        # then
        self.assertTrue(mock_execute.called)
        embed = mock_execute.call_args[1]["embeds"][0]
        self.assertIn("now eligible", embed.description)

    def test_should_fetch_and_send_notification_when_enabled_for_webhook_all_anchoring(
        self, mock_esi_2, mock_esi, mock_execute
    ):
        # given
        webhook = WebhookFactory(
            notification_types=[NotificationType.SOV_ALL_ANCHORING_MSG]
        )
        owner = OwnerFactory(webhooks=[webhook], is_alliance_main=False)
        eve_character = owner.characters.first().character_ownership.character
        alliance = EveEntityAllianceFactory(
            id=owner.corporation.alliance_id,
            name=owner.corporation.alliance.alliance_name,
        )
        corporation = EveEntityCorporationFactory(
            id=owner.corporation.corporation_id, name=owner.corporation.corporation_name
        )
        starbase = StarbaseFactory(owner=owner)
        notif = RawNotificationFactory(
            type="AllAnchoringMsg",
            sender=corporation,
            data={
                "allianceID": alliance.id,
                "corpID": corporation.id,
                "corpsPresent": [{"allianceID": alliance.id, "corpID": corporation.id}],
                "moonID": starbase.eve_moon.id,
                "solarSystemID": starbase.eve_solar_system.id,
                "towers": [
                    {"moonID": starbase.eve_moon.id, "typeID": starbase.eve_type.id}
                ],
                "typeID": starbase.eve_type.id,
            },
        )
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_notifications",
                "character_id",
                needs_token=True,
                data={
                    str(eve_character.character_id): [notif],
                },
            ),
        ]
        mock_esi.client = mock_esi_2.client = EsiClientStub.create_from_endpoints(
            endpoints
        )
        # when
        tasks.fetch_all_notifications.delay()
        # then
        self.assertTrue(mock_execute.called)
        embed = mock_execute.call_args[1]["embeds"][0]
        self.assertIn("has anchored in", embed.description)

    @patch(NOTIFICATIONS_PATH + ".STRUCTURES_ADD_TIMERS", True)
    def test_should_fetch_new_notification_from_esi_and_send_to_webhook_and_create_timers(
        self, mock_esi_2, mock_esi, mock_execute
    ):
        # given
        sender = EveEntityCorporationFactory()
        structure = StructureFactory(
            eve_solar_system=EveSolarSystem.objects.get(name="Amamake")
        )
        owner = structure.owner
        eve_character = owner.characters.first().character_ownership.character
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_notifications",
                "character_id",
                needs_token=True,
                data={
                    str(eve_character.character_id): [
                        {
                            "notification_id": 1,
                            "is_read": False,
                            "sender_id": sender.id,
                            "sender_type": "corporation",
                            "text": yaml.dump(
                                {
                                    "solarsystemID": structure.eve_solar_system.id,
                                    "structureID": structure.id,
                                    "structureShowInfoData": [
                                        "showinfo",
                                        structure.eve_type.id,
                                        structure.id,
                                    ],
                                    "structureTypeID": structure.eve_type.id,
                                    "timeLeft": 3432362784823,
                                    "timestamp": 132977978640000000,
                                    "vulnerableTime": 9000000000,
                                }
                            ),
                            "timestamp": datetime_to_esi(now()),
                            "type": "StructureLostShields",
                        }
                    ]
                },
            )
        ]
        mock_esi.client = mock_esi_2.client = EsiClientStub.create_from_endpoints(
            endpoints
        )
        # when
        tasks.fetch_all_notifications.delay()
        # then
        self.assertTrue(mock_execute.called)
        embed = mock_execute.call_args[1]["embeds"][0]
        self.assertIn(structure.name, embed.description)

        if StructureTimer:
            obj = StructureTimer.objects.first()
            self.assertEqual(obj.eve_solar_system.id, structure.eve_solar_system.id)

        if AuthTimer:
            obj = AuthTimer.objects.first()
            self.assertEqual(obj.system, structure.eve_solar_system.name)

    @patch(NOTIFICATIONS_PATH + ".STRUCTURES_ADD_TIMERS", False)
    def test_should_send_selected_notif_types_only(
        self, mock_esi_2, mock_esi, mock_webhook_execute
    ):
        # given
        webhook = WebhookFactory(
            notification_types=[
                NotificationType.SOV_STRUCTURE_REINFORCED,
                NotificationType.SOV_STRUCTURE_DESTROYED,
                NotificationType.SOV_ALL_CLAIM_ACQUIRED_MSG,
                NotificationType.SOV_ALL_CLAIM_LOST_MSG,
            ]
        )
        owner = OwnerFactory(webhooks=[webhook], is_alliance_main=True)
        NotificationFactory(
            owner=owner, notif_type=NotificationType.STRUCTURE_DESTROYED
        )
        NotificationFactory(
            owner=owner,
            notif_type=NotificationType.SOV_STRUCTURE_DESTROYED,
            text_from_dict={"solarSystemID": 30000474, "structureTypeID": 32226},
        )
        # when
        tasks.process_notifications_for_owner.delay(owner_pk=owner.pk)
        # then
        self.assertTrue(mock_webhook_execute.called)
        embeds = mock_webhook_execute.call_args[1]["embeds"]
        self.assertEqual(len(embeds), 1)
        embed = embeds[0]
        self.assertIn("Territorial Claim Unit", embed.title)
