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


class TestEveCategoryManager(TestCase):
    
    def setUp(self):
        EveCategory.objects.all().delete()

    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_category_get(
        self, 
        mock_esi_client_factory
    ):
        load_entity(EveCategory)
        
        obj, created = EveCategory.objects.get_or_create_esi(65)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 65)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_category_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_categories_category_id\
            .return_value.result.return_value = {
                "id": 65,
                "name": "Structure"
            }       
        mock_esi_client_factory.return_value = mock_client
        
        obj, created = EveCategory.objects.get_or_create_esi(65)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 65)
        self.assertIsInstance(EveCategory.objects.get(id=65), EveCategory)
    
    def test_eve_category_create_w_client(self):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_categories_category_id\
            .return_value.result.return_value = {
                "id": 65,
                "name": "Structure"
            }
        
        obj, created = EveCategory.objects.get_or_create_esi(
            65, 
            mock_client
        )
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 65)
        self.assertIsInstance(EveCategory.objects.get(id=65), EveCategory)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_category_create_failed(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_categories_category_id\
            .return_value.result.side_effect = RuntimeError()
        mock_esi_client_factory.return_value = mock_client
                
        with self.assertRaises(RuntimeError):
            EveCategory.objects.get_or_create_esi(65)


class TestEveGroupManager(TestCase):
    
    def setUp(self):
        load_entity(EveCategory)

    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_group_get(
        self, 
        mock_esi_client_factory
    ):
        load_entity(EveGroup)
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 1657)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_group_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_groups_group_id\
            .return_value.result.return_value = {
                "id": 1657,
                "name": "Citadel",
                "category_id": 65
            }       
        mock_esi_client_factory.return_value = mock_client
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 1657)
        self.assertIsInstance(EveGroup.objects.get(id=1657), EveGroup)

    def test_eve_group_create_w_client(self):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_groups_group_id\
            .return_value.result.return_value = {
                "id": 1657,
                "name": "Citadel",
                "category_id": 65
            }
        
        obj, created = EveGroup.objects.get_or_create_esi(
            1657, 
            mock_client
        )
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 1657)
        self.assertIsInstance(EveGroup.objects.get(id=1657), EveGroup)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_group_create_failed(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_groups_group_id\
            .return_value.result.side_effect = RuntimeError()
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveGroup.objects.get_or_create_esi(1657)
        

class TestEveTypeManager(TestCase):

    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_type_get(
        self, 
        mock_esi_client_factory
    ):
        load_entities([EveCategory, EveGroup, EveType])

        obj, created = EveType.objects.get_or_create_esi(35832)        
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 35832)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_type_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_types_type_id\
            .return_value.result.return_value = {
                "id": 35832,
                "name": "Astrahus",
                "group_id": 1657
            }        
        mock_esi_client_factory.return_value = mock_client
        
        load_entities([EveCategory, EveGroup])
        
        obj, created = EveType.objects.get_or_create_esi(35832)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 35832)
        self.assertIsInstance(EveType.objects.get(id=35832), EveType)

    def test_eve_type_create_w_client(self):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_types_type_id\
            .return_value.result.return_value = {
                "id": 35832,
                "name": "Astrahus",
                "group_id": 1657
            }        
                
        load_entities([EveCategory, EveGroup])        
        obj, created = EveType.objects.get_or_create_esi(35832, mock_client)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 35832)
        self.assertIsInstance(EveType.objects.get(id=35832), EveType)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_type_create_failed(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_types_type_id\
            .return_value.result.side_effect = RuntimeError()     
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveType.objects.get_or_create_esi(35832)


class TestEveRegionManager(TestCase):

    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_region_get(
        self, 
        mock_esi_client_factory
    ):
        load_entity(EveRegion)

        obj, created = EveRegion.objects.get_or_create_esi(10000005)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 10000005)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_region_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                        
        mock_client = Mock()        
        mock_client.Universe.get_universe_regions_region_id\
            .return_value.result.return_value = {
                "id": 10000005,
                "name": "Detorid"
            }
        mock_esi_client_factory.return_value = mock_client
        
        obj, created = EveRegion.objects.get_or_create_esi(10000005)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 10000005)
        self.assertIsInstance(EveRegion.objects.get(id=10000005), EveRegion)

    def test_eve_region_create_w_client(
        self
    ):                        
        mock_client = Mock()        
        mock_client.Universe.get_universe_regions_region_id\
            .return_value.result.return_value = {
                "id": 10000005,
                "name": "Detorid"
            }        
        
        obj, created = EveRegion.objects.get_or_create_esi(
            10000005, 
            mock_client
        )
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 10000005)
        self.assertIsInstance(EveRegion.objects.get(id=10000005), EveRegion)
    
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_region_create_failed(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_regions_region_id\
            .return_value.result.side_effect = RuntimeError()     
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveRegion.objects.get_or_create_esi(35832)


class TestEveConstellationManager(TestCase):

    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_constellation_get(
        self, 
        mock_esi_client_factory
    ):
        load_entity(EveRegion)
        load_entity(EveConstellation)

        obj, created = EveConstellation.objects.get_or_create_esi(20000069)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 20000069)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_constellation_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                        
        mock_client = Mock()        
        mock_client.Universe.get_universe_constellations_constellation_id\
            .return_value.result.return_value = {
                "id": 20000069,
                "name": "1RG-GU",
                "region_id": 10000005
            }
        mock_esi_client_factory.return_value = mock_client
        load_entity(EveRegion)

        obj, created = EveConstellation.objects.get_or_create_esi(10000005)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 10000005)
        self.assertIsInstance(
            EveConstellation.objects.get(id=10000005),
            EveConstellation
        )
    
    def test_eve_constellation_create_w_client(self):                        
        mock_client = Mock()        
        mock_client.Universe.get_universe_constellations_constellation_id\
            .return_value.result.return_value = {
                "id": 20000069,
                "name": "1RG-GU",
                "region_id": 10000005
            }        
        load_entity(EveRegion)

        obj, created = EveConstellation.objects.get_or_create_esi(
            10000005,
            mock_client
        )
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 10000005)
        self.assertIsInstance(
            EveConstellation.objects.get(id=10000005),
            EveConstellation
        )

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_constellation_create_failed(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_constellations_constellation_id\
            .return_value.result.side_effect = RuntimeError()
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveConstellation.objects.get_or_create_esi(10000005)


class TestEveSolarSystemManager(TestCase):
    
    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_solar_system_get(
        self, 
        mock_esi_client_factory
    ):        
        load_entities([
            EveCategory, 
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem
        ])

        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 30000474)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_solar_system_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                        
        mock_client = Mock()        
        mock_client.Universe.get_universe_systems_system_id\
            .return_value.result.return_value = {
                "id": 30000474,
                "name": "1-PGSG",
                "security_status": -0.496552765369415,
                "constellation_id": 20000069,
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
        mock_esi_client_factory.return_value = mock_client
        
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation          
        ])

        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 30000474)
        self.assertIsInstance(
            EveSolarSystem.objects.get(id=30000474), 
            EveSolarSystem
        )
        self.assertSetEqual(
            {x.id for x in EvePlanet.objects.filter(eve_solar_system=obj)},
            {40029526, 40029528, 40029529}
        )

    def test_eve_solar_system_create_w_client(self):                        
        mock_client = Mock()        
        mock_client.Universe.get_universe_systems_system_id\
            .return_value.result.return_value = {
                "id": 30000474,
                "name": "1-PGSG",
                "security_status": -0.496552765369415,
                "constellation_id": 20000069,
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
                
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation
        ])
                
        obj, created = EveSolarSystem.objects.get_or_create_esi(
            30000474,
            mock_client
        )
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 30000474)
        self.assertIsInstance(
            EveSolarSystem.objects.get(id=30000474), 
            EveSolarSystem
        )
        self.assertSetEqual(
            {x.id for x in EvePlanet.objects.filter(eve_solar_system=obj)},
            {40029526, 40029528, 40029529}
        )

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_solar_system_create_failed(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_systems_system_id\
            .return_value.result.side_effect = RuntimeError()
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveSolarSystem.objects.get_or_create_esi(30000474)


class TestEveMoonManager(TestCase):

    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_moon_get(
        self, 
        mock_esi_client_factory
    ):
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveMoon
        ])

        obj, created = EveMoon.objects.get_or_create_esi(40161465)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161465)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_moon_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                        
        mock_client = Mock()        
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
        mock_esi_client_factory.return_value = mock_client
                
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem          
        ])

        obj, created = EveMoon.objects.get_or_create_esi(40161465)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161465)
        self.assertIsInstance(
            EveMoon.objects.get(id=40161465), 
            EveMoon
        )        

    def test_eve_moon_create_w_client(self):                        
        mock_client = Mock()        
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
                
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem
        ])

        obj, created = EveMoon.objects.get_or_create_esi(
            40161465, 
            mock_client
        )
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161465)
        self.assertIsInstance(
            EveMoon.objects.get(id=40161465), 
            EveMoon
        )        

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_moon_create_failed(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_moons_moon_id\
            .return_value.result.side_effect = RuntimeError()  
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveMoon.objects.get_or_create_esi(40161465)


class TestEvePlanetManager(TestCase):

    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_planet_get(
        self, 
        mock_esi_client_factory
    ):        
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveMoon,
            EvePlanet
        ])

        obj, created = EvePlanet.objects.get_or_create_esi(40161469)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161469)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_planet_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                           
        mock_client = Mock()        
        mock_client.Universe.get_universe_planets_planet_id\
            .side_effect = esi_get_universe_planets_planet_id
        mock_esi_client_factory.return_value = mock_client
        
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem            
        ])        
        
        obj, created = EvePlanet.objects.get_or_create_esi(40161469)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161469)
        self.assertIsInstance(
            EvePlanet.objects.get(id=40161469), 
            EvePlanet
        )        

    def test_eve_planet_create_w_client(self):                           
        mock_client = Mock()        
        mock_client.Universe.get_universe_planets_planet_id\
            .side_effect = esi_get_universe_planets_planet_id
        
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem            
        ])

        obj, created = EvePlanet.objects.get_or_create_esi(
            40161469, 
            mock_client
        )
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161469)
        self.assertIsInstance(
            EvePlanet.objects.get(id=40161469), 
            EvePlanet
        )        

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_planet_create_failed(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_planets_planet_id\
            .return_value.result.side_effect = RuntimeError()
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EvePlanet.objects.get_or_create_esi(40161469)


class TestEveEntityManager(TestCase):

    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_entity_get(
        self, 
        mock_esi_client_factory
    ):        
        load_entity(EveEntity)

        obj, created = EveEntity.objects.get_or_create_esi(3011)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 3011)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_eve_entity_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                        
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

    def test_eve_entity_create_w_client(self):                        
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

    def test_eve_entity_create_w_client_no_match(self):                        
        mock_client = Mock()        
        mock_client.Universe.post_universe_names\
            .return_value.result.return_value = []      
        
        with self.assertRaises(ValueError):
            EveEntity.objects.get_or_create_esi(3011, mock_client)
        
    def test_eve_entity_create_w_client_wrong_type(self):                        
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
    def test_eve_entity_create_failed(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.post_universe_names\
            .return_value.result.side_effect = RuntimeError()
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveEntity.objects.get_or_create_esi(3011)


class TestStructureManager(TestCase):
            
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_structure_get(
        self, 
        mock_esi_client_factory
    ):                   
        mock_client = Mock()
        
        create_structures()        
        obj, created = Structure.objects.get_or_create_esi(
            1000000000001,
            mock_client
        )
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 1000000000001)

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_structure_create(
        self, 
        mock_esi_client_factory
    ):                        
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
    def test_structure_create_failed(
        self, 
        mock_esi_client_factory
    ):        
        x = Mock()
        x.result.side_effect = RuntimeError()
        mock_client = Mock()        
        mock_client.Universe.get_universe_structures_structure_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            Structure.objects.get_or_create_esi(1000000000001, mock_client)
