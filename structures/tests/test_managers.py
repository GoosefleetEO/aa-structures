from unittest.mock import Mock, patch

from django.test import TestCase

from allianceauth.eveonline.models import EveCorporationInfo

from . import set_logger
from .testdata import load_entity, load_entities,\
    create_structures, esi_get_universe_planets_planet_id
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
    Owner,    
    Structure
)


MODULE_PATH = 'structures.managers'
logger = set_logger(MODULE_PATH, __file__)


def my_client():
    mock_client = Mock()
    mock_client.Universe\
        .get_universe_categories_category_id.return_value\
        .result.return_value = {
            "id": 65,
            "name": "Structure"
        }
    mock_client.Universe\
        .get_universe_groups_group_id.return_value\
        .result.return_value = {
            "id": 1657,
            "name": "Citadel",
            "category_id": 65
        } 
    mock_client.Universe\
        .get_universe_types_type_id\
        .return_value.result.return_value = {
            "id": 35832,
            "name": "Astrahus",
            "group_id": 1657
        }            
    mock_client.Universe\
        .get_universe_regions_region_id\
        .return_value.result.return_value = {
            "id": 10000005,
            "name": "Detorid"
        }
    mock_client.Universe\
        .get_universe_constellations_constellation_id\
        .return_value.result.return_value = {
            "id": 20000069,
            "name": "1RG-GU",
            "region_id": 10000005
        }
    mock_client.Universe\
        .get_universe_systems_system_id\
        .return_value.result.return_value = {
            "id": 30000474,
            "name": "1-PGSG",
            "security_status": -0.496552765369415,
            "constellation_id": 20000069,
            "star_id": 99,
            "planets":
            [
                {
                    "planet_id": 40029526
                },
                {
                    "planet_id": 40029528
                },
                {
                    "planet_id": 40029529
                }
            ]
        }
    mock_client.Universe.get_universe_planets_planet_id\
        .side_effect = esi_get_universe_planets_planet_id

    mock_client.Universe.get_universe_moons_moon_id\
        .return_value.result.return_value = {
            "id": 40161465,
            "name": "Amamake II - Moon 1",
            "system_id": 30002537,
            "position": {
                "x": 1,
                "y": 2,
                "z": 3
            }
        }
    
    return mock_client


class TestEveCategoryManager(TestCase):
    
    def setUp(self):
        EveCategory.objects.all().delete()

    @patch(MODULE_PATH + '.provider')
    def test_get(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveCategory)
        
        obj, created = EveCategory.objects.get_or_create_esi(65)
        
        self.assertFalse(created)
        self.assertIsInstance(obj, EveCategory)
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')

    @patch(MODULE_PATH + '.provider')
    def test_create(self, mock_provider):        
        mock_provider.client = my_client()

        obj, created = EveCategory.objects.get_or_create_esi(65)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveCategory)
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')
        
    @patch(MODULE_PATH + '.provider')
    def test_create_failed(self, mock_provider):
        mock_provider.client.Universe\
            .get_universe_categories_category_id.return_value\
            .result.side_effect = RuntimeError()
                
        with self.assertRaises(RuntimeError):
            EveCategory.objects.get_or_create_esi(65)


class TestEveGroupManager(TestCase):
    
    def setUp(self):
        load_entity(EveCategory)
    
    @patch(MODULE_PATH + '.provider')
    def test_get(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveGroup)
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)                
        self.assertFalse(created)
        self.assertIsInstance(obj, EveGroup)
        self.assertEqual(obj.id, 1657)
        self.assertEqual(obj.name, 'Citadel')
        self.assertEqual(obj.eve_category_id, 65)

    @patch(MODULE_PATH + '.provider')
    def test_create(self, mock_provider):        
        mock_provider.client = my_client()
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveGroup)
        self.assertEqual(obj.id, 1657)
        self.assertEqual(obj.name, 'Citadel')
        self.assertEqual(obj.eve_category_id, 65)

    @patch(MODULE_PATH + '.provider')
    def test_create_w_parent(self, mock_provider):
        EveCategory.objects.get(id=65).delete()
        mock_provider.client = my_client()
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveGroup)
        self.assertEqual(obj.id, 1657)
        self.assertEqual(obj.name, 'Citadel')
        
        obj_parent = obj.eve_category        
        self.assertIsInstance(obj_parent, EveCategory)
        self.assertEqual(obj_parent.id, 65)
        self.assertEqual(obj_parent.name, 'Structure')


class TestEveTypeManager(TestCase):

    def setUp(self):
        load_entities([EveCategory, EveGroup])

    @patch(MODULE_PATH + '.provider')
    def test_get(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveType)
        
        obj, created = EveType.objects.get_or_create_esi(35832)                
        self.assertFalse(created)
        self.assertEqual(obj.id, 35832)

    @patch(MODULE_PATH + '.provider')
    def test_create(self, mock_provider):
        mock_provider.client = my_client()
        
        obj, created = EveType.objects.get_or_create_esi(35832)        
        self.assertTrue(created)
        self.assertEqual(obj.id, 35832)
        self.assertIsInstance(EveType.objects.get(id=35832), EveType)

    @patch(MODULE_PATH + '.provider')
    def test_create_w_parent(self, mock_provider):
        mock_provider.client = my_client()
        EveGroup.objects.get(id=1657).delete()
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveGroup)
        self.assertEqual(obj.id, 1657)
        self.assertEqual(obj.name, 'Citadel')
        
        obj_parent = obj.eve_category        
        self.assertIsInstance(obj_parent, EveCategory)
        self.assertEqual(obj_parent.id, 65)
        self.assertEqual(obj_parent.name, 'Structure')


class TestEveRegionManager(TestCase):

    @patch(MODULE_PATH + '.provider')
    def test_get(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveRegion)

        obj, created = EveRegion.objects.get_or_create_esi(10000005)        
        self.assertFalse(created)
        self.assertEqual(obj.id, 10000005)

    @patch(MODULE_PATH + '.provider')
    def test_create(self, mock_provider):        
        mock_provider.client = my_client()                
        
        obj, created = EveRegion.objects.get_or_create_esi(10000005)        
        self.assertTrue(created)
        self.assertEqual(obj.id, 10000005)
        self.assertEqual(obj.name, 'Detorid')


class TestEveConstellationManager(TestCase):

    def setUp(self):
        load_entity(EveRegion)

    @patch(MODULE_PATH + '.provider')
    def test_get(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveConstellation)

        obj, created = EveConstellation.objects.get_or_create_esi(20000069)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 20000069)
        self.assertEqual(obj.name, '1RG-GU')

    @patch(MODULE_PATH + '.provider')
    def test_create(self, mock_provider):
        mock_provider.client = my_client()
        load_entity(EveRegion)

        obj, created = EveConstellation.objects.get_or_create_esi(20000069)
        self.assertTrue(created)
        self.assertEqual(obj.id, 20000069)
        self.assertEqual(obj.name, '1RG-GU')

    @patch(MODULE_PATH + '.provider')
    def test_create_w_parent(self, mock_provider):
        mock_provider.client = my_client()
        EveRegion.objects.get(id=10000005).delete()

        obj, created = EveConstellation.objects.get_or_create_esi(20000069)
        self.assertTrue(created)
        self.assertEqual(obj.id, 20000069)
        self.assertEqual(obj.name, '1RG-GU')
        
        obj_parent = obj.eve_region        
        self.assertEqual(obj_parent.id, 10000005)
        self.assertEqual(obj_parent.name, 'Detorid')
        
    
class TestEveSolarSystemManager(TestCase):
    
    def setUp(self):
        load_entities([
            EveCategory, 
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation
        ])
    
    @patch(MODULE_PATH + '.provider')
    def test_get(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveSolarSystem)
        load_entity(EvePlanet)
        
        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        
        self.assertFalse(created)
        self.assertIsInstance(obj, EveSolarSystem)
        self.assertEqual(obj.id, 30000474)
        self.assertEqual(obj.name, '1-PGSG')
        self.assertEqual(obj.security_status, -0.496552765369415)
        self.assertEqual(obj.eve_constellation_id, 20000069)

    @patch(MODULE_PATH + '.provider')
    def test_create(self, mock_provider):
        mock_provider.client = my_client()
        
        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveSolarSystem)
        self.assertEqual(obj.id, 30000474)
        self.assertEqual(obj.name, '1-PGSG')
        self.assertEqual(obj.security_status, -0.496552765369415)
        self.assertEqual(obj.eve_constellation_id, 20000069)
        self.assertSetEqual(
            {x.id for x in EvePlanet.objects.filter(eve_solar_system=obj)},
            {40029526, 40029528, 40029529}
        )

    @patch(MODULE_PATH + '.provider')
    def test_create_w_parent(self, mock_provider):
        mock_provider.client = my_client()
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
        

class TestEveMoonManager(TestCase):

    def setUp(self):
        load_entities([
            EveCategory, 
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EvePlanet
        ])

    @patch(MODULE_PATH + '.provider')
    def test_get(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveMoon)

        obj, created = EveMoon.objects.get_or_create_esi(40161465)        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161465)

    @patch(MODULE_PATH + '.provider')
    def test_create(self, mock_provider):
        mock_provider.client = my_client()
       
        obj, created = EveMoon.objects.get_or_create_esi(40161465)
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161465)
        self.assertEqual(obj.name, 'Amamake II - Moon 1')
        self.assertEqual(obj.eve_solar_system_id, 30002537)        
        self.assertEqual(obj.position_x, 1)
        self.assertEqual(obj.position_y, 2)
        self.assertEqual(obj.position_z, 3)
        
    @patch(MODULE_PATH + '.provider')
    def test_create_w_parent(self, mock_provider):
        mock_provider.client = my_client()
        EveSolarSystem.objects.get(id=30000474).delete()
        
        obj, created = EveMoon.objects.get_or_create_esi(40161465)
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161465)
        
        obj_parent_1 = obj.eve_solar_system
        self.assertEqual(obj_parent_1.id, 30002537)


class TestEvePlanetManager(TestCase):

    def setUp(self):
        load_entities([
            EveCategory, 
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem
        ])

    @patch(MODULE_PATH + '.provider')
    def test_get(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EvePlanet)

        obj, created = EvePlanet.objects.get_or_create_esi(40161469)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161469)

    @patch(MODULE_PATH + '.provider')
    def test_create(self, mock_provider):
        mock_provider.client = my_client()
        
        obj, created = EvePlanet.objects.get_or_create_esi(40161469)        
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161469)
        self.assertEqual(obj.name, 'Amamake IV')
        self.assertEqual(obj.eve_solar_system_id, 30002537)
        self.assertEqual(obj.eve_type_id, 2016)
        self.assertEqual(obj.position_x, 1)
        self.assertEqual(obj.position_y, 2)
        self.assertEqual(obj.position_z, 3)
                
    @patch(MODULE_PATH + '.provider')
    def test_create_w_parent(self, mock_provider):
        mock_provider.client = my_client()
        EveSolarSystem.objects.get(id=30000474).delete()
        EveType.objects.get(id=2016).delete()

        obj, created = EvePlanet.objects.get_or_create_esi(40161469)        
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161469)
        
        obj_parent_1 = obj.eve_solar_system
        self.assertEqual(obj_parent_1.id, 30002537)

        obj_parent_2 = obj.eve_type
        self.assertEqual(obj_parent_2.id, 2016)


class TestEveEntityManager(TestCase):

    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_get(self, mock_esi_client_factory):        
        load_entity(EveEntity)

        obj, created = EveEntity.objects.get_or_create_esi(3011)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 3011)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_create_wo_client(self, mock_esi_client_factory):
        mock_client = Mock()        
        mock_client.Universe.post_universe_names\
            .return_value.result.return_value = [
                {
                    "id": 3011,
                    "category": "alliance",
                    "name": "Big Bad Alliance"
                }                
            ]      
        mock_esi_client_factory.return_value = mock_client
        
        obj, created = EveEntity.objects.get_or_create_esi(3011)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 3011)
        self.assertIsInstance(
            EveEntity.objects.get(id=3011), 
            EveEntity
        )        

    def test_create_w_client(self):                        
        mock_client = Mock()        
        mock_client.Universe.post_universe_names\
            .return_value.result.return_value = [
                {
                    "id": 3011,
                    "category": "alliance",
                    "name": "Big Bad Alliance"
                }                
            ]      
        
        obj, created = EveEntity.objects.get_or_create_esi(3011, mock_client)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 3011)
        self.assertIsInstance(
            EveEntity.objects.get(id=3011), 
            EveEntity
        )  

    def test_create_w_client_no_match(self):                        
        mock_client = Mock()        
        mock_client.Universe.post_universe_names\
            .return_value.result.return_value = []      
        
        with self.assertRaises(ValueError):
            EveEntity.objects.get_or_create_esi(3011, mock_client)
        
    def test_create_w_client_wrong_type(self):                        
        mock_client = Mock()        
        mock_client.Universe.post_universe_names\
            .return_value.result.return_value = [
                {
                    "id": 6666,
                    "category": "XXX",
                    "name": "Unclear entity"
                }                
            ]      
        
        obj, created = EveEntity.objects.get_or_create_esi(6666, mock_client)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 6666)
        self.assertIsInstance(
            EveEntity.objects.get(id=6666), 
            EveEntity
        )  
        
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_create_failed(self, mock_esi_client_factory):                
        mock_client = Mock()        
        mock_client.Universe.post_universe_names\
            .return_value.result.side_effect = RuntimeError()
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveEntity.objects.get_or_create_esi(3011)


class TestStructureManager(TestCase):
            
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_get(self, mock_esi_client_factory):                   
        mock_client = Mock()
        
        create_structures()        
        obj, created = Structure.objects.get_or_create_esi(
            1000000000001,
            mock_client
        )
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 1000000000001)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_create(self, mock_esi_client_factory):                        
        mock_client = Mock()        
        mock_client.Universe.get_universe_structures_structure_id\
            .return_value.result.return_value = {
                'id': 1000000000001,            
                'name': 'Test Structure Alpha',
                'type_id': 35832,
                'solar_system_id': 30002537,
                'owner_id': 2001,
                "position": {
                    "x": 1,
                    "y": 2,
                    "z": 3
                }
            }   

        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveCorporationInfo            
        ])
        
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )

        obj, created = Structure.objects.get_or_create_esi(
            1000000000001,
            mock_client
        )
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 1000000000001)
        self.assertIsInstance(
            Structure.objects.get(id=1000000000001), 
            Structure
        )        

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_create_failed(self, mock_esi_client_factory):        
        x = Mock()
        x.result.side_effect = RuntimeError()
        mock_client = Mock()        
        mock_client.Universe.get_universe_structures_structure_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            Structure.objects.get_or_create_esi(1000000000001, mock_client)
