from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User, Permission 
from django.test import TestCase, RequestFactory
from django.urls import reverse

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo

from . import set_logger, load_testdata_entities
from ..models import *
from .. import views

logger = set_logger('structures.views', __file__)



class TestViews(TestCase):
    
    def setUp(self):        
        entities = load_testdata_entities()

        entities_def = [
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveMoon,
            EveGroup,
            EveType,
            EveAllianceInfo,
            EveCorporationInfo,
            EveCharacter,    
            EveEntity    
        ]
    
        for EntityClass in entities_def:
            entity_name = EntityClass.__name__
            for x in entities[entity_name]:
                EntityClass.objects.create(**x)
            assert(len(entities[entity_name]) == EntityClass.objects.count())
                
        for corporation in EveCorporationInfo.objects.all():
            EveEntity.objects.get_or_create(
                id = corporation.corporation_id,
                defaults={
                    'category': EveEntity.CATEGORY_CORPORATION,
                    'name': corporation.corporation_name
                }
            )
            Owner.objects.create(
                corporation=corporation
            )
            if int(corporation.corporation_id) in [2001, 2002]:
                alliance = EveAllianceInfo.objects.get(alliance_id=3001)
                corporation.alliance = alliance
                corporation.save()


        for character in EveCharacter.objects.all():
            EveEntity.objects.get_or_create(
                id = character.character_id,
                defaults={
                    'category': EveEntity.CATEGORY_CHARACTER,
                    'name': character.character_name
                }
            )
            corporation = EveCorporationInfo.objects.get(
                corporation_id=character.corporation_id
            )
            if corporation.alliance:                
                character.alliance_id = corporation.alliance.alliance_id
                character.alliance_name = corporation.alliance.alliance_name
                character.save()
               
        self.factory = RequestFactory()
        
        # 1 user
        self.character = EveCharacter.objects.get(character_id=1001)
                
        self.corporation = EveCorporationInfo.objects.get(
            corporation_id=self.character.corporation_id
        )
        self.user = User.objects.create_user(
            self.character.character_name,
            'abc@example.com',
            'password'
        )

        # user needs basic permission to access the app
        p = Permission.objects.get(
            codename='basic_access', 
            content_type__app_label='structures'
        )
        self.user.user_permissions.add(p)
        self.user.save()

        self.main_ownership = CharacterOwnership.objects.create(
            character=self.character,
            owner_hash='x1',
            user=self.user
        )
        self.user.profile.main_character = self.character
        
        self.owner = Owner.objects.get(
            corporation__corporation_id=self.character.corporation_id
        )
        self.owner.character = self.main_ownership


        for x in entities['Structure']:
            x['owner'] = Owner.objects.get(
                corporation__corporation_id=x['owner_corporation_id']
            )
            del x['owner_corporation_id']
            Structure.objects.create(**x)
        

    def test_basic_access_main_view(self):
        request = self.factory.get(reverse('structures:index'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
    
    def test_basic_access_own_structures_only(self):
                
        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        structure_ids = { x['structure_id'] for x in data }
        self.assertSetEqual(
            structure_ids, 
            {1000000000001}
        )
        

        """
        print('\nCorporations')
        print(EveCorporationInfo.objects.all().values())
        print('\nOwners')
        print(Owner.objects.all().values())
        print('\nStructures')
        print(Structure.objects.all().values())
        """

    def test_perm_view_alliance_structures_normal(self):
        
        # user needs permission to access view
        p = Permission.objects.get(
            codename='view_alliance_structures', 
            content_type__app_label='structures'
        )
        self.user.user_permissions.add(p)
        self.user.save()

        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))
        structure_ids = { x['structure_id'] for x in data }
        self.assertSetEqual(
            structure_ids, 
            {1000000000001, 1000000000002}
        )


    def test_perm_view_alliance_structures_no_alliance(self):
        # run with a user that is not a member of an alliance        
        character = EveCharacter.objects.get(character_id=1002)        
        user = User.objects.create_user(
            character.character_name,
            'abc@example.com',
            'password'
        )
        main_ownership = CharacterOwnership.objects.create(
            character=character,
            owner_hash='x2',
            user=user
        )
        user.profile.main_character = character
        
        # user needs permission to access view
        p = Permission.objects.get(
            codename='basic_access', 
            content_type__app_label='structures'
        )
        user.user_permissions.add(p)
        p = Permission.objects.get(
            codename='view_alliance_structures', 
            content_type__app_label='structures'
        )
        user.user_permissions.add(p)
        user.save()

        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))
        structure_ids = { x['structure_id'] for x in data }
        self.assertSetEqual(
            structure_ids, 
            {1000000000003}
        )
            

    def test_perm_view_all_structures(self):
        
        # user needs permission to access view
        p = Permission.objects.get(
            codename='view_all_structures', 
            content_type__app_label='structures'
        )
        self.user.user_permissions.add(p)
        self.user.save()

        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))
        structure_ids = { x['structure_id'] for x in data }
        self.assertSetEqual(
            structure_ids, 
            {1000000000001, 1000000000002, 1000000000003}
        )


    def test_view_add_structure_owner(self):
        
        # user needs permission to access view
        p = Permission.objects.get(
            codename='add_structure_owner', 
            content_type__app_label='structures'
        )
        self.user.user_permissions.add(p)
        self.user.save()

        request = self.factory.get(reverse('structures:add_structure_owner'))
        request.user = self.user
        response = views.index(request)
        self.assertEqual(response.status_code, 200)


    def test_view_service_status_ok(self):
                
        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 200)

    
    def test_view_service_status_fail(self):
                
        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_UNKNOWN
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_UNKNOWN
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_UNKNOWN
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now() - timedelta(
                minutes=STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES + 1
            )
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()- timedelta(
                minutes=STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES + 1
            )
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()- timedelta(
                minutes=STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES + 1
            )
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)


class TestManagers(TestCase):    
    
    def setUp(self):                
        self.entities = load_testdata_entities()

    def _load_entity(self, EntityClass):            
        entity_name = EntityClass.__name__        
        for x in self.entities[entity_name]:
            EntityClass.objects.create(**x)
        assert(len(self.entities[entity_name]) == EntityClass.objects.count())


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
        for x in self.entities['Structure']:
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

