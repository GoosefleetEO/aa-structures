import datetime as dt
from unittest.mock import Mock, patch

from bravado.exception import HTTPError

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
    EveType,
)
from .testdata import esi_mock_client, load_entities, load_entity

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
        self.assertIsInstance(structure.last_updated, dt.datetime)

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
