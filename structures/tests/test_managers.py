from datetime import datetime
from unittest.mock import Mock, patch

from bravado.exception import HTTPError

from allianceauth.eveonline.models import EveCorporationInfo, EveCharacter

from . import to_json
from ..models import (
    EveEntity,    
    EveCategory,
    EveGroup,
    EveType,
    EveRegion,
    EveConstellation,
    EveSolarSystem,
    EveMoon,
    EvePlanet,
    EveSovereigntyMap,
    Owner,    
    Structure,
    StructureService,
    StructureTag
    
)
from .testdata import (
    load_entity, 
    load_entities,
    create_structures,     
    esi_mock_client
)
from ..utils import NoSocketsTestCase, set_test_logger

MODULE_PATH = 'structures.managers'
MODULE_PATH_ESI_FETCH = 'structures.helpers.esi_fetch'
logger = set_test_logger(MODULE_PATH, __file__)


class TestEveCategoryManager(NoSocketsTestCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EveCategory.objects.all().delete()
    
    def test_can_get_stored_object(self):        
        load_entity(EveCategory)
        
        obj, created = EveCategory.objects.get_or_create_esi(65)
        
        self.assertFalse(created)
        self.assertIsInstance(obj, EveCategory)
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')
    
    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi(self, mock_provider):
        mock_provider.client = esi_mock_client()

        obj, created = EveCategory.objects.update_or_create_esi(65)
        self.assertTrue(created)
        self.assertIsInstance(obj, EveCategory)
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')
        self.assertEqual(obj.name_de, 'Structure_de')        
        self.assertEqual(obj.name_ko, 'Structure_ko')
        self.assertEqual(obj.name_ru, 'Structure_ru')
        self.assertEqual(obj.name_zh, 'Structure_zh')
        self.assertIsInstance(obj.last_updated, datetime)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_update_object_from_esi(self, mock_provider):        
        mock_provider.client = esi_mock_client()

        load_entity(EveCategory)
        obj = EveCategory.objects.get(id=65)
        obj.name = 'Superheroes'
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Superheroes')
        
        obj, created = EveCategory.objects.update_or_create_esi(65)
        self.assertFalse(created)
        self.assertIsInstance(obj, EveCategory)
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()

        obj, created = EveCategory.objects.get_or_create_esi(65)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveCategory)
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')
        
    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_raises_exception_when_create_fails(self, mock_provider):
        mock_provider.client.Universe\
            .get_universe_categories_category_id.return_value\
            .result.side_effect = RuntimeError
                
        with self.assertRaises(RuntimeError):
            EveCategory.objects.update_or_create_esi(65)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_update_all_objects_from_esi(self, mock_provider):        
        mock_provider.client = esi_mock_client()

        load_entity(EveCategory)
        obj = EveCategory.objects.get(id=65)
        obj.name = 'Superheroes'
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Superheroes')
        total_count = EveCategory.objects.count()
        
        count_updated = EveCategory.objects.update_all_esi()
        
        obj.refresh_from_db()
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')
        self.assertEqual(count_updated, total_count)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_recover_from_errors_during_update_all_objects_from_esi(
        self, mock_provider
    ):
        mock_provider.client.Universe\
            .get_universe_categories_category_id.return_value\
            .result.side_effect = HTTPError(
                response=Mock(), message='Test'
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
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)                
        self.assertFalse(created)
        self.assertIsInstance(obj, EveGroup)
        self.assertEqual(obj.id, 1657)
        self.assertEqual(obj.name, 'Citadel')
        self.assertEqual(obj.eve_category_id, 65)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveGroup)
        self.assertEqual(obj.id, 1657)
        self.assertEqual(obj.name, 'Citadel')
        self.assertEqual(obj.eve_category_id, 65)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found_including_parent(
        self, mock_provider
    ):
        EveCategory.objects.get(id=65).delete()
        mock_provider.client = esi_mock_client()
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveGroup)
        self.assertEqual(obj.id, 1657)
        self.assertEqual(obj.name, 'Citadel')
        
        obj_parent = obj.eve_category        
        self.assertIsInstance(obj_parent, EveCategory)
        self.assertEqual(obj_parent.id, 65)
        self.assertEqual(obj_parent.name, 'Structure')

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_update_from_esi_not_including_related(self, mock_provider):
        mock_provider.client = esi_mock_client()
        load_entity(EveGroup)
        obj = EveGroup.objects.get(id=1657)
        obj.name = 'Fantastic Four'
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Fantastic Four')

        obj_parent = EveCategory.objects.get(id=65)
        obj_parent.name = 'Superheros'
        obj_parent.save()
        obj_parent.refresh_from_db()
        self.assertEqual(obj_parent.name, 'Superheros')
        
        obj, created = EveGroup.objects.update_or_create_esi(1657)        
        self.assertFalse(created)
        self.assertIsInstance(obj, EveGroup)
        self.assertEqual(obj.id, 1657)
        self.assertEqual(obj.name, 'Citadel')
        self.assertEqual(obj.eve_category_id, 65)
        obj_parent.refresh_from_db()
        self.assertEqual(obj_parent.name, 'Superheros')


class TestEveTypeManager(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([EveCategory, EveGroup])
    
    def test_can_get_stored_object(self):        
        load_entity(EveType)
        
        obj, created = EveType.objects.get_or_create_esi(35832)                
        self.assertFalse(created)
        self.assertEqual(obj.id, 35832)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        
        obj, created = EveType.objects.get_or_create_esi(35832)        
        self.assertTrue(created)
        self.assertEqual(obj.id, 35832)
        self.assertIsInstance(EveType.objects.get(id=35832), EveType)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found_including_related(
        self, mock_provider
    ):
        mock_provider.client = esi_mock_client()
        EveGroup.objects.get(id=1657).delete()
        
        obj, created = EveType.objects.get_or_create_esi(35832)
        self.assertTrue(created)
        self.assertIsInstance(obj, EveType)
        self.assertEqual(obj.id, 35832)
        self.assertEqual(obj.name, 'Astrahus')
        
        obj_parent = obj.eve_group        
        self.assertEqual(obj_parent.id, 1657)
        self.assertEqual(obj_parent.name, 'Citadel')


class TestEveRegionManager(NoSocketsTestCase):

    def test_can_get_stored_object(self):        
        load_entity(EveRegion)

        obj, created = EveRegion.objects.get_or_create_esi(10000005)        
        self.assertFalse(created)
        self.assertEqual(obj.id, 10000005)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()                
        
        obj, created = EveRegion.objects.get_or_create_esi(10000005)        
        self.assertTrue(created)
        self.assertEqual(obj.id, 10000005)
        self.assertEqual(obj.name, 'Detorid')


class TestEveConstellationManager(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entity(EveRegion)
    
    def test_can_get_stored_object(self):        
        load_entity(EveConstellation)

        obj, created = EveConstellation.objects.get_or_create_esi(20000069)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 20000069)
        self.assertEqual(obj.name, '1RG-GU')

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        load_entity(EveRegion)

        obj, created = EveConstellation.objects.get_or_create_esi(20000069)
        self.assertTrue(created)
        self.assertEqual(obj.id, 20000069)
        self.assertEqual(obj.name, '1RG-GU')

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found_w_parent(
        self, mock_provider
    ):
        mock_provider.client = esi_mock_client()
        EveRegion.objects.get(id=10000005).delete()

        obj, created = EveConstellation.objects.get_or_create_esi(20000069)
        self.assertTrue(created)
        self.assertEqual(obj.id, 20000069)
        self.assertEqual(obj.name, '1RG-GU')
        
        obj_parent = obj.eve_region        
        self.assertEqual(obj_parent.id, 10000005)
        self.assertEqual(obj_parent.name, 'Detorid')
        
    
class TestEveSolarSystemManager(NoSocketsTestCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([
            EveCategory, 
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation
        ])
        
    def test_can_get_stored_object(self):        
        load_entity(EveSolarSystem)
        load_entity(EvePlanet)
        
        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        
        self.assertFalse(created)
        self.assertIsInstance(obj, EveSolarSystem)
        self.assertEqual(obj.id, 30000474)
        self.assertEqual(obj.name, '1-PGSG')
        self.assertEqual(obj.security_status, -0.496552765369415)
        self.assertEqual(obj.eve_constellation_id, 20000069)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        
        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        self.assertTrue(created)
        self.assertIsInstance(obj, EveSolarSystem)
        self.assertEqual(obj.id, 30000474)
        self.assertEqual(obj.name, '1-PGSG')
        self.assertEqual(obj.security_status, -0.496552765369415)
        self.assertEqual(obj.eve_constellation_id, 20000069)
        
    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found_including_related(
        self, mock_provider
    ):
        mock_provider.client = esi_mock_client()
        EveConstellation.objects.get(id=20000069).delete()

        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 30000474)
        self.assertEqual(obj.name, '1-PGSG')
        self.assertEqual(obj.security_status, -0.496552765369415)
        self.assertEqual(obj.eve_constellation_id, 20000069)
        self.assertSetEqual(
            {x.id for x in EvePlanet.objects.filter(eve_solar_system=obj)},
            {40029526, 40029528, 40029529}
        )
        
        obj_parent = obj.eve_constellation
        self.assertIsInstance(obj_parent, EveConstellation)
        self.assertEqual(obj_parent.id, 20000069)
        self.assertEqual(obj_parent.name, "1RG-GU")
        self.assertEqual(obj_parent.eve_region_id, 10000005)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_update_object_from_esi_including_related(self, mock_provider):
        mock_provider.client = esi_mock_client()
        load_entity(EveSolarSystem)
        obj = EveSolarSystem.objects.get(id=30000474)
        obj.name = 'Alpha'
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Alpha')

        load_entity(EvePlanet)
        obj_child = EvePlanet.objects.get(id=40029526)
        obj_child.name = 'Alpha I'
        obj_child.save()
        obj_child.refresh_from_db()
        self.assertEqual(obj_child.name, 'Alpha I')

        obj, created = EveSolarSystem.objects.update_or_create_esi(30000474)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 30000474)
        self.assertEqual(obj.name, '1-PGSG')        
        obj_child.refresh_from_db()
        self.assertEqual(obj_child.name, '1-PGSG I')
        

class TestEveMoonManager(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([
            EveCategory, 
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EvePlanet
        ])

    def test_can_get_stored_object(self):        
        load_entity(EveMoon)

        obj, created = EveMoon.objects.get_or_create_esi(40161465)        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161465)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
       
        obj, created = EveMoon.objects.get_or_create_esi(40161465)
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161465)
        self.assertEqual(obj.name, 'Amamake II - Moon 1')
        self.assertEqual(obj.eve_solar_system_id, 30002537)        
        self.assertEqual(obj.position_x, 1)
        self.assertEqual(obj.position_y, 2)
        self.assertEqual(obj.position_z, 3)
        
    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found_w_parent(self, mock_provider):
        mock_provider.client = esi_mock_client()
        EveSolarSystem.objects.get(id=30000474).delete()
        
        obj, created = EveMoon.objects.get_or_create_esi(40161465)
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161465)
        
        obj_parent_1 = obj.eve_solar_system
        self.assertEqual(obj_parent_1.id, 30002537)


class TestEvePlanetManager(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([
            EveCategory, 
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem
        ])
    
    def test_can_get_stored_object(self):
        load_entity(EvePlanet)

        obj, created = EvePlanet.objects.get_or_create_esi(40161469)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161469)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        
        obj, created = EvePlanet.objects.get_or_create_esi(40161469)        
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161469)
        self.assertEqual(obj.name, 'Amamake IV')
        self.assertEqual(obj.eve_solar_system_id, 30002537)
        self.assertEqual(obj.eve_type_id, 2016)
        self.assertEqual(obj.position_x, 1)
        self.assertEqual(obj.position_y, 2)
        self.assertEqual(obj.position_z, 3)

        # localizations
        self.assertEqual(obj.name_de, 'Amamake_de IV')
        self.assertEqual(obj.name_ko, 'Amamake_ko IV')
        self.assertEqual(obj.name_ru, 'Amamake_ru IV')
        self.assertEqual(obj.name_zh, 'Amamake_zh IV')
        
    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found_w_parent(
        self, mock_provider
    ):
        mock_provider.client = esi_mock_client()
        EveSolarSystem.objects.get(id=30000474).delete()
        EveType.objects.get(id=2016).delete()

        obj, created = EvePlanet.objects.get_or_create_esi(40161469)        
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161469)
        
        obj_parent_1 = obj.eve_solar_system
        self.assertEqual(obj_parent_1.id, 30002537)

        obj_parent_2 = obj.eve_type
        self.assertEqual(obj_parent_2.id, 2016)


class TestEveSovereigntyMapManagerUpdateFromEsi(NoSocketsTestCase):

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_fetch_from_esi_and_overwrites_existing_map(
        self, mock_provider
    ):
        mock_provider.client = esi_mock_client()
        
        EveSovereigntyMap.objects.create(
            solar_system_id=30000726,
            alliance_id=3001
        )
        
        EveSovereigntyMap.objects.update_from_esi()
        self.assertEqual(EveSovereigntyMap.objects.count(), 3)
        
        obj = EveSovereigntyMap.objects.get(solar_system_id=30000726)
        self.assertEqual(obj.corporation_id, 2011)
        self.assertEqual(obj.alliance_id, 3011)

        obj = EveSovereigntyMap.objects.get(solar_system_id=30000474)
        self.assertEqual(obj.corporation_id, 2001)
        self.assertEqual(obj.alliance_id, 3001)

        obj = EveSovereigntyMap.objects.get(solar_system_id=30000728)
        self.assertEqual(obj.corporation_id, 2001)
        self.assertEqual(obj.alliance_id, 3001)

    
class TestEveEntityManager(NoSocketsTestCase):
    
    def test_can_get_stored_object(self):
        load_entity(EveEntity)

        obj, created = EveEntity.objects.get_or_create_esi(3011)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 3011)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        
        obj, created = EveEntity.objects.get_or_create_esi(3011)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 3011)
        self.assertEqual(obj.name, "Big Bad Alliance")

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_update_object_from_esi(self, mock_provider):
        mock_provider.client = esi_mock_client()
        load_entity(EveEntity)
        obj = EveEntity.objects.get(id=3011)
        obj.name = 'Fantastic Four'
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Fantastic Four')
        
        obj, created = EveEntity.objects.update_or_create_esi(3011)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 3011)
        self.assertEqual(obj.name, "Big Bad Alliance")

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_raises_exceptions_if_no_esi_match(self, mock_provider):
        mock_client = Mock()    
        mock_client.Universe.post_universe_names\
            .return_value.result.return_value = []
        mock_provider.client = mock_client
        
        with self.assertRaises(ValueError):
            EveEntity.objects.update_or_create_esi(3011)
        
    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_raises_exception_when_create_fails(self, mock_provider):
        mock_client = Mock()        
        mock_client.Universe.post_universe_names\
            .return_value.result.side_effect = RuntimeError()
        mock_provider.client = mock_client
        
        with self.assertRaises(RuntimeError):
            EveEntity.objects.update_or_create_esi(3011)


class TestStructureManager(NoSocketsTestCase):
                
    def test_can_get_stored_object(self):
        mock_client = Mock(side_effect=RuntimeError)        
        create_structures()

        obj, created = Structure.objects.get_or_create_esi(
            1000000000001, mock_client
        )        
        self.assertFalse(created)
        self.assertEqual(obj.id, 1000000000001)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        mock_token = Mock()
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveCharacter
        ])
        
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )

        obj, created = Structure.objects.get_or_create_esi(
            1000000000001, mock_token
        )        
        self.assertTrue(created)
        self.assertEqual(obj.id, 1000000000001)
        self.assertEqual(obj.name, 'Test Structure Alpha')
        self.assertEqual(obj.eve_type_id, 35832)
        self.assertEqual(obj.eve_solar_system_id, 30002537)
        self.assertEqual(int(obj.owner.corporation.corporation_id), 2001)
        self.assertEqual(obj.position_x, 55028384780.0)
        self.assertEqual(obj.position_y, 7310316270.0)
        self.assertEqual(obj.position_z, -163686684205.0)

    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_can_update_object_from_esi(self, mock_provider):
        mock_provider.client = esi_mock_client()            
        mock_token = Mock()
        create_structures()
        obj = Structure.objects.get(id=1000000000001)
        obj.name = 'Batcave'
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Batcave')
        
        obj, created = Structure.objects.update_or_create_esi(
            1000000000001, mock_token
        )        
        self.assertFalse(created)
        self.assertEqual(obj.id, 1000000000001)
        self.assertEqual(obj.name, 'Test Structure Alpha')
        
    @patch(MODULE_PATH_ESI_FETCH + '.provider')
    def test_raises_exception_when_create_fails(self, mock_provider):        
        mock_token = Mock()
        mock_provider.client\
            .Universe.get_universe_structures_structure_id\
            .return_value.result.side_effect = RuntimeError()
                
        with self.assertRaises(RuntimeError):
            Structure.objects.update_or_create_esi(
                1000000000001, mock_token
            )

    def test_raises_exception_when_create_without_token(self):
        with self.assertRaises(ValueError):
            obj, created = Structure.objects.update_or_create_esi(987, None)


class TestStructureManagerCreateFromDict(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveCharacter,
            EveSovereigntyMap
        ])
        cls.owner = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
    
    def test_can_create_full(self):
       
        structure = {     
            "corporation_id": 2001,
            "fuel_expires": None,        
            "name": "Test Structure Alpha",
            "next_reinforce_apply": None,
            "next_reinforce_hour": None,
            "next_reinforce_weekday": None,
            "position": {
                "x": 55028384780.0,
                "y": 7310316270.0,
                "z": -163686684205.0
            },
            "profile_id": 101853,
            "reinforce_hour": 18,
            "reinforce_weekday": 5,
            "services": [
                {
                    "name": "Clone Bay",
                    "name_de": "Clone Bay_de",
                    "name_ko": "Clone Bay_ko",
                    "state": "online"
                },
                {
                    "name": "Market Hub",
                    "name_de": "Market Hub_de",
                    "name_ko": "Market Hub_ko",
                    "state": "offline"
                }
            ],
            "state": "shield_vulnerable",
            "state_timer_end": None,
            "state_timer_start": None,
            "structure_id": 1000000000001,
            "system_id": 30002537,
            "type_id": 35832,
            "unanchors_at": None
        }
        obj, created = Structure.objects.update_or_create_from_dict(
            structure, self.owner
        )
        
        # check structure
        self.assertEqual(obj.id, 1000000000001)
        self.assertEqual(obj.name, 'Test Structure Alpha')
        self.assertEqual(obj.eve_type_id, 35832)
        self.assertEqual(obj.eve_solar_system_id, 30002537)
        self.assertEqual(int(obj.owner.corporation.corporation_id), 2001)
        self.assertEqual(obj.position_x, 55028384780.0)
        self.assertEqual(obj.position_y, 7310316270.0)
        self.assertEqual(obj.position_z, -163686684205.0)
        self.assertEqual(obj.reinforce_hour, 18)
        self.assertEqual(obj.state, Structure.STATE_SHIELD_VULNERABLE)
        # todo: add more content tests
        
        # check services
        services = {
            to_json(
                {
                    'name': x.name,
                    'name_de': x.name_de,
                    'name_ko': x.name_ko,
                    'state': x.state
                }
            )
            for x in obj.structureservice_set.all()
        }
        expected = {
            to_json(
                {
                    'name': 'Clone Bay', 
                    'name_de': 'Clone Bay_de', 
                    'name_ko': 'Clone Bay_ko', 
                    'state': StructureService.STATE_ONLINE
                }
            ),
            to_json(
                {
                    'name': 'Market Hub', 
                    'name_de': 'Market Hub_de', 
                    'name_ko': 'Market Hub_ko', 
                    'state': StructureService.STATE_OFFLINE
                }
            ),
        }
        self.assertEqual(services, expected)


class TestStructureTagManager(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([
            EveCategory, 
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem
        ])
    
    def test_can_get_space_type_tag_that_exists(self):
        solar_system = EveSolarSystem.objects.get(id=30002537)
        tag = StructureTag.objects.create(name=StructureTag.NAME_LOWSEC_TAG)
        obj, created = \
            StructureTag.objects.get_or_create_for_space_type(solar_system)
        self.assertFalse(created)
        self.assertEqual(obj, tag)
        
    def test_can_get_space_type_tag_that_does_not_exist(self):
        solar_system = EveSolarSystem.objects.get(id=30002537)
        obj, created = \
            StructureTag.objects.get_or_create_for_space_type(solar_system)
        self.assertTrue(created)
        self.assertEqual(obj.name, StructureTag.NAME_LOWSEC_TAG)
        self.assertEqual(obj.style, StructureTag.STYLE_ORANGE)
        self.assertEqual(obj.is_user_managed, False)
        self.assertEqual(obj.is_default, False)
        self.assertEqual(obj.order, 50)

    def test_can_update_space_type_tag(self):
        solar_system = EveSolarSystem.objects.get(id=30002537)
        StructureTag.objects.create(
            name=StructureTag.NAME_LOWSEC_TAG,
            style=StructureTag.STYLE_GREEN,
            is_user_managed=True,
            is_default=True,
            order=100
        )
        obj, created = \
            StructureTag.objects.update_or_create_for_space_type(solar_system)
        self.assertFalse(created)
        self.assertEqual(obj.name, StructureTag.NAME_LOWSEC_TAG)
        self.assertEqual(obj.style, StructureTag.STYLE_ORANGE)
        self.assertEqual(obj.is_user_managed, False)
        self.assertEqual(obj.is_default, False)
        self.assertEqual(obj.order, 50)

    def test_can_create_for_space_type_highsec(self):
        solar_system = EveSolarSystem.objects.get(id=30002506)
        obj, created = \
            StructureTag.objects.update_or_create_for_space_type(solar_system)
        self.assertTrue(created)
        self.assertEqual(obj.name, StructureTag.NAME_HIGHSEC_TAG)
        self.assertEqual(obj.style, StructureTag.STYLE_GREEN)
        self.assertEqual(obj.is_user_managed, False)
        self.assertEqual(obj.is_default, False)
        self.assertEqual(obj.order, 50)
    
    def test_can_create_for_space_type_nullsec(self):
        solar_system = EveSolarSystem.objects.get(id=30000474)
        obj, created = \
            StructureTag.objects.update_or_create_for_space_type(solar_system)
        self.assertTrue(created)
        self.assertEqual(obj.name, StructureTag.NAME_NULLSEC_TAG)
        self.assertEqual(obj.style, StructureTag.STYLE_RED)
        self.assertEqual(obj.is_user_managed, False)
        self.assertEqual(obj.is_default, False)
        self.assertEqual(obj.order, 50)

    def test_can_create_for_space_type_w_space(self):
        solar_system = EveSolarSystem.objects.get(id=31000005)
        obj, created = \
            StructureTag.objects.update_or_create_for_space_type(solar_system)
        self.assertTrue(created)
        self.assertEqual(obj.name, StructureTag.NAME_W_SPACE_TAG)
        self.assertEqual(obj.style, StructureTag.STYLE_LIGHT_BLUE)
        self.assertEqual(obj.is_user_managed, False)
        self.assertEqual(obj.is_default, False)
        self.assertEqual(obj.order, 50)

    def test_can_get_existing_sov_tag(self):
        tag = StructureTag.objects.create(name='sov')        
        obj, created = StructureTag.objects.update_or_create_for_sov()
        self.assertFalse(created)
        self.assertEqual(obj, tag)

    def test_can_get_non_existing_sov_tag(self):
        obj, created = StructureTag.objects.update_or_create_for_sov()
        self.assertTrue(created)
        self.assertEqual(obj.name, 'sov')
        self.assertEqual(obj.style, StructureTag.STYLE_DARK_BLUE)
        self.assertEqual(obj.is_user_managed, False)
        self.assertEqual(obj.is_default, False)
        self.assertEqual(obj.order, 20)

    def test_can_update_sov_tag(self):
        StructureTag.objects.create(
            name='sov', 
            style=StructureTag.STYLE_GREEN,
            is_user_managed=True,
            is_default=True,
            order=100
        )
        obj, created = StructureTag.objects.update_or_create_for_sov()
        self.assertFalse(created)
        self.assertEqual(obj.name, 'sov')
        self.assertEqual(obj.style, StructureTag.STYLE_DARK_BLUE)
        self.assertEqual(obj.is_user_managed, False)
        self.assertEqual(obj.is_default, False)
        self.assertEqual(obj.order, 20)

    """
    def test_update_nullsec_tag(self):
        solar_system = EveSolarSystem.objects.get(id=30000474)
        obj, created = \
            StructureTag.objects.get_or_create_for_space_type(solar_system)
        self.assertEqual(obj.name, StructureTag.NAME_NULLSEC_TAG)
        self.assertEqual(obj.style, StructureTag.STYLE_RED)
        self.assertEqual(obj.is_user_managed, False)
        self.assertEqual(obj.is_default, False)
        self.assertEqual(obj.order, 50)

        obj.style = StructureTag.STYLE_GREEN
        obj.is_user_managed = True
        obj.order = 100
        obj.save()

        obj, created = \
            StructureTag.objects.get_or_create_for_space_type(solar_system)

        self.assertFalse(created)
        self.assertEqual(obj.name, StructureTag.NAME_NULLSEC_TAG)
        self.assertEqual(obj.style, StructureTag.STYLE_RED)
        self.assertEqual(obj.is_user_managed, False)
        self.assertEqual(obj.is_default, False)
        self.assertEqual(obj.order, 50)
    """
