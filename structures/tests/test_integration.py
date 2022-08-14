import datetime as dt
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils.timezone import now

from app_utils.esi_testing import EsiClientStub, EsiEndpoint

from .. import tasks
from .testdata.factories_2 import (
    OwnerFactory,
    StarbaseFactory,
    StructureFactory,
    StructureWentHighPowerEsiNotificationFactory,
    datetime_to_esi,
)
from .testdata.helpers import load_eveuniverse as structures_load_eveuniverse
from .testdata.load_eveuniverse import load_eveuniverse

MANAGERS_PATH = "structures.managers"
OWNERS_PATH = "structures.models.owners"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(OWNERS_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
@patch(OWNERS_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
@patch(MANAGERS_PATH + ".esi")
@patch(OWNERS_PATH + ".esi")
class TestEnd2EndUpdateAllStructures(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        structures_load_eveuniverse()
        load_eveuniverse()

    def test_should_fetch_new_upwell_structure_from_esi(self, mock_esi_2, mock_esi):
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
        mock_esi_2.client = EsiClientStub.create_from_endpoints(endpoints)
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        structure_id = structure.id
        structure.delete()
        # when
        tasks.update_all_structures.delay()
        # then
        self.assertTrue(owner.structures.filter(id=structure_id).exists())

    def test_should_fetch_new_starbase_from_esi(self, mock_esi_2, mock_esi):
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
        mock_esi_2.client = EsiClientStub.create_from_endpoints(endpoints)
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        structure_id = structure.id
        structure.delete()
        # when
        tasks.update_all_structures.delay()
        # then
        self.assertTrue(owner.structures.filter(id=structure_id).exists())


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch("structures.webhooks.core.dhooks_lite.Webhook.execute", spec=True)
@patch(OWNERS_PATH + ".esi")
class TestEnd2EndFetchAllNotifications(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        structures_load_eveuniverse()
        load_eveuniverse()

    def test_should_fetch_new_notification_from_esi_and_send_them_to_webhook(
        self, mock_esi, mock_execute
    ):
        # given
        structure = StructureFactory()
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
                        StructureWentHighPowerEsiNotificationFactory(
                            structure=structure
                        )
                    ]
                },
            )
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when
        tasks.fetch_all_notifications.delay()
        # then
        embed = mock_execute.call_args[1]["embeds"][0]
        self.assertIn(structure.name, embed.description)
