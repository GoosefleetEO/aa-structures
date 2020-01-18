from unittest.mock import Mock, patch

from django.test import TestCase

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo

from . import set_logger
from .testdata import entities_testdata
from ..models import *


logger = set_logger('structures.managers', __file__)


class TestManagers(TestCase):    
    
    def _load_entity(self, EntityClass):            
        entity_name = EntityClass.__name__        
        for x in entities_testdata[entity_name]:
            EntityClass.objects.create(**x)
        assert(len(entities_testdata[entity_name]) == EntityClass.objects.count())


    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_group_get(
        self, 
        mock_esi_client_factory
    ):
        self._load_entity(EveGroup)
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 1657)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_group_create(
        self, 
        mock_esi_client_factory
    ):        
        x = Mock()
        x.result.return_value = {
            "id": 1657,
            "name": "Citadel"
        }        
        mock_client = Mock()        
        mock_client.Universe.get_universe_groups_group_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 1657)
        self.assertIsInstance(EveGroup.objects.get(id=1657), EveGroup)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_group_create_failed(
        self, 
        mock_esi_client_factory
    ):        
        x = Mock()
        x.result.side_effect = RuntimeError()
        mock_client = Mock()        
        mock_client.Universe.get_universe_groups_group_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveGroup.objects.get_or_create_esi(1657)
        

    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_type_get(
        self, 
        mock_esi_client_factory
    ):
        self._load_entity(EveGroup)
        self._load_entity(EveType)

        obj, created = EveType.objects.get_or_create_esi(35832)        
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 35832)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_type_create(
        self, 
        mock_esi_client_factory
    ):        
        x = Mock()
        x.result.return_value = {
            "id": 35832,
            "name": "Astrahus",
            "group_id": 1657
        }
        mock_client = Mock()        
        mock_client.Universe.get_universe_types_type_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        self._load_entity(EveGroup)
        
        obj, created = EveType.objects.get_or_create_esi(35832)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 35832)
        self.assertIsInstance(EveType.objects.get(id=35832), EveType)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_type_create_failed(
        self, 
        mock_esi_client_factory
    ):        
        x = Mock()
        x.result.side_effect = RuntimeError()
        mock_client = Mock()        
        mock_client.Universe.get_universe_types_type_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveType.objects.get_or_create_esi(35832)


    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_region_get(
        self, 
        mock_esi_client_factory
    ):
        self._load_entity(EveRegion)

        obj, created = EveRegion.objects.get_or_create_esi(10000005)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 10000005)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_region_create(
        self, 
        mock_esi_client_factory
    ):                
        x = Mock()
        x.result.return_value = {
            "id": 10000005,
            "name": "Detorid"
        }        
        mock_client = Mock()        
        mock_client.Universe.get_universe_regions_region_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        obj, created = EveRegion.objects.get_or_create_esi(10000005)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 10000005)
        self.assertIsInstance(EveRegion.objects.get(id=10000005), EveRegion)
        
    
    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_region_create_failed(
        self, 
        mock_esi_client_factory
    ):        
        x = Mock()
        x.result.side_effect = RuntimeError()
        mock_client = Mock()        
        mock_client.Universe.get_universe_regions_region_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveRegion.objects.get_or_create_esi(35832)


    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_constellation_get(
        self, 
        mock_esi_client_factory
    ):
        self._load_entity(EveRegion)
        self._load_entity(EveConstellation)

        obj, created = EveConstellation.objects.get_or_create_esi(20000069)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 20000069)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_constellation_create(
        self, 
        mock_esi_client_factory
    ):                
        x = Mock()
        x.result.return_value = {
            "id": 20000069,
            "name": "1RG-GU",
            "region_id": 10000005
        }        
        mock_client = Mock()        
        mock_client.Universe.get_universe_constellations_constellation_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        self._load_entity(EveRegion)

        obj, created = EveConstellation.objects.get_or_create_esi(10000005)
        
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
        x = Mock()
        x.result.side_effect = RuntimeError()
        mock_client = Mock()        
        mock_client.Universe.get_universe_constellations_constellation_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveConstellation.objects.get_or_create_esi(10000005)


    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_solar_system_get(
        self, 
        mock_esi_client_factory
    ):
        self._load_entity(EveRegion)
        self._load_entity(EveConstellation)
        self._load_entity(EveSolarSystem)

        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 30000474)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_solar_system_create(
        self, 
        mock_esi_client_factory
    ):                
        x = Mock()
        x.result.return_value = {
            "id": 30000474,
            "name": "1-PGSG",
            "security_status": -0.496552765369415,
            "constellation_id": 20000069
        }        
        mock_client = Mock()        
        mock_client.Universe.get_universe_systems_system_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        self._load_entity(EveRegion)
        self._load_entity(EveConstellation)

        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        
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
        x = Mock()
        x.result.side_effect = RuntimeError()
        mock_client = Mock()        
        mock_client.Universe.get_universe_systems_system_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveSolarSystem.objects.get_or_create_esi(30000474)


    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_moon_get(
        self, 
        mock_esi_client_factory
    ):
        self._load_entity(EveRegion)
        self._load_entity(EveConstellation)
        self._load_entity(EveSolarSystem)
        self._load_entity(EveMoon)

        obj, created = EveMoon.objects.get_or_create_esi(40161465)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161465)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_moon_create(
        self, 
        mock_esi_client_factory
    ):                
        x = Mock()
        x.result.return_value = {
            "id": 40161465,
            "name": "Amamake II - Moon 1",
            "system_id": 30002537,
            "position": {
                "x": 1,
                "y": 2,
                "z": 3
            }
        }        
        mock_client = Mock()        
        mock_client.Universe.get_universe_moons_moon_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        self._load_entity(EveRegion)
        self._load_entity(EveConstellation)
        self._load_entity(EveSolarSystem)

        obj, created = EveMoon.objects.get_or_create_esi(40161465)
        
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
        x = Mock()
        x.result.side_effect = RuntimeError()
        mock_client = Mock()        
        mock_client.Universe.get_universe_moons_moon_id\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveMoon.objects.get_or_create_esi(40161465)


    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_eve_entity_get(
        self, 
        mock_esi_client_factory
    ):        
        self._load_entity(EveEntity)

        obj, created = EveEntity.objects.get_or_create_esi(3011)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 3011)


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_entity_create(
        self, 
        mock_esi_client_factory
    ):                
        x = Mock()
        x.result.return_value = [
            {
                "id": 3011,
                "category": "alliance",
                "name": "Big Bad Alliance"
            }                
        ]
        mock_client = Mock()        
        mock_client.Universe.post_universe_names\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        obj, created = EveEntity.objects.get_or_create_esi(3011)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 3011)
        self.assertIsInstance(
            EveEntity.objects.get(id=3011), 
            EveEntity
        )        


    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_eve_entity_create_failed(
        self, 
        mock_esi_client_factory
    ):        
        x = Mock()
        x.result.side_effect = RuntimeError()
        mock_client = Mock()        
        mock_client.Universe.post_universe_names\
            .return_value = x        
        mock_esi_client_factory.return_value = mock_client
        
        with self.assertRaises(RuntimeError):
            EveEntity.objects.get_or_create_esi(3011)

        
    @patch('structures.managers.esi_client_factory', autospec=True)
    def test_structure_get(
        self, 
        mock_esi_client_factory
    ):                   
        mock_client = Mock()

        self._load_entity(EveRegion)
        self._load_entity(EveConstellation)
        self._load_entity(EveSolarSystem)
        self._load_entity(EveGroup)
        self._load_entity(EveType)
        self._load_entity(EveCorporationInfo)        
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
        x = Mock()
        x.result.return_value = {
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
        mock_client = Mock()        
        mock_client.Universe.get_universe_structures_structure_id\
            .return_value = x        
                
        self._load_entity(EveRegion)
        self._load_entity(EveConstellation)
        self._load_entity(EveSolarSystem)
        self._load_entity(EveGroup)
        self._load_entity(EveType)
        self._load_entity(EveCorporationInfo)
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

