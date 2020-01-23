from unittest.mock import Mock, patch

from django.test import TestCase

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo

from . import set_logger
from .testdata import entities_testdata, load_entity
from ..models import *


logger = set_logger('structures.managers', __file__)


class TestEveGroupManager(TestCase):
    
    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_group_get(
        self, 
        mock_esi_client_factory
    ):
        load_entity(EveGroup)
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 1657)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_group_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                
        mock_client = Mock()        
        mock_client.Universe.get_universe_groups_group_id\
            .return_value.result.return_value = {
                "id": 1657,
                "name": "Citadel"
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
                "name": "Citadel"
            }
        
        obj, created = EveGroup.objects.get_or_create_esi(
            1657, 
            mock_client
        )
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 1657)
        self.assertIsInstance(EveGroup.objects.get(id=1657), EveGroup)


    @patch('structures.managers.esi_client_factory', autospec=True)
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
        load_entity(EveGroup)
        load_entity(EveType)

        obj, created = EveType.objects.get_or_create_esi(35832)        
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 35832)


    @patch('structures.managers.esi_client_factory', autospec=True)
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
        
        load_entity(EveGroup)
        
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
        
        load_entity(EveGroup)
        
        obj, created = EveType.objects.get_or_create_esi(35832, mock_client)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 35832)
        self.assertIsInstance(EveType.objects.get(id=35832), EveType)


    @patch('structures.managers.esi_client_factory', autospec=True)
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


    @patch('structures.managers.esi_client_factory', autospec=True)
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
        
        obj, created = EveRegion.objects.get_or_create_esi(10000005, mock_client)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 10000005)
        self.assertIsInstance(EveRegion.objects.get(id=10000005), EveRegion)
        
    
    @patch('structures.managers.esi_client_factory', autospec=True)
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


    @patch('structures.managers.esi_client_factory', autospec=True)
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


    @patch('structures.managers.esi_client_factory', autospec=True)
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
        load_entity(EveRegion)
        load_entity(EveConstellation)
        load_entity(EveSolarSystem)

        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 30000474)


    @patch('structures.managers.esi_client_factory', autospec=True)
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
                "constellation_id": 20000069
            }      
        mock_esi_client_factory.return_value = mock_client
        
        load_entity(EveRegion)
        load_entity(EveConstellation)

        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 30000474)
        self.assertIsInstance(
            EveSolarSystem.objects.get(id=30000474), 
            EveSolarSystem
        )        


    def test_eve_solar_system_create_w_client(self):                        
        mock_client = Mock()        
        mock_client.Universe.get_universe_systems_system_id\
            .return_value.result.return_value = {
                "id": 30000474,
                "name": "1-PGSG",
                "security_status": -0.496552765369415,
                "constellation_id": 20000069
            }      
                
        load_entity(EveRegion)
        load_entity(EveConstellation)

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


    @patch('structures.managers.esi_client_factory', autospec=True)
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
        load_entity(EveRegion)
        load_entity(EveConstellation)
        load_entity(EveSolarSystem)
        load_entity(EveMoon)

        obj, created = EveMoon.objects.get_or_create_esi(40161465)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161465)


    @patch('structures.managers.esi_client_factory', autospec=True)
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
        
        load_entity(EveRegion)
        load_entity(EveConstellation)
        load_entity(EveSolarSystem)

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
        
        load_entity(EveRegion)
        load_entity(EveConstellation)
        load_entity(EveSolarSystem)

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


    @patch('structures.managers.esi_client_factory', autospec=True)
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
        load_entity(EveGroup)
        load_entity(EveType)
        load_entity(EveRegion)
        load_entity(EveConstellation)
        load_entity(EveSolarSystem)
        load_entity(EvePlanet)

        obj, created = EvePlanet.objects.get_or_create_esi(40161469)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161469)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_planet_create_wo_client(
        self, 
        mock_esi_client_factory
    ):                           
        mock_client = Mock()        
        mock_client.Universe.get_universe_planets_planet_id\
            .return_value.result.return_value = {
                "id": 40161469,
                "name": "Amamake IV",
                "system_id": 30002537,
                "position": {
                    "x": 1,
                    "y": 2,
                    "z": 3
                },
                "type_id": 2016,
            }
        mock_esi_client_factory.return_value = mock_client
        
        load_entity(EveGroup)
        load_entity(EveType)
        load_entity(EveRegion)
        load_entity(EveConstellation)
        load_entity(EveSolarSystem)
        
        obj, created = EvePlanet.objects.get_or_create_esi(40161469)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161469)
        self.assertIsInstance(
            EvePlanet.objects.get(id=40161469), 
            EvePlanet
        )        


    def test_eve_planet_create_wo_client(self):                           
        mock_client = Mock()        
        mock_client.Universe.get_universe_planets_planet_id\
            .return_value.result.return_value = {
                "id": 40161469,
                "name": "Amamake IV",
                "system_id": 30002537,
                "position": {
                    "x": 1,
                    "y": 2,
                    "z": 3
                },
                "type_id": 2016,
            }
        
        load_entity(EveGroup)
        load_entity(EveType)
        load_entity(EveRegion)
        load_entity(EveConstellation)
        load_entity(EveSolarSystem)
        
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


    @patch('structures.managers.esi_client_factory', autospec=True)
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


    @patch('structures.managers.esi_client_factory', autospec=True)
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

        
    @patch('structures.managers.esi_client_factory', autospec=True)
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
            
    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_structure_get(
        self, 
        mock_esi_client_factory
    ):                   
        mock_client = Mock()

        load_entity(EveRegion)
        load_entity(EveConstellation)
        load_entity(EveSolarSystem)
        load_entity(EveGroup)
        load_entity(EveType)
        load_entity(EveCorporationInfo)        
        owner = Owner.objects.create(
            corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        )
        for structure in entities_testdata['Structure']:
            x = structure.copy()
            x['owner'] = owner
            del x['owner_corporation_id']
            Structure.objects.create(**x)
        
        obj, created = Structure.objects.get_or_create_esi(
            1000000000001,
            mock_client
        )
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 1000000000001)

    
    @patch('structures.managers.esi_client_factory', autospec=True)
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
                
        load_entity(EveRegion)
        load_entity(EveConstellation)
        load_entity(EveSolarSystem)
        load_entity(EveGroup)
        load_entity(EveType)
        load_entity(EveCorporationInfo)
        owner = Owner.objects.create(
            corporation = EveCorporationInfo.objects.get(corporation_id=2001)
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


    @patch('structures.managers.esi_client_factory', autospec=True)
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

