import datetime as dt
from unittest.mock import patch

from django.utils.timezone import now
from eveuniverse.models import EveSolarSystem

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from app_utils.esi_testing import EsiClientStub, EsiEndpoint
from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from structures.models import (
    EveSovereigntyMap,
    NotificationType,
    Owner,
    Structure,
    StructureService,
    StructureTag,
    Webhook,
)

from .testdata.factories import (
    create_eve_sovereignty_map,
    create_owner_from_user,
    create_upwell_structure,
)
from .testdata.factories_2 import OwnerFactory
from .testdata.helpers import create_structures, load_entities
from .testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "structures.managers"
MODULE_PATH_ESI_FETCH = "structures.helpers.esi_fetch"


class TestEveSovereigntyMapManagerUpdateFromEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        endpoints = [
            EsiEndpoint(
                "Sovereignty",
                "get_sovereignty_map",
                data=[
                    {
                        "alliance_id": 3011,
                        "corporation_id": 2011,
                        "system_id": 30000726,
                    },
                    {
                        "alliance_id": 3001,
                        "corporation_id": 2001,
                        "system_id": 30000474,
                        "faction_id": None,
                    },
                    {
                        "alliance_id": 3001,
                        "corporation_id": 2001,
                        "system_id": 30000728,
                        "faction_id": None,
                    },
                    {
                        "alliance_id": None,
                        "corporation_id": None,
                        "system_id": 30000142,
                        "faction_id": None,
                    },
                ],
            )
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(endpoints)

    @patch(MODULE_PATH + ".esi")
    def test_should_create_sov_map_from_scratch(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        # when
        EveSovereigntyMap.objects.update_from_esi()
        # then
        solar_system_ids = EveSovereigntyMap.objects.values_list(
            "solar_system_id", flat=True
        )
        self.assertSetEqual(set(solar_system_ids), {30000726, 30000474, 30000728})

    @patch(MODULE_PATH + ".esi")
    def test_should_update_existing_map(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        create_eve_sovereignty_map(solar_system_id=30000726, alliance_id=3001)
        # when
        EveSovereigntyMap.objects.update_from_esi()
        # then
        solar_system_ids = EveSovereigntyMap.objects.values_list(
            "solar_system_id", flat=True
        )
        self.assertSetEqual(set(solar_system_ids), {30000726, 30000474, 30000728})
        structure = EveSovereigntyMap.objects.get(solar_system_id=30000726)
        self.assertEqual(structure.corporation_id, 2011)
        self.assertEqual(structure.alliance_id, 3011)
        structure = EveSovereigntyMap.objects.get(solar_system_id=30000474)
        self.assertEqual(structure.corporation_id, 2001)
        self.assertEqual(structure.alliance_id, 3001)
        structure = EveSovereigntyMap.objects.get(solar_system_id=30000728)
        self.assertEqual(structure.corporation_id, 2001)
        self.assertEqual(structure.alliance_id, 3001)


class TestEveSovereigntyMapManagerOther(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities([EveCharacter, EveSovereigntyMap])

    def test_sov_alliance_id(self):
        # returns alliance ID for sov system in null
        obj = EveSolarSystem.objects.get(id=30000474)
        self.assertEqual(
            EveSovereigntyMap.objects.solar_system_sov_alliance_id(obj), 3001
        )

        # returns None if there is not sov info
        obj = EveSolarSystem.objects.get(id=30000476)
        self.assertIsNone(EveSovereigntyMap.objects.solar_system_sov_alliance_id(obj))

        # returns None if system is not in Null sec
        obj = EveSolarSystem.objects.get(id=30002537)
        self.assertIsNone(EveSovereigntyMap.objects.solar_system_sov_alliance_id(obj))

    def test_corporation_has_sov(self):
        corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        # Wayne Tech has sov in 1-PG
        eve_solar_system = EveSolarSystem.objects.get(name="1-PGSG")
        self.assertTrue(
            EveSovereigntyMap.objects.corporation_has_sov(eve_solar_system, corporation)
        )

        # Wayne Tech has no sov in A-C5TC
        eve_solar_system = EveSolarSystem.objects.get(name="A-C5TC")
        self.assertFalse(
            EveSovereigntyMap.objects.corporation_has_sov(eve_solar_system, corporation)
        )

        # There can't be any sov outside nullsec
        eve_solar_system = EveSolarSystem.objects.get(name="Amamake")
        self.assertFalse(
            EveSovereigntyMap.objects.corporation_has_sov(eve_solar_system, corporation)
        )


@patch(MODULE_PATH + ".esi")
class TestStructureManagerEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities([EveCharacter])
        user, _ = create_user_from_evecharacter(
            1001,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        cls.owner = create_owner_from_user(user)
        cls.token = cls.owner.fetch_token()
        endpoints = [
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
            )
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(endpoints)

    def test_should_return_object_from_db_if_found(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Universe",
                "get_universe_structures_structure_id",
                "structure_id",
                needs_token=True,
                side_effect=RuntimeError,
            )
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        structure = create_upwell_structure(
            owner=self.owner, id=1000000000001, name="Batcave"
        )
        # when
        structure, created = Structure.objects.get_or_create_esi(
            id=1000000000001, token=self.token
        )
        # then
        self.assertFalse(created)
        self.assertEqual(structure.id, 1000000000001)

    def test_can_create_object_from_esi_if_not_found(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        # when
        structure, created = Structure.objects.get_or_create_esi(
            id=1000000000001, token=self.token
        )
        # then
        self.assertTrue(created)
        self.assertEqual(structure.id, 1000000000001)
        self.assertEqual(structure.name, "Test Structure Alpha")
        self.assertEqual(structure.eve_type_id, 35832)
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.position_x, 55028384780.0)
        self.assertEqual(structure.position_y, 7310316270.0)
        self.assertEqual(structure.position_z, -163686684205.0)

    def test_can_update_object_from_esi(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        structure = create_upwell_structure(
            owner=self.owner, id=1000000000001, name="Batcave"
        )
        # when
        structure, created = Structure.objects.update_or_create_esi(
            id=1000000000001, token=self.token
        )
        # then
        self.assertFalse(created)
        self.assertEqual(structure.id, 1000000000001)
        self.assertEqual(structure.name, "Test Structure Alpha")

    def test_raises_exception_when_create_fails(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Universe",
                "get_universe_structures_structure_id",
                "structure_id",
                needs_token=True,
                side_effect=RuntimeError,
            )
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when/then
        with self.assertRaises(RuntimeError):
            Structure.objects.update_or_create_esi(id=1000000000001, token=self.token)

    def test_raises_exception_when_create_without_token(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        # when
        with self.assertRaises(ValueError):
            Structure.objects.update_or_create_esi(id=987, token=None)


class TestStructureManagerQuerySet(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()

    def test_should_return_ids_as_set(self):
        # when
        ids = Structure.objects.ids()
        # then
        self.assertSetEqual(
            ids,
            {
                1000000000001,
                1000000000002,
                1000000000003,
                1000000000004,
                1200000000003,
                1200000000004,
                1200000000005,
                1200000000006,
                1300000000001,
                1300000000002,
                1300000000003,
            },
        )

    def test_should_filter_upwell_structures(self):
        # when
        result_qs = Structure.objects.filter_upwell_structures()
        # then
        self.assertSetEqual(
            result_qs.ids(),
            {1000000000001, 1000000000002, 1000000000003, 1000000000004},
        )

    def test_should_filter_customs_offices(self):
        # when
        result_qs = Structure.objects.filter_customs_offices()
        # then
        self.assertSetEqual(
            result_qs.ids(),
            {1200000000003, 1200000000004, 1200000000005, 1200000000006},
        )

    def test_should_filter_starbases(self):
        # when
        result_qs = Structure.objects.filter_starbases()
        # then
        self.assertSetEqual(
            result_qs.ids(), {1300000000001, 1300000000002, 1300000000003}
        )


class TestStructureManagerCreateFromDict(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_can_create_full(self):
        load_entities([EveCharacter, EveSovereigntyMap])
        owner = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        structure = {
            "fuel_expires": None,
            "name": "Test Structure Alpha",
            "next_reinforce_apply": None,
            "next_reinforce_hour": None,
            "position": {"x": 55028384780.0, "y": 7310316270.0, "z": -163686684205.0},
            "profile_id": 101853,
            "reinforce_hour": 18,
            "services": [
                {
                    "name": "Clone Bay",
                    "state": "online",
                },
                {
                    "name": "Market Hub",
                    "state": "offline",
                },
            ],
            "state": "shield_vulnerable",
            "state_timer_end": None,
            "state_timer_start": None,
            "structure_id": 1000000000001,
            "system_id": 30002537,
            "type_id": 35832,
            "unanchors_at": None,
        }
        structure, created = Structure.objects.update_or_create_from_dict(
            structure, owner
        )

        # check structure
        self.assertTrue(created)
        self.assertEqual(structure.id, 1000000000001)
        self.assertEqual(structure.name, "Test Structure Alpha")
        self.assertEqual(structure.eve_type_id, 35832)
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(structure.owner, owner)
        self.assertEqual(structure.position_x, 55028384780.0)
        self.assertEqual(structure.position_y, 7310316270.0)
        self.assertEqual(structure.position_z, -163686684205.0)
        self.assertEqual(structure.reinforce_hour, 18)
        self.assertEqual(structure.state, Structure.State.SHIELD_VULNERABLE)
        self.assertAlmostEqual(
            (now() - structure.created_at).total_seconds(), 0, delta=2
        )
        self.assertAlmostEqual(
            (now() - structure.last_updated_at).total_seconds(), 0, delta=2
        )
        self.assertAlmostEqual(
            (now() - structure.last_online_at).total_seconds(), 0, delta=2
        )
        self.assertEqual(structure.services.count(), 2)
        service_1 = structure.services.get(name="Clone Bay")
        self.assertEqual(service_1.state, StructureService.State.ONLINE)
        service_1 = structure.services.get(name="Market Hub")
        self.assertEqual(service_1.state, StructureService.State.OFFLINE)
        # todo: add more content tests

    def test_can_update_full(self):
        create_structures()
        owner = Owner.objects.get(corporation__corporation_id=2001)
        structure = Structure.objects.get(id=1000000000001)
        structure.last_updated_at = now() - dt.timedelta(hours=2)
        structure.save()
        structure = {
            "corporation_id": 2001,
            "fuel_expires": None,
            "name": "Test Structure Alpha Updated",
            "next_reinforce_apply": None,
            "next_reinforce_hour": None,
            "position": {"x": 55028384780.0, "y": 7310316270.0, "z": -163686684205.0},
            "profile_id": 101853,
            "reinforce_hour": 18,
            "services": [
                {
                    "name": "Clone Bay",
                    "state": "online",
                },
                {
                    "name": "Market Hub",
                    "state": "offline",
                },
            ],
            "state": "shield_vulnerable",
            "state_timer_end": None,
            "state_timer_start": None,
            "structure_id": 1000000000001,
            "system_id": 30002537,
            "type_id": 35832,
            "unanchors_at": None,
        }
        structure, created = Structure.objects.update_or_create_from_dict(
            structure, owner
        )

        # check structure
        self.assertFalse(created)
        self.assertEqual(structure.id, 1000000000001)
        self.assertEqual(structure.name, "Test Structure Alpha Updated")
        self.assertEqual(structure.eve_type_id, 35832)
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(structure.owner, owner)
        self.assertEqual(structure.position_x, 55028384780.0)
        self.assertEqual(structure.position_y, 7310316270.0)
        self.assertEqual(structure.position_z, -163686684205.0)
        self.assertEqual(structure.reinforce_hour, 18)
        self.assertEqual(structure.state, Structure.State.SHIELD_VULNERABLE)
        self.assertAlmostEqual(
            (now() - structure.last_updated_at).total_seconds(), 0, delta=2
        )
        self.assertAlmostEqual(
            (now() - structure.last_online_at).total_seconds(), 0, delta=2
        )

    def test_does_not_update_last_online_when_services_are_offline(self):
        create_structures()
        owner = Owner.objects.get(corporation__corporation_id=2001)
        structure = Structure.objects.get(id=1000000000001)
        structure.last_online_at = None
        structure.save()
        structure = {
            "fuel_expires": None,
            "name": "Test Structure Alpha Updated",
            "next_reinforce_apply": None,
            "next_reinforce_hour": None,
            "position": {"x": 55028384780.0, "y": 7310316270.0, "z": -163686684205.0},
            "profile_id": 101853,
            "reinforce_hour": 18,
            "services": [
                {
                    "name": "Clone Bay",
                    "state": "offline",
                },
                {
                    "name": "Market Hub",
                    "state": "offline",
                },
            ],
            "state": "shield_vulnerable",
            "state_timer_end": None,
            "state_timer_start": None,
            "structure_id": 1000000000001,
            "system_id": 30002537,
            "type_id": 35832,
            "unanchors_at": None,
        }
        structure, created = Structure.objects.update_or_create_from_dict(
            structure, owner
        )

        # check structure
        self.assertFalse(created)
        self.assertIsNone(structure.last_online_at)

    def test_can_create_starbase_without_moon(self):
        owner = OwnerFactory()
        structure = {
            "structure_id": 1300000000099,
            "name": "Hidden place",
            "system_id": 30002537,
            "type_id": 16213,
            "moon_id": None,
            "position": {"x": 55028384780.0, "y": 7310316270.0, "z": -163686684205.0},
        }
        structure, created = Structure.objects.update_or_create_from_dict(
            structure, owner
        )

        # check structure
        structure: Structure
        self.assertTrue(created)
        self.assertEqual(structure.id, 1300000000099)
        self.assertEqual(structure.eve_type_id, 16213)
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(structure.owner, owner)
        self.assertEqual(structure.position_x, 55028384780.0)
        self.assertEqual(structure.position_y, 7310316270.0)
        self.assertEqual(structure.position_z, -163686684205.0)
        self.assertEqual(structure.state, Structure.State.UNKNOWN)


class TestStructureTagManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities([EveSovereigntyMap])

    def test_can_get_space_type_tag_that_exists(self):
        solar_system = EveSolarSystem.objects.get(id=30002537)
        tag = StructureTag.objects.create(name=StructureTag.NAME_LOWSEC_TAG)
        structure, created = StructureTag.objects.get_or_create_for_space_type(
            solar_system
        )
        self.assertFalse(created)
        self.assertEqual(structure, tag)

    def test_can_get_space_type_tag_that_does_not_exist(self):
        solar_system = EveSolarSystem.objects.get(id=30002537)
        structure, created = StructureTag.objects.get_or_create_for_space_type(
            solar_system
        )
        self.assertTrue(created)
        self.assertEqual(structure.name, StructureTag.NAME_LOWSEC_TAG)
        self.assertEqual(structure.style, StructureTag.Style.ORANGE)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)

    def test_can_update_space_type_tag(self):
        solar_system = EveSolarSystem.objects.get(id=30002537)
        StructureTag.objects.create(
            name=StructureTag.NAME_LOWSEC_TAG,
            style=StructureTag.Style.GREEN,
            is_user_managed=True,
            is_default=True,
            order=100,
        )
        structure, created = StructureTag.objects.update_or_create_for_space_type(
            solar_system
        )
        self.assertFalse(created)
        self.assertEqual(structure.name, StructureTag.NAME_LOWSEC_TAG)
        self.assertEqual(structure.style, StructureTag.Style.ORANGE)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)

    def test_can_create_for_space_type_highsec(self):
        solar_system = EveSolarSystem.objects.get(name="Osoggur")
        structure, created = StructureTag.objects.update_or_create_for_space_type(
            solar_system
        )
        self.assertTrue(created)
        self.assertEqual(structure.name, StructureTag.NAME_HIGHSEC_TAG)
        self.assertEqual(structure.style, StructureTag.Style.GREEN)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)

    def test_can_create_for_space_type_nullsec(self):
        solar_system = EveSolarSystem.objects.get(name="1-PGSG")
        structure, created = StructureTag.objects.update_or_create_for_space_type(
            solar_system
        )
        self.assertTrue(created)
        self.assertEqual(structure.name, StructureTag.NAME_NULLSEC_TAG)
        self.assertEqual(structure.style, StructureTag.Style.RED)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)

    def test_can_create_for_space_type_w_space(self):
        solar_system = EveSolarSystem.objects.get(id=31000005)
        structure, created = StructureTag.objects.update_or_create_for_space_type(
            solar_system
        )
        self.assertTrue(created)
        self.assertEqual(structure.name, StructureTag.NAME_W_SPACE_TAG)
        self.assertEqual(structure.style, StructureTag.Style.LIGHT_BLUE)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)

    def test_can_get_existing_sov_tag(self):
        tag = StructureTag.objects.create(name="sov")
        structure, created = StructureTag.objects.update_or_create_for_sov()
        self.assertFalse(created)
        self.assertEqual(structure, tag)

    def test_can_get_non_existing_sov_tag(self):
        structure, created = StructureTag.objects.update_or_create_for_sov()
        self.assertTrue(created)
        self.assertEqual(structure.name, "sov")
        self.assertEqual(structure.style, StructureTag.Style.DARK_BLUE)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 20)

    def test_can_update_sov_tag(self):
        StructureTag.objects.create(
            name="sov",
            style=StructureTag.Style.GREEN,
            is_user_managed=True,
            is_default=True,
            order=100,
        )
        structure, created = StructureTag.objects.update_or_create_for_sov()
        self.assertFalse(created)
        self.assertEqual(structure.name, "sov")
        self.assertEqual(structure.style, StructureTag.Style.DARK_BLUE)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 20)

    """
    def test_update_nullsec_tag(self):
        solar_system = EveSolarSystem.objects.get(id=30000474)
        structure, created = \
            StructureTag.objects.get_or_create_for_space_type(solar_system)
        self.assertEqual(structure.name, StructureTag.NAME_NULLSEC_TAG)
        self.assertEqual(structure.style, StructureTag.Style.RED)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)

        structure.style = StructureTag.Style.GREEN
        structure.is_user_managed = True
        structure.order = 100
        structure.save()

        structure, created = \
            StructureTag.objects.get_or_create_for_space_type(solar_system)

        self.assertFalse(created)
        self.assertEqual(structure.name, StructureTag.NAME_NULLSEC_TAG)
        self.assertEqual(structure.style, StructureTag.Style.RED)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)
    """


class TestWebhookManager(NoSocketsTestCase):
    def test_should_return_enabled_notification_types(self):
        # given
        Webhook.objects.create(
            name="w1",
            url="w1",
            is_active=True,
            notification_types=[
                NotificationType.STRUCTURE_ANCHORING,
                NotificationType.STRUCTURE_REFUELED_EXTRA,
            ],
        )
        Webhook.objects.create(
            name="w2",
            url="w2",
            is_active=True,
            notification_types=[
                NotificationType.STRUCTURE_LOST_ARMOR,
                NotificationType.STRUCTURE_LOST_SHIELD,
            ],
        )
        Webhook.objects.create(
            name="w3",
            url="w3",
            is_active=False,
            notification_types=[NotificationType.TOWER_ALERT_MSG],
        )
        # when
        result = Webhook.objects.enabled_notification_types()
        # then
        self.assertSetEqual(
            result,
            {
                NotificationType.STRUCTURE_LOST_ARMOR,
                NotificationType.STRUCTURE_LOST_SHIELD,
                NotificationType.STRUCTURE_ANCHORING,
                NotificationType.STRUCTURE_REFUELED_EXTRA,
            },
        )

    def test_should_return_empty_set(self):
        # when
        result = Webhook.objects.enabled_notification_types()
        # then
        self.assertSetEqual(result, set())
