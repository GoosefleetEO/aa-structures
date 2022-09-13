import datetime as dt
from unittest.mock import patch

from django.utils.timezone import now, utc
from eveuniverse.models import EvePlanet

from app_utils.esi_testing import EsiClientStub, EsiEndpoint
from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from ...models import (
    FuelAlertConfig,
    NotificationType,
    Owner,
    PocoDetails,
    StarbaseDetail,
    Structure,
    StructureService,
    StructureTag,
    Webhook,
)
from .. import to_json
from ..testdata.factories import (
    create_owner_from_user,
    create_poco,
    create_starbase,
    create_structure_service,
    create_upwell_structure,
)
from ..testdata.helpers import load_entities
from ..testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "structures.models.owners"


@patch(MODULE_PATH + ".esi")
class TestUpdateStructuresEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # given (global)
        load_eveuniverse()
        load_entities()
        cls.user, _ = create_user_from_evecharacter(
            1001,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        Webhook.objects.all().delete()
        cls.endpoints = [
            EsiEndpoint(
                "Assets",
                "get_corporations_corporation_id_assets",
                "corporation_id",
                needs_token=True,
                data={
                    "2001": [
                        {
                            "is_singleton": False,
                            "item_id": 1300000001001,
                            "location_flag": "QuantumCoreRoom",
                            "location_id": 1000000000001,
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": 56201,
                        },
                        {
                            "is_singleton": True,
                            "item_id": 1300000001002,
                            "location_flag": "ServiceSlot0",
                            "location_id": 1000000000001,
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": 35894,
                        },
                        {
                            "is_singleton": True,
                            "item_id": 1300000002001,
                            "location_flag": "ServiceSlot0",
                            "location_id": 1000000000002,
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": 35894,
                        },
                    ],
                    "2102": [
                        {
                            "is_singleton": False,
                            "item_id": 1300000003001,
                            "location_flag": "StructureFuel",
                            "location_id": 1000000000004,
                            "location_type": "item",
                            "quantity": 5000,
                            "type_id": 16273,
                        }
                    ],
                },
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_locations",
                "corporation_id",
                needs_token=True,
                data={
                    "2001": [
                        {
                            "item_id": 1200000000003,
                            "position": {"x": 1.2, "y": 2.3, "z": -3.4},
                        },
                        {
                            "item_id": 1200000000004,
                            "position": {"x": 5.2, "y": 6.3, "z": -7.4},
                        },
                        {
                            "item_id": 1200000000005,
                            "position": {"x": 1.2, "y": 6.3, "z": -7.4},
                        },
                        {
                            "item_id": 1200000000006,
                            "position": {"x": 41.2, "y": 26.3, "z": -47.4},
                        },
                        {
                            "item_id": 1300000000001,
                            "position": {"x": 40.2, "y": 27.3, "z": -19.4},
                        },
                    ]
                },
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_names",
                "corporation_id",
                needs_token=True,
                data={
                    "2001": [
                        {
                            "item_id": 1200000000003,
                            "name": "Customs Office (Amamake V)",
                        },
                        {
                            "item_id": 1200000000004,
                            "name": "Customs Office (1-PGSG VI)",
                        },
                        {
                            "item_id": 1200000000005,
                            "name": "Customs Office (1-PGSG VII)",
                        },
                        {
                            "item_id": 1200000000006,
                            "name": '<localized hint="Customs Office">Customs Office*</localized> (1-PGSG VIII)',
                        },
                        {"item_id": 1300000000001, "name": "Home Sweat Home"},
                        {"item_id": 1300000000002, "name": "Bat cave"},
                        {"item_id": 1300000000003, "name": "Panic Room"},
                    ]
                },
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_structures",
                "corporation_id",
                needs_token=True,
                data={
                    "2001": [
                        {
                            "corporation_id": 2001,
                            "fuel_expires": dt.datetime(2020, 3, 5, 5, tzinfo=utc),
                            "next_reinforce_apply": None,
                            "next_reinforce_hour": None,
                            "profile_id": 52436,
                            "reinforce_hour": 19,
                            "services": [
                                {"name": "Reprocessing", "state": "online"},
                                {"name": "Moon Drilling", "state": "online"},
                            ],
                            "state": "shield_vulnerable",
                            "state_timer_end": None,
                            "state_timer_start": None,
                            "structure_id": 1000000000002,
                            "system_id": 30002537,
                            "type_id": 35835,
                            "unanchors_at": None,
                        },
                        {
                            "corporation_id": 2001,
                            "fuel_expires": dt.datetime(2020, 3, 5, 5, tzinfo=utc),
                            "next_reinforce_apply": None,
                            "next_reinforce_hour": None,
                            "profile_id": 101853,
                            "reinforce_hour": 18,
                            "services": [
                                {"name": "Clone Bay", "state": "online"},
                                {"name": "Market Hub", "state": "offline"},
                            ],
                            "state": "shield_vulnerable",
                            "state_timer_end": dt.datetime(2020, 4, 5, 7, tzinfo=utc),
                            "state_timer_start": dt.datetime(
                                2020, 4, 5, 6, 30, tzinfo=utc
                            ),
                            "structure_id": 1000000000001,
                            "system_id": 30002537,
                            "type_id": 35832,
                            "unanchors_at": dt.datetime(2020, 5, 5, 6, 30, tzinfo=utc),
                        },
                        {
                            "corporation_id": 2001,
                            "fuel_expires": None,
                            "next_reinforce_apply": None,
                            "next_reinforce_hour": None,
                            "profile_id": 101853,
                            "reinforce_hour": 18,
                            "services": None,
                            "state": "shield_vulnerable",
                            "state_timer_end": None,
                            "state_timer_start": None,
                            "structure_id": 1000000000003,
                            "system_id": 30000476,
                            "type_id": 35832,
                            "unanchors_at": None,
                        },
                    ],
                    "2005": [],
                },
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_starbases",
                "corporation_id",
                needs_token=True,
                data={
                    "2001": [
                        {
                            "moon_id": 40161465,
                            "starbase_id": 1300000000001,
                            "state": "online",
                            "system_id": 30002537,
                            "type_id": 16213,
                            "reinforced_until": dt.datetime(2020, 4, 5, 7, tzinfo=utc),
                        },
                        {
                            "moon_id": 40161466,
                            "starbase_id": 1300000000002,
                            "state": "offline",
                            "system_id": 30002537,
                            "type_id": 20061,
                            "unanchors_at": dt.datetime(2020, 5, 5, 7, tzinfo=utc),
                        },
                        {
                            "moon_id": 40029527,
                            "reinforced_until": dt.datetime(2020, 1, 2, 3, tzinfo=utc),
                            "starbase_id": 1300000000003,
                            "state": "reinforced",
                            "system_id": 30000474,
                            "type_id": 20062,
                        },
                    ]
                },
            ),
            EsiEndpoint(
                "Corporation",
                "get_corporations_corporation_id_starbases_starbase_id",
                ("corporation_id", "starbase_id"),
                needs_token=True,
                data={
                    "2001": {
                        "1300000000001": {
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
                        },
                        "1300000000002": {
                            "allow_alliance_members": True,
                            "allow_corporation_members": True,
                            "anchor": "config_starbase_equipment_role",
                            "attack_if_at_war": False,
                            "attack_if_other_security_status_dropping": False,
                            "fuel_bay_take": "config_starbase_equipment_role",
                            "fuels": [
                                {"quantity": 5, "type_id": 4051},
                                {"quantity": 11678, "type_id": 16275},
                            ],
                            "fuel_bay_view": "starbase_fuel_technician_role",
                            "offline": "config_starbase_equipment_role",
                            "online": "config_starbase_equipment_role",
                            "unanchor": "config_starbase_equipment_role",
                            "use_alliance_standings": True,
                        },
                        "1300000000003": {
                            "allow_alliance_members": True,
                            "allow_corporation_members": True,
                            "anchor": "config_starbase_equipment_role",
                            "attack_if_at_war": False,
                            "attack_if_other_security_status_dropping": False,
                            "fuel_bay_take": "config_starbase_equipment_role",
                            "fuel_bay_view": "starbase_fuel_technician_role",
                            "fuels": [
                                {"quantity": 1000, "type_id": 4051},
                                {"quantity": 11678, "type_id": 16275},
                            ],
                            "offline": "config_starbase_equipment_role",
                            "online": "config_starbase_equipment_role",
                            "unanchor": "config_starbase_equipment_role",
                            "use_alliance_standings": True,
                        },
                    }
                },
            ),
            EsiEndpoint(
                "Planetary_Interaction",
                "get_corporations_corporation_id_customs_offices",
                "corporation_id",
                needs_token=True,
                data={
                    "2001": [
                        {
                            "alliance_tax_rate": 0.02,
                            "allow_access_with_standings": True,
                            "allow_alliance_access": True,
                            "bad_standing_tax_rate": 0.3,
                            "corporation_tax_rate": 0.02,
                            "excellent_standing_tax_rate": 0.02,
                            "good_standing_tax_rate": 0.02,
                            "neutral_standing_tax_rate": 0.02,
                            "office_id": 1200000000003,
                            "reinforce_exit_end": 21,
                            "reinforce_exit_start": 19,
                            "standing_level": "terrible",
                            "system_id": 30002537,
                            "terrible_standing_tax_rate": 0.5,
                        },
                        {
                            "alliance_tax_rate": 0.02,
                            "allow_access_with_standings": True,
                            "allow_alliance_access": True,
                            "bad_standing_tax_rate": 0.02,
                            "corporation_tax_rate": 0.02,
                            "excellent_standing_tax_rate": 0.02,
                            "good_standing_tax_rate": 0.02,
                            "neutral_standing_tax_rate": 0.02,
                            "office_id": 1200000000004,
                            "reinforce_exit_end": 21,
                            "reinforce_exit_start": 19,
                            "standing_level": "terrible",
                            "system_id": 30000474,
                            "terrible_standing_tax_rate": 0.02,
                        },
                        {
                            "alliance_tax_rate": 0.02,
                            "allow_access_with_standings": True,
                            "allow_alliance_access": True,
                            "bad_standing_tax_rate": 0.02,
                            "corporation_tax_rate": 0.02,
                            "excellent_standing_tax_rate": 0.02,
                            "good_standing_tax_rate": 0.02,
                            "neutral_standing_tax_rate": 0.02,
                            "office_id": 1200000000005,
                            "reinforce_exit_end": 21,
                            "reinforce_exit_start": 19,
                            "standing_level": "terrible",
                            "system_id": 30000474,
                            "terrible_standing_tax_rate": 0.02,
                        },
                        {
                            "alliance_tax_rate": 0.02,
                            "allow_access_with_standings": True,
                            "allow_alliance_access": True,
                            "bad_standing_tax_rate": 0.02,
                            "corporation_tax_rate": 0.02,
                            "excellent_standing_tax_rate": 0.02,
                            "good_standing_tax_rate": 0.02,
                            "neutral_standing_tax_rate": 0.02,
                            "office_id": 1200000000006,
                            "reinforce_exit_end": 21,
                            "reinforce_exit_start": 19,
                            "standing_level": "terrible",
                            "system_id": 30000474,
                            "terrible_standing_tax_rate": 0.02,
                        },
                        {
                            "alliance_tax_rate": 0.02,
                            "allow_access_with_standings": True,
                            "allow_alliance_access": True,
                            "bad_standing_tax_rate": 0.02,
                            "corporation_tax_rate": 0.02,
                            "excellent_standing_tax_rate": 0.02,
                            "good_standing_tax_rate": 0.02,
                            "neutral_standing_tax_rate": 0.02,
                            "office_id": 1200000000099,
                            "reinforce_exit_end": 21,
                            "reinforce_exit_start": 19,
                            "standing_level": "terrible",
                            "system_id": 30000474,
                            "terrible_standing_tax_rate": 0.02,
                        },
                    ]
                },
            ),
            EsiEndpoint(
                "Universe",
                "get_universe_structures_structure_id",
                "structure_id",
                needs_token=True,
                data={
                    "1000000000001": {
                        "corporation_id": 2001,
                        "name": "Amamake - Test Structure Alpha",
                        "position": {
                            "x": 55028384780.0,
                            "y": 7310316270.0,
                            "z": -163686684205.0,
                        },
                        "solar_system_id": 30002537,
                        "type_id": 35832,
                    },
                    "1000000000002": {
                        "corporation_id": 2001,
                        "name": "Amamake - Test Structure Bravo",
                        "position": {
                            "x": -2518743930339.066,
                            "y": -130157937025.56424,
                            "z": -442026427345.6355,
                        },
                        "solar_system_id": 30002537,
                        "type_id": 35835,
                    },
                    "1000000000003": {
                        "corporation_id": 2001,
                        "name": "Amamake - Test Structure Charlie",
                        "position": {
                            "x": -2518743930339.066,
                            "y": -130157937025.56424,
                            "z": -442026427345.6355,
                        },
                        "solar_system_id": 30000476,
                        "type_id": 35832,
                    },
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(cls.endpoints)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_can_sync_upwell_structures(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)
        self.assertAlmostEqual(
            owner.structures_last_update_at, now(), delta=dt.timedelta(seconds=30)
        )

        # must contain all expected structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

        # verify attributes for structure
        structure = Structure.objects.get(id=1000000000001)
        self.assertEqual(structure.name, "Test Structure Alpha")
        self.assertEqual(structure.position_x, 55028384780.0)
        self.assertEqual(structure.position_y, 7310316270.0)
        self.assertEqual(structure.position_z, -163686684205.0)
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(structure.eve_type_id, 35832)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.state, Structure.State.SHIELD_VULNERABLE)
        self.assertEqual(structure.reinforce_hour, 18)
        self.assertEqual(
            structure.fuel_expires_at, dt.datetime(2020, 3, 5, 5, 0, 0, tzinfo=utc)
        )
        self.assertEqual(
            structure.state_timer_start, dt.datetime(2020, 4, 5, 6, 30, 0, tzinfo=utc)
        )
        self.assertEqual(
            structure.state_timer_end, dt.datetime(2020, 4, 5, 7, 0, 0, tzinfo=utc)
        )
        self.assertEqual(
            structure.unanchors_at, dt.datetime(2020, 5, 5, 6, 30, 0, tzinfo=utc)
        )

        # must have created services with localizations
        # structure 1000000000001
        expected = {
            to_json(
                {
                    "name": "Clone Bay",
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": "Clone Bay_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
            to_json(
                {
                    "name": "Market Hub",
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": "Market Hub_zh",
                    "state": StructureService.State.OFFLINE,
                }
            ),
        }
        structure = Structure.objects.get(id=1000000000001)
        services = {
            to_json(
                {
                    "name": x.name,
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": x.name_zh,
                    "state": x.state,
                }
            )
            for x in structure.services.all()
        }
        self.assertEqual(services, expected)

        # must have created services with localizations
        # structure 1000000000002
        expected = {
            to_json(
                {
                    "name": "Reprocessing",
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": "Reprocessing_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
            to_json(
                {
                    "name": "Moon Drilling",
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": "Moon Drilling_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
        }
        structure = Structure.objects.get(id=1000000000002)
        services = {
            to_json(
                {
                    "name": x.name,
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": x.name_zh,
                    "state": x.state,
                }
            )
            for x in structure.services.all()
        }
        self.assertEqual(services, expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_sync_pocos(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()

        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)

        # must contain all expected structures
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1200000000099,
        }
        self.assertSetEqual(owner.structures.ids(), expected)
        self.assertSetEqual(
            set(PocoDetails.objects.values_list("structure_id", flat=True)),
            {1200000000003, 1200000000004, 1200000000005, 1200000000006, 1200000000099},
        )

        # verify attributes for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "Planet (Barren)")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 2233)
        self.assertEqual(structure.reinforce_hour, 20)
        self.assertEqual(structure.state, Structure.State.UNKNOWN)
        self.assertEqual(structure.eve_planet_id, 40161472)

        # verify attributes for POCO details
        details = structure.poco_details
        self.assertEqual(details.alliance_tax_rate, 0.02)
        self.assertTrue(details.allow_access_with_standings)
        self.assertTrue(details.allow_alliance_access)
        self.assertEqual(details.bad_standing_tax_rate, 0.3)
        self.assertEqual(details.corporation_tax_rate, 0.02)
        self.assertEqual(details.excellent_standing_tax_rate, 0.02)
        self.assertEqual(details.good_standing_tax_rate, 0.02)
        self.assertEqual(details.neutral_standing_tax_rate, 0.02)
        self.assertEqual(details.reinforce_exit_end, 21)
        self.assertEqual(details.reinforce_exit_start, 19)
        self.assertEqual(details.standing_level, PocoDetails.StandingLevel.TERRIBLE)
        self.assertEqual(details.terrible_standing_tax_rate, 0.5)

        # empty name for POCO with no asset data
        structure = Structure.objects.get(id=1200000000099)
        self.assertEqual(structure.name, "")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_can_sync_starbases(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()

        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)

        # must contain all expected structures
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

        # verify attributes for POS
        structure = Structure.objects.get(id=1300000000001)
        self.assertEqual(structure.name, "Home Sweat Home")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 16213)
        self.assertEqual(structure.state, Structure.State.POS_ONLINE)
        self.assertEqual(structure.eve_moon_id, 40161465)
        self.assertEqual(
            structure.state_timer_end, dt.datetime(2020, 4, 5, 7, 0, 0, tzinfo=utc)
        )
        self.assertAlmostEqual(
            structure.fuel_expires_at,
            now() + dt.timedelta(hours=24),
            delta=dt.timedelta(seconds=30),
        )
        self.assertEqual(structure.position_x, 40.2)
        self.assertEqual(structure.position_y, 27.3)
        self.assertEqual(structure.position_z, -19.4)
        # verify details
        detail = structure.starbase_detail
        self.assertTrue(detail.allow_alliance_members)
        self.assertTrue(detail.allow_corporation_members)
        self.assertEqual(
            detail.anchor_role, StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE
        )
        self.assertFalse(detail.attack_if_at_war)
        self.assertFalse(detail.attack_if_other_security_status_dropping)
        self.assertEqual(
            detail.anchor_role, StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE
        )
        self.assertEqual(
            detail.fuel_bay_take_role,
            StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE,
        )
        self.assertEqual(
            detail.fuel_bay_view_role,
            StarbaseDetail.Role.STARBASE_FUEL_TECHNICIAN_ROLE,
        )
        self.assertEqual(
            detail.offline_role,
            StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE,
        )
        self.assertEqual(
            detail.online_role,
            StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE,
        )
        self.assertEqual(
            detail.unanchor_role,
            StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE,
        )
        self.assertTrue(detail.use_alliance_standings)
        # fuels
        self.assertEqual(detail.fuels.count(), 2)
        self.assertEqual(detail.fuels.get(eve_type_id=4051).quantity, 960)
        self.assertEqual(detail.fuels.get(eve_type_id=16275).quantity, 11678)

        structure = Structure.objects.get(id=1300000000002)
        self.assertEqual(structure.name, "Bat cave")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 20061)
        self.assertEqual(structure.state, Structure.State.POS_OFFLINE)
        self.assertEqual(structure.eve_moon_id, 40161466)
        self.assertEqual(
            structure.unanchors_at, dt.datetime(2020, 5, 5, 7, 0, 0, tzinfo=utc)
        )
        self.assertIsNone(structure.fuel_expires_at)
        self.assertFalse(structure.generatednotification_set.exists())

        structure = Structure.objects.get(id=1300000000003)
        self.assertEqual(structure.name, "Panic Room")
        self.assertEqual(structure.eve_solar_system_id, 30000474)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 20062)
        self.assertEqual(structure.state, Structure.State.POS_REINFORCED)
        self.assertEqual(structure.eve_moon_id, 40029527)
        self.assertAlmostEqual(
            structure.fuel_expires_at,
            now() + dt.timedelta(hours=133, minutes=20),
            delta=dt.timedelta(seconds=30),
        )
        self.assertEqual(
            structure.state_timer_end, dt.datetime(2020, 1, 2, 3, tzinfo=utc)
        )
        self.assertTrue(structure.generatednotification_set.exists())

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    @patch(MODULE_PATH + ".notify", spec=True)
    def test_can_sync_all_structures_and_notify_user(self, mock_notify, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)

        # when
        owner.update_structures_esi(user=self.user)

        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)

        # must contain all expected structures
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1200000000099,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

        # user report has been sent
        self.assertTrue(mock_notify.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_can_handle_owner_without_structures(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        user, _ = create_user_from_evecharacter(
            1005,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner = create_owner_from_user(user)  # corp_ID = 2005
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)
        self.assertSetEqual(owner.structures.ids(), set())

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_break_when_endpoint_for_fetching_upwell_structures_is_down(
        self, mock_esi
    ):
        # given
        new_endpoint = EsiEndpoint(
            "Corporation",
            "get_corporations_corporation_id_structures",
            http_error_code=500,
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = {
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1200000000099,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_break_on_http_error_when_fetching_custom_offices(
        self, mock_esi
    ):
        # given
        new_endpoint = EsiEndpoint(
            "Planetary_Interaction",
            "get_corporations_corporation_id_customs_offices",
            http_error_code=500,
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_break_on_http_error_when_fetching_custom_office_names(
        self, mock_esi
    ):
        # given
        new_endpoint = EsiEndpoint(
            "Assets",
            "post_corporations_corporation_id_assets_names",
            http_error_code=404,
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1200000000099,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_not_break_on_http_error_when_fetching_star_bases(self, mock_esi):
        # given
        new_endpoint = EsiEndpoint(
            "Corporation",
            "get_corporations_corporation_id_starbases",
            http_error_code=500,
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_ESI_DIRECTOR_ERROR_MAX_RETRIES", 3)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(MODULE_PATH + ".notify", spec=True)
    def test_should_mark_error_when_character_not_director_while_updating_starbases(
        self, mock_notify, mock_esi
    ):
        # given
        new_endpoint = EsiEndpoint(
            "Corporation",
            "get_corporations_corporation_id_starbases",
            http_error_code=403,
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        self.assertTrue(mock_notify)
        character = owner.characters.first()
        self.assertEqual(character.error_count, 1)

    @patch(MODULE_PATH + ".STRUCTURES_ESI_DIRECTOR_ERROR_MAX_RETRIES", 3)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(MODULE_PATH + ".notify", spec=True)
    def test_should_remove_character_when_not_director_while_updating_starbases(
        self, mock_notify, mock_esi
    ):
        # given
        new_endpoint = EsiEndpoint(
            "Corporation",
            "get_corporations_corporation_id_starbases",
            http_error_code=403,
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        character = owner.characters.first()
        character.error_count = 3
        character.save()
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        self.assertTrue(mock_notify)
        self.assertEqual(owner.characters.count(), 0)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_update_will_not_break_on_http_error_from_structure_info(self, mock_esi):
        # given
        new_endpoint = EsiEndpoint(
            "Universe", "get_universe_structures_structure_id", http_error_code=500
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.is_structure_sync_fresh)
        structure = Structure.objects.get(id=1000000000002)
        self.assertEqual(structure.name, "(no data)")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(MODULE_PATH + ".Structure.objects.update_or_create_from_dict")
    def test_update_will_not_break_on_http_error_when_creating_structures(
        self, mock_create_structure, mock_esi
    ):
        mock_create_structure.side_effect = OSError
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.is_structure_sync_fresh)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_remove_old_upwell_structures(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000004, name="delete-me")
        # when
        owner.update_structures_esi()
        # then
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_remove_old_pocos(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        create_poco(owner=owner, id=1000000000004, name="delete-me")
        # when
        owner.update_structures_esi()
        # then
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1200000000099,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_remove_old_starbases(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        create_starbase(owner=owner, id=1300000000099, name="delete-me")
        # when
        owner.update_structures_esi()
        # then
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_tags_are_not_modified_by_update(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then

        # should contain the right structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

        # adding tags
        tag_a = StructureTag.objects.get(name="tag_a")
        s = Structure.objects.get(id=1000000000001)
        s.tags.add(tag_a)
        s.save()

        # run update task 2nd time
        owner.update_structures_esi()

        # should still contain alls structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

        # should still contain the tag
        s_new = Structure.objects.get(id=1000000000001)
        self.assertEqual(s_new.tags.get(name="tag_a"), tag_a)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_not_delete_existing_upwell_structures_when_update_failed(
        self, mock_esi
    ):
        # given
        new_endpoint = EsiEndpoint(
            "Corporation",
            "get_corporations_corporation_id_structures",
            http_error_code=500,
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000001)
        create_upwell_structure(owner=owner, id=1000000000002)
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = {1000000000001, 1000000000002}
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_delete_existing_pocos_when_update_failed(self, mock_esi):
        # given
        new_endpoint = EsiEndpoint(
            "Planetary_Interaction",
            "get_corporations_corporation_id_customs_offices",
            http_error_code=500,
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        create_poco(owner=owner, id=1200000000003)
        create_poco(owner=owner, id=1200000000004)
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_not_delete_existing_starbases_when_update_failed(self, mock_esi):
        # given

        new_endpoint = EsiEndpoint(
            "Corporation",
            "get_corporations_corporation_id_starbases",
            http_error_code=500,
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        create_starbase(owner=owner, id=1300000000001)
        create_starbase(owner=owner, id=1300000000002)
        # when
        owner.update_structures_esi()
        # then
        # self.assertFalse(owner.is_structure_sync_fresh)
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_remove_outdated_services(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        structure = create_upwell_structure(owner=owner, id=1000000000002)
        create_structure_service(structure=structure, name="Clone Bay")
        # when
        owner.update_structures_esi()
        # then
        structure.refresh_from_db()
        services = {
            obj.name for obj in StructureService.objects.filter(structure=structure)
        }
        self.assertEqual(services, {"Moon Drilling", "Reprocessing"})

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_have_empty_name_if_not_match_with_planets(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        EvePlanet.objects.all().delete()
        # when
        owner.update_structures_esi()
        # then
        self.assertTrue(owner.is_structure_sync_fresh)
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_define_poco_name_from_planet_type_if_found(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, "Planet (Barren)")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(
        "structures.models.structures.STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", True
    )
    @patch("structures.models.notifications.Webhook.send_message")
    def test_should_send_refueled_notification_when_fuel_level_increased(
        self, mock_send_message, mock_esi
    ):
        # given
        mock_esi.client = self.esi_client_stub
        mock_send_message.return_value = 1
        webhook = Webhook.objects.create(
            name="Webhook 1",
            url="webhook-1",
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA],
            is_active=True,
        )
        owner = create_owner_from_user(self.user)
        owner.webhooks.add(webhook)
        owner.update_structures_esi()
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = dt.datetime(2020, 3, 3, 0, 0, tzinfo=utc)
        structure.save()
        # when
        with patch("structures.models.structures.now") as now:
            now.return_value = dt.datetime(2020, 3, 2, 0, 0, tzinfo=utc)
            owner.update_structures_esi()
        # then
        self.assertTrue(mock_send_message.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(
        "structures.models.structures.STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", True
    )
    @patch("structures.models.notifications.Webhook.send_message")
    def test_should_not_send_refueled_notification_when_fuel_level_unchanged(
        self, mock_send_message, mock_esi
    ):
        # given
        mock_esi.client = self.esi_client_stub
        mock_send_message.side_effect = RuntimeError
        webhook = Webhook.objects.create(
            name="Webhook 1",
            url="webhook-1",
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA],
            is_active=True,
        )
        owner = create_owner_from_user(self.user)
        owner.webhooks.add(webhook)
        with patch("structures.models.structures.now") as now:
            now.return_value = dt.datetime(2020, 3, 2, 0, 0, tzinfo=utc)
            owner.update_structures_esi()
            # when
            owner.update_structures_esi()
        # then
        self.assertFalse(mock_send_message.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch("structures.models.notifications.Webhook.send_message")
    def test_should_remove_outdated_fuel_alerts_when_fuel_level_changed(
        self, mock_send_message, mock_esi
    ):
        # given
        mock_esi.client = self.esi_client_stub
        mock_send_message.return_value = 1
        webhook = Webhook.objects.create(
            name="Webhook 1",
            url="webhook-1",
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA],
            is_active=True,
        )
        owner = create_owner_from_user(self.user)
        owner.webhooks.add(webhook)
        owner.update_structures_esi()
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = dt.datetime(2020, 3, 3, 0, 0, tzinfo=utc)
        structure.save()
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure.structure_fuel_alerts.create(config=config, hours=12)
        # when
        with patch("structures.models.structures.now") as now:
            now.return_value = dt.datetime(2020, 3, 2, 0, 0, tzinfo=utc)
            owner.update_structures_esi()
        # then
        self.assertEqual(structure.structure_fuel_alerts.count(), 0)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_not_break_when_starbase_names_not_found(self, mock_esi):
        # given
        new_endpoint = EsiEndpoint(
            "Assets",
            "post_corporations_corporation_id_assets_names",
            http_error_code=404,
        )
        mock_esi.client = self.esi_client_stub.replace_endpoints([new_endpoint])
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    # @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    # @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    # def test_should_notify_admins_when_service_is_restored(
    #     self, mock_esi_client
    # ):
    #     # given
    #     mock_esi_client.side_effect = esi_mock_client
    #     owner = create_owner_from_user(self.user)
    #     owner.is_structure_sync_fresh = False
    #     owner.save()
    #     # when
    #     owner.update_structures_esi()
    #     # then
    #     owner.refresh_from_db()
    #     self.assertTrue(owner.is_structure_sync_fresh)
