from unittest.mock import Mock, patch

# from django.test import TestCase

from allianceauth.eveonline.models import EveCorporationInfo

from ..utils import set_test_logger
from .testdata import (
    load_entity, 
    load_entities,
    create_structures,     
    esi_mock_client
)
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
from ..utils import NoSocketsTestCase

MODULE_PATH = 'structures.managers'
logger = set_test_logger(MODULE_PATH, __file__)

DEFAULT_LANGUAGE_CODE = 'en-us'


class TestEveCategoryManager(NoSocketsTestCase):
    
    def setUp(self):
        EveCategory.objects.all().delete()

    @patch(MODULE_PATH + '.provider')
    def test_can_get_stored_object(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveCategory)
        
        obj, created = EveCategory.objects.get_or_create_esi(65)
        
        self.assertFalse(created)
        self.assertIsInstance(obj, EveCategory)
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')

    @patch(MODULE_PATH + '.settings.LANGUAGE_CODE', DEFAULT_LANGUAGE_CODE)
    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi(self, mock_provider):        
        mock_provider.client = esi_mock_client()

        obj, created = EveCategory.objects.update_or_create_esi(65)
        self.assertTrue(created)
        self.assertIsInstance(obj, EveCategory)
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')
        # self.assertEqual(obj.language_code, DEFAULT_LANGUAGE_CODE)

    @patch(MODULE_PATH + '.provider')
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

    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()

        obj, created = EveCategory.objects.get_or_create_esi(65)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveCategory)
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')
        
    @patch(MODULE_PATH + '.provider')
    def test_raises_exception_when_create_fails(self, mock_provider):
        mock_provider.client.Universe\
            .get_universe_categories_category_id.return_value\
            .result.side_effect = RuntimeError()
                
        with self.assertRaises(RuntimeError):
            EveCategory.objects.update_or_create_esi(65)


class TestEveGroupManager(NoSocketsTestCase):
    
    def setUp(self):
        load_entity(EveCategory)
    
    @patch(MODULE_PATH + '.provider')
    def test_can_get_stored_object(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveGroup)
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)                
        self.assertFalse(created)
        self.assertIsInstance(obj, EveGroup)
        self.assertEqual(obj.id, 1657)
        self.assertEqual(obj.name, 'Citadel')
        self.assertEqual(obj.eve_category_id, 65)

    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        
        obj, created = EveGroup.objects.get_or_create_esi(1657)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveGroup)
        self.assertEqual(obj.id, 1657)
        self.assertEqual(obj.name, 'Citadel')
        self.assertEqual(obj.eve_category_id, 65)

    @patch(MODULE_PATH + '.provider')
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

    @patch(MODULE_PATH + '.provider')
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

    def setUp(self):
        load_entities([EveCategory, EveGroup])

    @patch(MODULE_PATH + '.provider')
    def test_can_get_stored_object(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveType)
        
        obj, created = EveType.objects.get_or_create_esi(35832)                
        self.assertFalse(created)
        self.assertEqual(obj.id, 35832)

    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        
        obj, created = EveType.objects.get_or_create_esi(35832)        
        self.assertTrue(created)
        self.assertEqual(obj.id, 35832)
        self.assertIsInstance(EveType.objects.get(id=35832), EveType)

    @patch(MODULE_PATH + '.provider')
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

    @patch(MODULE_PATH + '.provider')
    def test_can_get_stored_object(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveRegion)

        obj, created = EveRegion.objects.get_or_create_esi(10000005)        
        self.assertFalse(created)
        self.assertEqual(obj.id, 10000005)

    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()                
        
        obj, created = EveRegion.objects.get_or_create_esi(10000005)        
        self.assertTrue(created)
        self.assertEqual(obj.id, 10000005)
        self.assertEqual(obj.name, 'Detorid')


class TestEveConstellationManager(NoSocketsTestCase):

    def setUp(self):
        load_entity(EveRegion)

    @patch(MODULE_PATH + '.provider')
    def test_can_get_stored_object(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveConstellation)

        obj, created = EveConstellation.objects.get_or_create_esi(20000069)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 20000069)
        self.assertEqual(obj.name, '1RG-GU')

    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        load_entity(EveRegion)

        obj, created = EveConstellation.objects.get_or_create_esi(20000069)
        self.assertTrue(created)
        self.assertEqual(obj.id, 20000069)
        self.assertEqual(obj.name, '1RG-GU')

    @patch(MODULE_PATH + '.provider')
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
    
    def setUp(self):
        load_entities([
            EveCategory, 
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation
        ])
    
    @patch(MODULE_PATH + '.provider')
    def test_can_get_stored_object(self, mock_provider):
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
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        
        obj, created = EveSolarSystem.objects.get_or_create_esi(30000474)
        self.assertTrue(created)
        self.assertIsInstance(obj, EveSolarSystem)
        self.assertEqual(obj.id, 30000474)
        self.assertEqual(obj.name, '1-PGSG')
        self.assertEqual(obj.security_status, -0.496552765369415)
        self.assertEqual(obj.eve_constellation_id, 20000069)
        
    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi_if_not_found_including_related(
        self, mock_provider
    ):
        mock_provider.client = esi_mock_client()
        EveConstellation.objects.get(id=20000069).delete()

        obj, created = EveSolarSystem.objects.get_or_create_esi(
            30000474, include_children=True
        )
        
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

    @patch(MODULE_PATH + '.provider')
    def test_can_update_object_from_esi_excluding_related(self, mock_provider):
        mock_provider.client = esi_mock_client()
        load_entity(EveSolarSystem)        
        obj = EveSolarSystem.objects.get(id=30000474)
        obj.name = 'Alpha'
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Alpha')

        obj_parent = EveConstellation.objects.get(id=20000069)
        obj_parent.name = 'Dark'
        obj_parent.save()
        obj_parent.refresh_from_db()
        self.assertEqual(obj_parent.name, 'Dark')

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
        obj_parent.refresh_from_db()
        self.assertEqual(obj_parent.name, 'Dark')
        obj_child.refresh_from_db()
        self.assertEqual(obj_child.name, 'Alpha I')

    @patch(MODULE_PATH + '.provider')
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

        obj, created = EveSolarSystem.objects.update_or_create_esi(
            30000474, update_children=True, include_children=True
        )
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 30000474)
        self.assertEqual(obj.name, '1-PGSG')        
        obj_child.refresh_from_db()
        self.assertEqual(obj_child.name, '1-PGSG I')
        

class TestEveMoonManager(NoSocketsTestCase):

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
    def test_can_get_stored_object(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EveMoon)

        obj, created = EveMoon.objects.get_or_create_esi(40161465)        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161465)

    @patch(MODULE_PATH + '.provider')
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
        
    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi_if_not_found_w_parent(self, mock_provider):
        mock_provider.client = esi_mock_client()
        EveSolarSystem.objects.get(id=30000474).delete()
        
        obj, created = EveMoon.objects.get_or_create_esi(40161465)
        self.assertTrue(created)
        self.assertEqual(obj.id, 40161465)
        
        obj_parent_1 = obj.eve_solar_system
        self.assertEqual(obj_parent_1.id, 30002537)


class TestEvePlanetManager(NoSocketsTestCase):

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
    def test_can_get_stored_object(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa
        load_entity(EvePlanet)

        obj, created = EvePlanet.objects.get_or_create_esi(40161469)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 40161469)

    @patch(MODULE_PATH + '.provider')
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
                
    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi_if_not_found_w_parent(self, mock_provider):
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


class TestEveEntityManager(NoSocketsTestCase):

    @patch(MODULE_PATH + '.provider')
    def test_can_get_stored_object(self, mock_provider):
        mock_provider = Mock(side_effect=RuntimeError)  # noqa     
        load_entity(EveEntity)

        obj, created = EveEntity.objects.get_or_create_esi(3011)
        
        self.assertFalse(created)
        self.assertEqual(obj.id, 3011)

    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()
        
        obj, created = EveEntity.objects.get_or_create_esi(3011)
        
        self.assertTrue(created)
        self.assertEqual(obj.id, 3011)
        self.assertEqual(obj.name, "Big Bad Alliance")

    @patch(MODULE_PATH + '.provider')
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

    @patch(MODULE_PATH + '.provider')
    def test_raises_exceptions_if_no_esi_match(self, mock_provider):
        mock_client = Mock()    
        mock_client.Universe.post_universe_names\
            .return_value.result.return_value = []
        mock_provider.client = mock_client
        
        with self.assertRaises(ValueError):
            EveEntity.objects.update_or_create_esi(3011)
        
    @patch(MODULE_PATH + '.provider')
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

    @patch(MODULE_PATH + '.provider')
    def test_can_create_object_from_esi_if_not_found(self, mock_provider):
        mock_provider.client = esi_mock_client()            
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
            1000000000001, mock_client
        )        
        self.assertTrue(created)
        self.assertEqual(obj.id, 1000000000001)
        self.assertEqual(obj.name, 'Test Structure Alpha')
        self.assertEqual(obj.eve_type_id, 35832)
        self.assertEqual(obj.eve_solar_system_id, 30002537)
        self.assertEqual(int(obj.owner.corporation.corporation_id), 2001)
        self.assertEqual(obj.position_x, 1)
        self.assertEqual(obj.position_y, 2)
        self.assertEqual(obj.position_z, 3)

    @patch(MODULE_PATH + '.provider')
    def test_can_update_object_from_esi(self, mock_provider):
        mock_provider.client = esi_mock_client()            
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
        create_structures()
        obj = Structure.objects.get(id=1000000000001)
        obj.name = 'Batcave'
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Batcave')
        
        obj, created = Structure.objects.update_or_create_esi(
            1000000000001, mock_client
        )        
        self.assertFalse(created)
        self.assertEqual(obj.id, 1000000000001)
        self.assertEqual(obj.name, 'Test Structure Alpha')
        
    @patch(MODULE_PATH + '.provider')
    def test_raises_exception_when_create_fails(self, mock_provider):        
        mock_provider = Mock(side_effect=RuntimeError)  # noqa        
        mock_client = Mock()        
        mock_client.Universe.get_universe_structures_structure_id\
            .return_value.result.side_effect = RuntimeError()
                
        with self.assertRaises(RuntimeError):
            Structure.objects.update_or_create_esi(
                1000000000001, mock_client
            )

    def test_raises_exception_when_create_without_esi_client(self):
        with self.assertRaises(ValueError):
            obj, created = Structure.objects.update_or_create_esi(987, None)
