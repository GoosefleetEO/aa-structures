from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from bravado.exception import HTTPError

from django.utils.timezone import now

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from app_utils.testing import NoSocketsTestCase

from ..models import (
    EveCategory,
    EveConstellation,
    EveEntity,
    EveGroup,
    EveMoon,
    EvePlanet,
    EveRegion,
    EveSolarSystem,
    EveSovereigntyMap,
    EveType,
    Owner,
    Structure,
    StructureService,
    StructureTag,
)
from . import to_json
from .testdata import create_structures, esi_mock_client, load_entities, load_entity

MODULE_PATH = "structures.managers"
MODULE_PATH_ESI_FETCH = "structures.helpers.esi_fetch"


class TestEveCategoryManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EveCategory.objects.all().delete()

    def test_can_get_stored_object(self):
        load_entity(EveCategory)

        structure, created = EveCategory.objects.get_or_create_esi(65)

        self.assertFalse(created)
        self.assertIsInstance(structure, EveCategory)
        self.assertEqual(structure.id, 65)
        self.assertEqual(structure.name, "Structure")

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        structure, created = EveCategory.objects.update_or_create_esi(65)
        self.assertTrue(created)
        self.assertIsInstance(structure, EveCategory)
        self.assertEqual(structure.id, 65)
        self.assertEqual(structure.name, "Structure")
        self.assertEqual(structure.name_de, "Structure_de")
        self.assertEqual(structure.name_ko, "Structure_ko")
        self.assertEqual(structure.name_ru, "Structure_ru")
        # self.assertEqual(structure.name_zh, "Structure_zh")
        self.assertIsInstance(structure.last_updated, datetime)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_update_object_from_esi(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        load_entity(EveCategory)
        structure = EveCategory.objects.get(id=65)
        structure.name = "Superheroes"
        structure.save()
        structure.refresh_from_db()
        self.assertEqual(structure.name, "Superheroes")

        structure, created = EveCategory.objects.update_or_create_esi(65)
        self.assertFalse(created)
        self.assertIsInstance(structure, EveCategory)
        self.assertEqual(structure.id, 65)
        self.assertEqual(structure.name, "Structure")

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        structure, created = EveCategory.objects.get_or_create_esi(65)
        self.assertTrue(created)
        self.assertIsInstance(structure, EveCategory)
        self.assertEqual(structure.id, 65)
        self.assertEqual(structure.name, "Structure")

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_raises_exception_when_create_fails(self, mock_esi_client):
        mock_esi_client.return_value.Universe.get_universe_categories_category_id.return_value.result.side_effect = (
            RuntimeError
        )

        with self.assertRaises(RuntimeError):
            EveCategory.objects.update_or_create_esi(65)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_update_all_objects_from_esi(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        load_entity(EveCategory)
        structure = EveCategory.objects.get(id=65)
        structure.name = "Superheroes"
        structure.save()
        structure.refresh_from_db()
        self.assertEqual(structure.name, "Superheroes")
        total_count = EveCategory.objects.count()

        count_updated = EveCategory.objects.update_all_esi()

        structure.refresh_from_db()
        self.assertEqual(structure.id, 65)
        self.assertEqual(structure.name, "Structure")
        self.assertEqual(count_updated, total_count)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_recover_from_errors_during_update_all_objects_from_esi(
        self, mock_esi_client
    ):
        mock_esi_client.return_value.Universe.get_universe_categories_category_id.return_value.result.side_effect = HTTPError(
            response=Mock(), message="Test"
        )

        load_entity(EveCategory)
        total_count = EveCategory.objects.update_all_esi()
        self.assertEqual(total_count, 0)


class TestEveGroupManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entity(EveCategory)

    def test_can_get_stored_object(self):
        load_entity(EveGroup)

        structure, created = EveGroup.objects.get_or_create_esi(1657)
        self.assertFalse(created)
        self.assertIsInstance(structure, EveGroup)
        self.assertEqual(structure.id, 1657)
        self.assertEqual(structure.name, "Citadel")
        self.assertEqual(structure.eve_category_id, 65)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        structure, created = EveGroup.objects.get_or_create_esi(1657)
        self.assertTrue(created)
        self.assertIsInstance(structure, EveGroup)
        self.assertEqual(structure.id, 1657)
        self.assertEqual(structure.name, "Citadel")
        self.assertEqual(structure.eve_category_id, 65)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found_including_parent(
        self, mock_esi_client
    ):
        EveCategory.objects.get(id=65).delete()
        mock_esi_client.side_effect = esi_mock_client

        structure, created = EveGroup.objects.get_or_create_esi(1657)
        self.assertTrue(created)
        self.assertIsInstance(structure, EveGroup)
        self.assertEqual(structure.id, 1657)
        self.assertEqual(structure.name, "Citadel")

        obj_parent = structure.eve_category
        self.assertIsInstance(obj_parent, EveCategory)
        self.assertEqual(obj_parent.id, 65)
        self.assertEqual(obj_parent.name, "Structure")

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_update_from_esi_not_including_related(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client
        load_entity(EveGroup)
        structure = EveGroup.objects.get(id=1657)
        structure.name = "Fantastic Four"
        structure.save()
        structure.refresh_from_db()
        self.assertEqual(structure.name, "Fantastic Four")

        obj_parent = EveCategory.objects.get(id=65)
        obj_parent.name = "Superheros"
        obj_parent.save()
        obj_parent.refresh_from_db()
        self.assertEqual(obj_parent.name, "Superheros")

        structure, created = EveGroup.objects.update_or_create_esi(1657)
        self.assertFalse(created)
        self.assertIsInstance(structure, EveGroup)
        self.assertEqual(structure.id, 1657)
        self.assertEqual(structure.name, "Citadel")
        self.assertEqual(structure.eve_category_id, 65)
        obj_parent.refresh_from_db()
        self.assertEqual(obj_parent.name, "Superheros")


class TestEveTypeManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([EveCategory, EveGroup])

    def test_can_get_stored_object(self):
        load_entity(EveType)

        structure, created = EveType.objects.get_or_create_esi(35832)
        self.assertFalse(created)
        self.assertEqual(structure.id, 35832)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        structure, created = EveType.objects.get_or_create_esi(35832)
        self.assertTrue(created)
        self.assertEqual(structure.id, 35832)
        self.assertIsInstance(EveType.objects.get(id=35832), EveType)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found_including_related(
        self, mock_esi_client
    ):
        mock_esi_client.side_effect = esi_mock_client
        EveGroup.objects.get(id=1657).delete()

        structure, created = EveType.objects.get_or_create_esi(35832)
        self.assertTrue(created)
        self.assertIsInstance(structure, EveType)
        self.assertEqual(structure.id, 35832)
        self.assertEqual(structure.name, "Astrahus")

        obj_parent = structure.eve_group
        self.assertEqual(obj_parent.id, 1657)
        self.assertEqual(obj_parent.name, "Citadel")


class TestEveRegionManager(NoSocketsTestCase):
    def test_can_get_stored_object(self):
        load_entity(EveRegion)

        structure, created = EveRegion.objects.get_or_create_esi(10000005)
        self.assertFalse(created)
        self.assertEqual(structure.id, 10000005)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        structure, created = EveRegion.objects.get_or_create_esi(10000005)
        self.assertTrue(created)
        self.assertEqual(structure.id, 10000005)
        self.assertEqual(structure.name, "Detorid")


class TestEveConstellationManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entity(EveRegion)

    def test_can_get_stored_object(self):
        load_entity(EveConstellation)

        structure, created = EveConstellation.objects.get_or_create_esi(20000069)

        self.assertFalse(created)
        self.assertEqual(structure.id, 20000069)
        self.assertEqual(structure.name, "1RG-GU")

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client
        load_entity(EveRegion)

        structure, created = EveConstellation.objects.get_or_create_esi(20000069)
        self.assertTrue(created)
        self.assertEqual(structure.id, 20000069)
        self.assertEqual(structure.name, "1RG-GU")

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found_w_parent(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client
        EveRegion.objects.get(id=10000005).delete()

        structure, created = EveConstellation.objects.get_or_create_esi(20000069)
        self.assertTrue(created)
        self.assertEqual(structure.id, 20000069)
        self.assertEqual(structure.name, "1RG-GU")

        obj_parent = structure.eve_region
        self.assertEqual(obj_parent.id, 10000005)
        self.assertEqual(obj_parent.name, "Detorid")


class TestEveSolarSystemManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([EveCategory, EveGroup, EveType, EveRegion, EveConstellation])

    def test_can_get_stored_object(self):
        load_entity(EveSolarSystem)
        load_entity(EvePlanet)

        structure, created = EveSolarSystem.objects.get_or_create_esi(30000474)

        self.assertFalse(created)
        self.assertIsInstance(structure, EveSolarSystem)
        self.assertEqual(structure.id, 30000474)
        self.assertEqual(structure.name, "1-PGSG")
        self.assertEqual(structure.security_status, -0.496552765369415)
        self.assertEqual(structure.eve_constellation_id, 20000069)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        structure, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        self.assertTrue(created)
        self.assertIsInstance(structure, EveSolarSystem)
        self.assertEqual(structure.id, 30000474)
        self.assertEqual(structure.name, "1-PGSG")
        self.assertEqual(structure.security_status, -0.496552765369415)
        self.assertEqual(structure.eve_constellation_id, 20000069)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found_including_related(
        self, mock_esi_client
    ):
        mock_esi_client.side_effect = esi_mock_client
        EveConstellation.objects.get(id=20000069).delete()

        structure, created = EveSolarSystem.objects.get_or_create_esi(30000474)

        self.assertTrue(created)
        self.assertEqual(structure.id, 30000474)
        self.assertEqual(structure.name, "1-PGSG")
        self.assertEqual(structure.security_status, -0.496552765369415)
        self.assertEqual(structure.eve_constellation_id, 20000069)
        self.assertSetEqual(
            {x.id for x in EvePlanet.objects.filter(eve_solar_system=structure)},
            {40029526, 40029528, 40029529},
        )

        obj_parent = structure.eve_constellation
        self.assertIsInstance(obj_parent, EveConstellation)
        self.assertEqual(obj_parent.id, 20000069)
        self.assertEqual(obj_parent.name, "1RG-GU")
        self.assertEqual(obj_parent.eve_region_id, 10000005)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_update_object_from_esi_including_related(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client
        load_entity(EveSolarSystem)
        structure = EveSolarSystem.objects.get(id=30000474)
        structure.name = "Alpha"
        structure.save()
        structure.refresh_from_db()
        self.assertEqual(structure.name, "Alpha")

        load_entity(EvePlanet)
        obj_child = EvePlanet.objects.get(id=40029526)
        obj_child.name = "Alpha I"
        obj_child.save()
        obj_child.refresh_from_db()
        self.assertEqual(obj_child.name, "Alpha I")

        structure, created = EveSolarSystem.objects.update_or_create_esi(30000474)

        self.assertFalse(created)
        self.assertEqual(structure.id, 30000474)
        self.assertEqual(structure.name, "1-PGSG")
        obj_child.refresh_from_db()
        self.assertEqual(obj_child.name, "1-PGSG I")


class TestEveMoonManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
                EvePlanet,
            ]
        )

    def test_can_get_stored_object(self):
        load_entity(EveMoon)

        structure, created = EveMoon.objects.get_or_create_esi(40161465)
        self.assertFalse(created)
        self.assertEqual(structure.id, 40161465)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        structure, created = EveMoon.objects.get_or_create_esi(40161465)
        self.assertTrue(created)
        self.assertEqual(structure.id, 40161465)
        self.assertEqual(structure.name, "Amamake II - Moon 1")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(structure.position_x, 1)
        self.assertEqual(structure.position_y, 2)
        self.assertEqual(structure.position_z, 3)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found_w_parent(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client
        EveSolarSystem.objects.get(id=30000474).delete()

        structure, created = EveMoon.objects.get_or_create_esi(40161465)
        self.assertTrue(created)
        self.assertEqual(structure.id, 40161465)

        obj_parent_1 = structure.eve_solar_system
        self.assertEqual(obj_parent_1.id, 30002537)


class TestEvePlanetManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
            ]
        )

    def test_can_get_stored_object(self):
        load_entity(EvePlanet)

        structure, created = EvePlanet.objects.get_or_create_esi(40161469)

        self.assertFalse(created)
        self.assertEqual(structure.id, 40161469)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        structure, created = EvePlanet.objects.get_or_create_esi(40161469)
        self.assertTrue(created)
        self.assertEqual(structure.id, 40161469)
        self.assertEqual(structure.name, "Amamake IV")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(structure.eve_type_id, 2016)
        self.assertEqual(structure.position_x, 1)
        self.assertEqual(structure.position_y, 2)
        self.assertEqual(structure.position_z, 3)

        # localizations
        self.assertEqual(structure.name_de, "Amamake_de IV")
        self.assertEqual(structure.name_ko, "Amamake_ko IV")
        self.assertEqual(structure.name_ru, "Amamake_ru IV")
        # self.assertEqual(structure.name_zh, "Amamake_zh IV")

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found_w_parent(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client
        EveSolarSystem.objects.get(id=30000474).delete()
        EveType.objects.get(id=2016).delete()

        structure, created = EvePlanet.objects.get_or_create_esi(40161469)
        self.assertTrue(created)
        self.assertEqual(structure.id, 40161469)

        obj_parent_1 = structure.eve_solar_system
        self.assertEqual(obj_parent_1.id, 30002537)

        obj_parent_2 = structure.eve_type
        self.assertEqual(obj_parent_2.id, 2016)


class TestEveSovereigntyMapManagerUpdateFromEsi(NoSocketsTestCase):
    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_fetch_from_esi_and_overwrites_existing_map(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        EveSovereigntyMap.objects.create(solar_system_id=30000726, alliance_id=3001)

        EveSovereigntyMap.objects.update_from_esi()
        self.assertEqual(EveSovereigntyMap.objects.count(), 3)

        structure = EveSovereigntyMap.objects.get(solar_system_id=30000726)
        self.assertEqual(structure.corporation_id, 2011)
        self.assertEqual(structure.alliance_id, 3011)

        structure = EveSovereigntyMap.objects.get(solar_system_id=30000474)
        self.assertEqual(structure.corporation_id, 2001)
        self.assertEqual(structure.alliance_id, 3001)

        structure = EveSovereigntyMap.objects.get(solar_system_id=30000728)
        self.assertEqual(structure.corporation_id, 2001)
        self.assertEqual(structure.alliance_id, 3001)


class TestEveEntityManager(NoSocketsTestCase):
    def test_can_get_stored_object(self):
        load_entity(EveEntity)

        structure, created = EveEntity.objects.get_or_create_esi(3011)

        self.assertFalse(created)
        self.assertEqual(structure.id, 3011)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client

        structure, created = EveEntity.objects.get_or_create_esi(3011)

        self.assertTrue(created)
        self.assertEqual(structure.id, 3011)
        self.assertEqual(structure.name, "Big Bad Alliance")

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_update_object_from_esi(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client
        load_entity(EveEntity)
        structure = EveEntity.objects.get(id=3011)
        structure.name = "Fantastic Four"
        structure.save()
        structure.refresh_from_db()
        self.assertEqual(structure.name, "Fantastic Four")

        structure, created = EveEntity.objects.update_or_create_esi(3011)

        self.assertFalse(created)
        self.assertEqual(structure.id, 3011)
        self.assertEqual(structure.name, "Big Bad Alliance")

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_raises_exceptions_if_no_esi_match(self, mock_esi_client):
        mock_esi_client.return_value.Universe.post_universe_names.return_value.result.return_value = (
            []
        )

        with self.assertRaises(ValueError):
            EveEntity.objects.update_or_create_esi(3011)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_raises_exception_when_create_fails(self, mock_esi_client):
        mock_esi_client.return_value.Universe.post_universe_names.return_value.result.side_effect = (
            RuntimeError()
        )

        with self.assertRaises(RuntimeError):
            EveEntity.objects.update_or_create_esi(3011)


class TestStructureManager(NoSocketsTestCase):
    def test_can_get_stored_object(self):
        mock_client = Mock(side_effect=RuntimeError)
        create_structures()

        structure, created = Structure.objects.get_or_create_esi(
            1000000000001, mock_client
        )
        self.assertFalse(created)
        self.assertEqual(structure.id, 1000000000001)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_create_object_from_esi_if_not_found(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client
        mock_token = Mock()
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
                EveCharacter,
            ]
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )

        structure, created = Structure.objects.get_or_create_esi(
            1000000000001, mock_token
        )
        self.assertTrue(created)
        self.assertEqual(structure.id, 1000000000001)
        self.assertEqual(structure.name, "Test Structure Alpha")
        self.assertEqual(structure.eve_type_id, 35832)
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.position_x, 55028384780.0)
        self.assertEqual(structure.position_y, 7310316270.0)
        self.assertEqual(structure.position_z, -163686684205.0)

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_can_update_object_from_esi(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client
        mock_token = Mock()
        create_structures()
        structure = Structure.objects.get(id=1000000000001)
        structure.name = "Batcave"
        structure.save()
        structure.refresh_from_db()
        self.assertEqual(structure.name, "Batcave")

        structure, created = Structure.objects.update_or_create_esi(
            1000000000001, mock_token
        )
        self.assertFalse(created)
        self.assertEqual(structure.id, 1000000000001)
        self.assertEqual(structure.name, "Test Structure Alpha")

    @patch(MODULE_PATH_ESI_FETCH + "._esi_client")
    def test_raises_exception_when_create_fails(self, mock_esi_client):
        mock_token = Mock()
        mock_esi_client.return_value.Universe.get_universe_structures_structure_id.return_value.result.side_effect = (
            RuntimeError()
        )

        with self.assertRaises(RuntimeError):
            Structure.objects.update_or_create_esi(1000000000001, mock_token)

    def test_raises_exception_when_create_without_token(self):
        with self.assertRaises(ValueError):
            structure, created = Structure.objects.update_or_create_esi(987, None)


class TestStructureManagerCreateFromDict(NoSocketsTestCase):
    def test_can_create_full(self):
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
                EveCharacter,
                EveSovereigntyMap,
            ]
        )
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
                    "name_de": "Clone Bay_de",
                    "name_ko": "Clone Bay_ko",
                    "state": "online",
                },
                {
                    "name": "Market Hub",
                    "name_de": "Market Hub_de",
                    "name_ko": "Market Hub_ko",
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
        self.assertEqual(structure.state, Structure.STATE_SHIELD_VULNERABLE)
        self.assertAlmostEqual(
            (now() - structure.created_at).total_seconds(), 0, delta=2
        )
        self.assertAlmostEqual(
            (now() - structure.last_updated_at).total_seconds(), 0, delta=2
        )
        self.assertAlmostEqual(
            (now() - structure.last_online_at).total_seconds(), 0, delta=2
        )
        # todo: add more content tests

        # check services
        services = {
            to_json(
                {
                    "name": x.name,
                    "name_de": x.name_de,
                    "name_ko": x.name_ko,
                    "state": x.state,
                }
            )
            for x in structure.structureservice_set.all()
        }
        expected = {
            to_json(
                {
                    "name": "Clone Bay",
                    "name_de": "Clone Bay_de",
                    "name_ko": "Clone Bay_ko",
                    "state": StructureService.STATE_ONLINE,
                }
            ),
            to_json(
                {
                    "name": "Market Hub",
                    "name_de": "Market Hub_de",
                    "name_ko": "Market Hub_ko",
                    "state": StructureService.STATE_OFFLINE,
                }
            ),
        }
        self.assertEqual(services, expected)

    def test_can_update_full(self):
        create_structures()
        owner = Owner.objects.get(corporation__corporation_id=2001)
        structure = Structure.objects.get(id=1000000000001)
        structure.last_updated_at = now() - timedelta(hours=2)
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
                    "name_de": "Clone Bay_de",
                    "name_ko": "Clone Bay_ko",
                    "state": "online",
                },
                {
                    "name": "Market Hub",
                    "name_de": "Market Hub_de",
                    "name_ko": "Market Hub_ko",
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
        self.assertEqual(structure.state, Structure.STATE_SHIELD_VULNERABLE)
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
                    "name_de": "Clone Bay_de",
                    "name_ko": "Clone Bay_ko",
                    "state": "offline",
                },
                {
                    "name": "Market Hub",
                    "name_de": "Market Hub_de",
                    "name_ko": "Market Hub_ko",
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


class TestStructureTagManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
            ]
        )

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
        self.assertEqual(structure.style, StructureTag.STYLE_ORANGE)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)

    def test_can_update_space_type_tag(self):
        solar_system = EveSolarSystem.objects.get(id=30002537)
        StructureTag.objects.create(
            name=StructureTag.NAME_LOWSEC_TAG,
            style=StructureTag.STYLE_GREEN,
            is_user_managed=True,
            is_default=True,
            order=100,
        )
        structure, created = StructureTag.objects.update_or_create_for_space_type(
            solar_system
        )
        self.assertFalse(created)
        self.assertEqual(structure.name, StructureTag.NAME_LOWSEC_TAG)
        self.assertEqual(structure.style, StructureTag.STYLE_ORANGE)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)

    def test_can_create_for_space_type_highsec(self):
        solar_system = EveSolarSystem.objects.get(id=30002506)
        structure, created = StructureTag.objects.update_or_create_for_space_type(
            solar_system
        )
        self.assertTrue(created)
        self.assertEqual(structure.name, StructureTag.NAME_HIGHSEC_TAG)
        self.assertEqual(structure.style, StructureTag.STYLE_GREEN)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)

    def test_can_create_for_space_type_nullsec(self):
        solar_system = EveSolarSystem.objects.get(id=30000474)
        structure, created = StructureTag.objects.update_or_create_for_space_type(
            solar_system
        )
        self.assertTrue(created)
        self.assertEqual(structure.name, StructureTag.NAME_NULLSEC_TAG)
        self.assertEqual(structure.style, StructureTag.STYLE_RED)
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
        self.assertEqual(structure.style, StructureTag.STYLE_LIGHT_BLUE)
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
        self.assertEqual(structure.style, StructureTag.STYLE_DARK_BLUE)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 20)

    def test_can_update_sov_tag(self):
        StructureTag.objects.create(
            name="sov",
            style=StructureTag.STYLE_GREEN,
            is_user_managed=True,
            is_default=True,
            order=100,
        )
        structure, created = StructureTag.objects.update_or_create_for_sov()
        self.assertFalse(created)
        self.assertEqual(structure.name, "sov")
        self.assertEqual(structure.style, StructureTag.STYLE_DARK_BLUE)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 20)

    """
    def test_update_nullsec_tag(self):
        solar_system = EveSolarSystem.objects.get(id=30000474)
        structure, created = \
            StructureTag.objects.get_or_create_for_space_type(solar_system)
        self.assertEqual(structure.name, StructureTag.NAME_NULLSEC_TAG)
        self.assertEqual(structure.style, StructureTag.STYLE_RED)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)

        structure.style = StructureTag.STYLE_GREEN
        structure.is_user_managed = True
        structure.order = 100
        structure.save()

        structure, created = \
            StructureTag.objects.get_or_create_for_space_type(solar_system)

        self.assertFalse(created)
        self.assertEqual(structure.name, StructureTag.NAME_NULLSEC_TAG)
        self.assertEqual(structure.style, StructureTag.STYLE_RED)
        self.assertEqual(structure.is_user_managed, False)
        self.assertEqual(structure.is_default, False)
        self.assertEqual(structure.order, 50)
    """
