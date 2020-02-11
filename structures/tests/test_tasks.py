from unittest.mock import Mock, patch

from bravado.exception import HTTPBadGateway

from django.contrib.auth.models import User, Permission 
from django.test import TestCase

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.timerboard.models import Timer
from esi.errors import TokenExpiredError, TokenInvalidError

from . import set_logger
from .. import tasks
from ..models import (
    EveCategory,
    EveGroup,
    EveType,
    EveRegion,
    EveConstellation,
    EveSolarSystem,
    EveMoon,
    EvePlanet,
    StructureTag,
    StructureService,
    Webhook,    
    Owner,
    Notification,
    Structure,
    NTYPE_OWNERSHIP_TRANSFERRED,
    NTYPE_STRUCTURE_ANCHORING,
    NTYPE_STRUCTURE_DESTROYED,
    NTYPE_STRUCTURE_FUEL_ALERT,
    NTYPE_STRUCTURE_LOST_ARMOR,
    NTYPE_STRUCTURE_LOST_SHIELD,
    NTYPE_STRUCTURE_ONLINE,
    NTYPE_STRUCTURE_SERVICES_OFFLINE,
    NTYPE_STRUCTURE_UNANCHORING,
    NTYPE_STRUCTURE_UNDER_ATTACK,
    NTYPE_STRUCTURE_WENT_HIGH_POWER,
    NTYPE_STRUCTURE_WENT_LOW_POWER,
    NTYPE_MOONS_AUTOMATIC_FRACTURE,
    NTYPE_MOONS_EXTRACTION_CANCELED,
    NTYPE_MOONS_EXTRACTION_FINISHED,
    NTYPE_MOONS_EXTRACTION_STARTED,
    NTYPE_MOONS_LASER_FIRED
)

from .testdata import \
    esi_get_corporations_corporation_id_structures, \
    esi_get_corporations_corporation_id_starbases, \
    esi_get_universe_structures_structure_id, \
    esi_get_characters_character_id_notifications, \
    esi_get_corporations_corporation_id_customs_offices, \
    esi_post_corporations_corporation_id_assets_locations, \
    esi_post_corporations_corporation_id_assets_names, \
    entities_testdata,\
    esi_corp_structures_data,\
    load_entities,\
    load_notification_entities,\
    get_all_notification_ids,\
    create_structures,\
    set_owner_character


MODULE_PATH = 'structures.tasks'
logger = set_logger(MODULE_PATH, __file__)


def _get_invalid_owner_pk():
    owner_pks = [x.pk for x in Owner.objects.all()]
    if owner_pks:
        return max(owner_pks) + 1
    else:
        return 99


class TestSyncStructures(TestCase):
    
    # note: setup is making calls to ESI to get full info for entities
    # all ESI calls in the tested module are mocked though

    def setUp(self):            
        # reset data that might be overridden
        esi_get_corporations_corporation_id_structures.override_data = None
        esi_get_corporations_corporation_id_customs_offices.override_data = \
            None
        
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,            
            EvePlanet,
            EveMoon,
            EveCorporationInfo,
            EveCharacter,            
        ])
            
        # 1 user
        self.character = EveCharacter.objects.get(character_id=1001)
                
        self.corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        self.user = User.objects.create_user(
            self.character.character_name,
            'abc@example.com',
            'password'
        )

        self.main_ownership = CharacterOwnership.objects.create(
            character=self.character,
            owner_hash='x1',
            user=self.user
        )        
        Structure.objects.all().delete()
        
        # create StructureTag objects
        StructureTag.objects.all().delete()
        for x in entities_testdata['StructureTag']:
            StructureTag.objects.create(**x)
    
    def test_run_unknown_owner(self):                                
        with self.assertRaises(Owner.DoesNotExist):
            tasks.update_structures_for_owner(owner_pk=_get_invalid_owner_pk())

    # run without char        
    def test_run_no_sync_char(self):
        owner = Owner.objects.create(
            corporation=self.corporation            
        )
        self.assertFalse(
            tasks.update_structures_for_owner(owner_pk=owner.pk)
        )
        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_NO_CHARACTER
        )

    # test expired token    
    @patch(MODULE_PATH + '.Token')    
    def test_check_expired_token(
            self,             
            mock_Token
    ):                        
        mock_Token.objects.filter.side_effect = TokenExpiredError()        
                        
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )
        
        # run update task
        self.assertFalse(
            tasks.update_structures_for_owner(owner_pk=owner.pk)
        )

        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_TOKEN_EXPIRED            
        )
    
    # test invalid token    
    @patch(MODULE_PATH + '.Token')
    def test_check_invalid_token(
            self,             
            mock_Token
    ):
        mock_Token.objects.filter.side_effect = TokenInvalidError()
                        
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )
        
        # run update task
        self.assertFalse(
            tasks.update_structures_for_owner(owner_pk=owner.pk)
        )

        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_TOKEN_INVALID            
        )
        
    # normal synch of new structures, mode my_alliance
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', True)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_update_structures_for_owner_normal(
        self, 
        mock_esi_client_factory,             
        mock_Token,
        mock_notify
    ):                               
        mock_client = Mock()        
        mock_client.Corporation\
            .get_corporations_corporation_id_structures.side_effect = \
            esi_get_corporations_corporation_id_structures
        mock_client.Corporation\
            .get_corporations_corporation_id_starbases.side_effect = \
            esi_get_corporations_corporation_id_starbases
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id
        mock_client.Planetary_Interaction\
            .get_corporations_corporation_id_customs_offices = \
            esi_get_corporations_corporation_id_customs_offices
        mock_client.Assets\
            .post_corporations_corporation_id_assets_locations = \
            esi_post_corporations_corporation_id_assets_locations
        mock_client.Assets\
            .post_corporations_corporation_id_assets_names = \
            esi_post_corporations_corporation_id_assets_names
        mock_esi_client_factory.return_value = mock_client

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )
        
        # run update task
        self.assertTrue(
            tasks.update_structures_for_owner(
                owner_pk=owner.pk, 
                user_pk=self.user.pk
            )
        )
        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_NONE            
        )        
        # should have tried to fetch structures
        self.assertEqual(
            mock_client.Corporation
                .get_corporations_corporation_id_structures.call_count,  # noqa: E502, E501
            2
        )                
        # must contain all expected structures
        self.assertSetEqual(
            {x['id'] for x in Structure.objects.values('id')},
            {
                1000000000001, 
                1000000000002, 
                1000000000003, 
                1200000000003,
                1200000000004,
                1200000000005,
                1300000000001,
                1300000000002,
            }
        )
        # must have created services
        structure = Structure.objects.get(id=1000000000001)        
        self.assertEqual(
            {
                x.name 
                for x in StructureService.objects.filter(structure=structure)
            },
            {'Clone Bay', 'Market Hub'}
        )
        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(
            structure.name,
            'Planet (Barren)'
        )
        
        # user report has been sent
        self.assertTrue(mock_notify.called)
    
    # synch of structures, ensure old structures are removed
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_update_structures_for_owner_remove_olds(
        self, 
        mock_esi_client_factory,             
        mock_Token
    ):                       
        mock_client = Mock()        
        mock_client.Corporation\
            .get_corporations_corporation_id_structures.side_effect = \
            esi_get_corporations_corporation_id_structures
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id
        mock_esi_client_factory.return_value = mock_client

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )        
        
        # run update task with all structures
        tasks.update_structures_for_owner(
            owner_pk=owner.pk
        )        
        # should contain the right structures
        self.assertSetEqual(
            {x['id'] for x in Structure.objects.values('id')},
            {1000000000001, 1000000000002, 1000000000003}
        )

        # run update task 2nd time with one less structure
        my_corp_structures_data = esi_corp_structures_data.copy()
        del(my_corp_structures_data["2001"][1])
        esi_get_corporations_corporation_id_structures.override_data = \
            my_corp_structures_data
        tasks.update_structures_for_owner(
            owner_pk=owner.pk
        )        
        # should contain only the remaining structure
        self.assertSetEqual(
            {x['id'] for x in Structure.objects.values('id')},
            {1000000000002, 1000000000003}
        )
    
    # synch of structures, ensure tags are not removed
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_update_structures_for_owner_keep_tags(
        self, 
        mock_esi_client_factory,             
        mock_Token
    ):                       
        mock_client = Mock()        
        mock_client.Corporation\
            .get_corporations_corporation_id_structures.side_effect = \
            esi_get_corporations_corporation_id_structures
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id
        mock_esi_client_factory.return_value = mock_client

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )        
        
        # run update task with all structures
        tasks.update_structures_for_owner(
            owner_pk=owner.pk
        )        
        # should contain the right structures
        self.assertSetEqual(
            {x['id'] for x in Structure.objects.values('id')},
            {1000000000001, 1000000000002, 1000000000003}
        )

        # adding tags
        tag_a = StructureTag.objects.get(name='tag_a')
        s = Structure.objects.get(id=1000000000001)
        s.tags.add(tag_a)
        s.save()
        
        # run update task 2nd time
        tasks.update_structures_for_owner(
            owner_pk=owner.pk
        )        
        # should still contain alls structures
        self.assertSetEqual(
            {x['id'] for x in Structure.objects.values('id')},
            {1000000000001, 1000000000002, 1000000000003}
        )
        # should still contain the tag
        s_new = Structure.objects.get(id=1000000000001)
        self.assertEqual(s_new.tags.get(name='tag_a'), tag_a)
    
    # no structures retrieved from ESI during sync
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_update_structures_for_owner_empty_and_no_user_report(
        self, 
        mock_esi_client_factory,             
        mock_Token
    ):                               
        mock_client = Mock()        
        mock_client.Corporation\
            .get_corporations_corporation_id_structures.side_effect = \
            esi_get_corporations_corporation_id_structures
        esi_get_corporations_corporation_id_structures.override_data = \
            {'2001': []}
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id        
        mock_client.Planetary_Interaction\
            .get_corporations_corporation_id_customs_offices = \
            esi_get_corporations_corporation_id_customs_offices
        esi_get_corporations_corporation_id_customs_offices.override_data = \
            {'2001': []}
        mock_client.Assets\
            .post_corporations_corporation_id_assets_locations = \
            esi_post_corporations_corporation_id_assets_locations
        mock_client.Assets\
            .post_corporations_corporation_id_assets_names = \
            esi_post_corporations_corporation_id_assets_names
        mock_esi_client_factory.return_value = mock_client

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )
        
        # run update task
        self.assertTrue(
            tasks.update_structures_for_owner(
                owner_pk=owner.pk
            )
        )
        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_NONE            
        )                
        # must be empty
        self.assertEqual(Structure.objects.count(), 0)

    # error during user report
    @patch(MODULE_PATH + '.settings.DEBUG', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.notify')
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_update_structures_for_owner_user_report_error(
        self, 
        mock_esi_client_factory,             
        mock_Token,
        mock_notify
    ):                               
        mock_client = Mock()        
        mock_client.Corporation\
            .get_corporations_corporation_id_structures.side_effect = \
            esi_get_corporations_corporation_id_structures
        esi_get_corporations_corporation_id_structures.override_data = \
            {'2001': []}
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id        
        mock_client.Planetary_Interaction\
            .get_corporations_corporation_id_customs_offices = \
            esi_get_corporations_corporation_id_customs_offices
        esi_get_corporations_corporation_id_customs_offices.override_data = \
            {'2001': []}
        mock_client.Assets\
            .post_corporations_corporation_id_assets_locations = \
            esi_post_corporations_corporation_id_assets_locations
        mock_client.Assets\
            .post_corporations_corporation_id_assets_names = \
            esi_post_corporations_corporation_id_assets_names
        mock_esi_client_factory.return_value = mock_client
        mock_notify.side_effect = RuntimeError    

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )
        
        # run update task
        self.assertTrue(
            tasks.update_structures_for_owner(
                owner_pk=owner.pk,
                user_pk=self.user.pk
            )
        )       

    # synch of structures, ensure services are removed correctly
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_update_structures_for_owner_remove_services(
        self, 
        mock_esi_client_factory,             
        mock_Token
    ):                       
        mock_client = Mock()        
        mock_client.Corporation\
            .get_corporations_corporation_id_structures.side_effect = \
            esi_get_corporations_corporation_id_structures
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id
        mock_esi_client_factory.return_value = mock_client

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )        
        
        # run update task with all structures
        tasks.update_structures_for_owner(
            owner_pk=owner.pk, 
            user_pk=self.user.pk
        )                        
        structure = Structure.objects.get(id=1000000000002)        
        self.assertEqual(
            {
                x.name 
                for x in StructureService.objects.filter(structure=structure)
            },
            {'Reprocessing', 'Moon Drilling'}
        )
        
        # run update task 2nd time after removing a service
        my_corp_structures_data = esi_corp_structures_data.copy()
        del(my_corp_structures_data['2001'][0]['services'][0])
        esi_get_corporations_corporation_id_structures.override_data = \
            my_corp_structures_data
        tasks.update_structures_for_owner(
            owner_pk=owner.pk, 
            user_pk=self.user.pk
        )        
        # should contain only the remaining service
        structure.refresh_from_db()
        self.assertEqual(
            {
                x.name 
                for x in StructureService.objects.filter(structure=structure)
            },
            {'Moon Drilling'}
        )

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_update_pocos_no_planet_match(
        self,         
        mock_esi_client_factory,
        mock_Token,
        mock_notify
    ):                               
        mock_client = Mock()        
        mock_client.Corporation\
            .get_corporations_corporation_id_structures.side_effect = \
            esi_get_corporations_corporation_id_structures
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id        
        mock_client.Planetary_Interaction\
            .get_corporations_corporation_id_customs_offices = \
            esi_get_corporations_corporation_id_customs_offices
        mock_client.Assets\
            .post_corporations_corporation_id_assets_locations = \
            esi_post_corporations_corporation_id_assets_locations
        mock_client.Assets\
            .post_corporations_corporation_id_assets_names = \
            esi_post_corporations_corporation_id_assets_names
        mock_esi_client_factory.return_value = mock_client

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )

        EvePlanet.objects.all().delete()
        
        # run update task
        self.assertTrue(
            tasks.update_structures_for_owner(
                owner_pk=owner.pk, 
                user_pk=self.user.pk
            )
        )

        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(
            structure.name,
            'Amamake V'
        )

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_update_pocos_no_asset_name_match(
        self,         
        mock_esi_client_factory,
        mock_Token,
        mock_notify
    ):                               
        mock_client = Mock()        
        mock_client.Corporation\
            .get_corporations_corporation_id_structures.side_effect = \
            esi_get_corporations_corporation_id_structures
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id        
        mock_client.Planetary_Interaction\
            .get_corporations_corporation_id_customs_offices = \
            esi_get_corporations_corporation_id_customs_offices
        mock_client.Assets\
            .post_corporations_corporation_id_assets_locations = \
            esi_post_corporations_corporation_id_assets_locations
        mock_client.Assets\
            .post_corporations_corporation_id_assets_names = \
            esi_post_corporations_corporation_id_assets_names
        mock_esi_client_factory.return_value = mock_client

        esi_post_corporations_corporation_id_assets_names.override_data = {
            "2001": []
        }
        
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )

        EvePlanet.objects.all().delete()
        
        # run update task
        self.assertTrue(
            tasks.update_structures_for_owner(
                owner_pk=owner.pk, 
                user_pk=self.user.pk
            )
        )
        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(
            structure.name,
            ''
        )
        esi_post_corporations_corporation_id_assets_names.override_data = None

    # catch exception during storing of structures
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Structure.objects.update_or_create_from_dict')
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_storing_structures_error(
        self, 
        mock_esi_client_factory,             
        mock_Token,
        mock_update_or_create_from_dict
    ):                       
        mock_client = Mock()        
        mock_client.Corporation\
            .get_corporations_corporation_id_structures.side_effect = \
            esi_get_corporations_corporation_id_structures
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id
        mock_esi_client_factory.return_value = mock_client

        mock_update_or_create_from_dict.side_effect = RuntimeError

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )        
        
        # run update task with all structures        
        self.assertFalse(tasks.update_structures_for_owner(
            owner_pk=owner.pk
        ))

    @patch(MODULE_PATH + '.update_structures_for_owner')
    def test_update_all_structures(self, mock_update_structures_for_owner):
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        owner_2002 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002)
        )
        tasks.update_all_structures()
        self.assertEqual(mock_update_structures_for_owner.delay.call_count, 2)
        call_args_list = mock_update_structures_for_owner.delay.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)
        args, kwargs = call_args_list[1]
        self.assertEqual(args[0], owner_2002.pk)
    
    @patch(MODULE_PATH + '.update_structures_for_owner')
    def test_update_all_structures_not_active(
        self, mock_update_structures_for_owner
    ):
        """test that non active owners are not synced"""
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001),
            is_active=True
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            is_active=False
        )
        tasks.update_all_structures()
        self.assertEqual(mock_update_structures_for_owner.delay.call_count, 1)
        call_args_list = mock_update_structures_for_owner.delay.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)        


class TestSyncNotifications(TestCase):    

    def setUp(self): 
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)        
                
    def test_run_unknown_owner(self):
        with self.assertRaises(Owner.DoesNotExist):
            tasks.fetch_notifications_for_owner(
                owner_pk=_get_invalid_owner_pk()
            )
   
    # run without char        
    def test_run_no_sync_char(self):        
        my_owner = Owner.objects.get(corporation__corporation_id=2002)
        self.assertFalse(
            tasks.fetch_notifications_for_owner(owner_pk=my_owner.pk)
        )
        my_owner.refresh_from_db()
        self.assertEqual(
            my_owner.notifications_last_error, 
            Owner.ERROR_NO_CHARACTER
        )
    
    # test expired token    
    @patch(MODULE_PATH + '.Token')    
    def test_check_expired_token(
        self,             
        mock_Token
    ):                        
        mock_Token.objects.filter.side_effect = TokenExpiredError()        
                        
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
                
        # run update task
        self.assertFalse(
            tasks.fetch_notifications_for_owner(owner_pk=self.owner.pk)
        )

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, 
            Owner.ERROR_TOKEN_EXPIRED            
        )
    
    # test invalid token    
    @patch(MODULE_PATH + '.Token')
    def test_check_invalid_token(
        self,             
        mock_Token
    ):                        
        mock_Token.objects.filter.side_effect = TokenInvalidError()
         
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
                
        # run update task
        self.assertFalse(
            tasks.fetch_notifications_for_owner(owner_pk=self.owner.pk)
        )

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, 
            Owner.ERROR_TOKEN_INVALID            
        )
        
    # normal synch of new structures, mode my_alliance                    
    @patch(
        'structures.models.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED', 
        False
    )
    @patch(MODULE_PATH + '.STRUCTURES_ADD_TIMERS', True)    
    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_fetch_notifications_for_owner_normal(
            self, 
            mock_esi_client_factory,             
            mock_Token,
            mock_notify
    ):        
        mock_client = Mock()       
        mock_client.Character\
            .get_characters_character_id_notifications.side_effect =\
            esi_get_characters_character_id_notifications
        mock_esi_client_factory.return_value = mock_client

        # create test data
        Timer.objects.all().delete()
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
                
        # run update task
        self.assertTrue(
            tasks.fetch_notifications_for_owner(
                owner_pk=self.owner.pk,
                user_pk=self.user.pk
            )
        )
        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, 
            Owner.ERROR_NONE            
        )                
        # should only contain the right notifications
        notification_ids = {
            x['notification_id'] 
            for x in Notification.objects.values('notification_id')
        }
        self.assertSetEqual(
            notification_ids,
            get_all_notification_ids()
        )
        # user report has been sent
        self.assertTrue(mock_notify.called)
        
        # should have added timers
        self.assertEqual(Timer.objects.count(), 5)

        # run sync again
        self.assertTrue(
            tasks.fetch_notifications_for_owner(
                owner_pk=self.owner.pk
            )
        )

        # should not have more timers
        self.assertEqual(Timer.objects.count(), 5)
        
    @patch(MODULE_PATH + '.STRUCTURES_ADD_TIMERS', False)        
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_fetch_notifications_for_owner_esi_error(
            self, 
            mock_esi_client_factory,             
            mock_Token
    ):
        # create mocks        
        def get_characters_character_id_notifications_error(*args, **kwargs):
            mock_response = Mock()
            mock_response.status_code = None
            raise HTTPBadGateway(mock_response)
        
        mock_client = Mock()       
        mock_client.Character\
            .get_characters_character_id_notifications.side_effect =\
            get_characters_character_id_notifications_error
        mock_esi_client_factory.return_value = mock_client

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
                
        # run update task
        self.assertFalse(
            tasks.fetch_notifications_for_owner(owner_pk=self.owner.pk)
        )

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, 
            Owner.ERROR_UNKNOWN
        )

    @patch(MODULE_PATH + '.STRUCTURES_ADD_TIMERS', False)
    @patch(MODULE_PATH + '.fetch_notifications_for_owner')
    def test_fetch_all_notifications(
        self, 
        mock_fetch_notifications_owner
    ):
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        owner_2002 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002)
        )
        tasks.fetch_all_notifications()
        self.assertEqual(
            mock_fetch_notifications_owner.delay.call_count, 2
        )
        call_args_list = mock_fetch_notifications_owner.delay.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)
        args, kwargs = call_args_list[1]
        self.assertEqual(args[0], owner_2002.pk)

    @patch(MODULE_PATH + '.STRUCTURES_ADD_TIMERS', False)
    @patch(MODULE_PATH + '.fetch_notifications_for_owner')
    def test_fetch_all_notifications_not_active(
        self, 
        mock_fetch_notifications_owner
    ):
        """test that not active owners are not synced"""
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001),
            is_active=True
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            is_active=False
        )
        tasks.fetch_all_notifications()
        self.assertEqual(mock_fetch_notifications_owner.delay.call_count, 1)
        call_args_list = mock_fetch_notifications_owner.delay.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)        


class TestForwardNotifications(TestCase):    

    def setUp(self):         
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        self.owner.is_alliance_main = True
        self.owner.save()

        load_notification_entities(self.owner)
    
    def test_run_unknown_owner(self):      
        with self.assertRaises(Owner.DoesNotExist):
            tasks.send_new_notifications_for_owner(
                owner_pk=_get_invalid_owner_pk()
            )

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(MODULE_PATH + '.Notification.send_to_webhook', autospec=True)
    def test_run_no_sync_char(
        self,         
        mock_esi_client_factory,
        mock_send_to_webhook,
        mock_token
    ):    
        self.owner.character = None
        self.owner.save()

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        
        self.assertFalse(
            tasks.send_new_notifications_for_owner(
                self.owner.pk, 
                rate_limited=False
            )
        )
        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.forwarding_last_error, 
            Owner.ERROR_NO_CHARACTER
        )

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(MODULE_PATH + '.Notification.send_to_webhook', autospec=True)
    def test_check_expired_token(
        self,         
        mock_esi_client_factory,
        mock_send_to_webhook,
        mock_token
    ):  
        mock_token.objects.filter.side_effect = TokenExpiredError()        
                        
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
                
        # run update task
        self.assertFalse(
            tasks.send_new_notifications_for_owner(
                self.owner.pk, 
                rate_limited=False
            )
        )
        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.forwarding_last_error, 
            Owner.ERROR_TOKEN_EXPIRED            
        )

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(MODULE_PATH + '.Notification.send_to_webhook', autospec=True)
    def test_check_invalid_token(
        self,         
        mock_esi_client_factory,
        mock_send_to_webhook,
        mock_token
    ):   
        mock_token.objects.filter.side_effect = TokenInvalidError()
                        
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
                
        # run update task
        self.assertFalse(
            tasks.send_new_notifications_for_owner(
                self.owner.pk, 
                rate_limited=False
            )
        )
        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.forwarding_last_error, 
            Owner.ERROR_TOKEN_INVALID            
        )

    @patch('structures.models.STRUCTURES_REPORT_NPC_ATTACKS', True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(MODULE_PATH + '.Notification.send_to_webhook', autospec=True)
    def test_send_new_notifications_normal_with_NPCs(
        self, 
        mock_send_to_webhook, 
        mock_esi_client_factory,
        mock_token
    ):
        logger.debug('test_send_new_notifications_normal')
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        
        tasks.send_all_new_notifications(rate_limited=False)
        
        tested_notification_ids = set()
        for x in mock_send_to_webhook.call_args_list:
            args, kwargs = x
            tested_notification_ids.add(args[0].notification_id)

        self.assertSetEqual(
            get_all_notification_ids(),
            tested_notification_ids
        )

    @patch('structures.models.STRUCTURES_REPORT_NPC_ATTACKS', False)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(MODULE_PATH + '.Notification.send_to_webhook', autospec=True)
    def test_send_new_notifications_normal_wo_NPCs(
        self, 
        mock_send_to_webhook, 
        mock_esi_client_factory,
        mock_token
    ):
        logger.debug('test_send_new_notifications_normal')
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        
        tasks.send_all_new_notifications(rate_limited=False)
        
        tested_notification_ids = set()
        for x in mock_send_to_webhook.call_args_list:
            args, kwargs = x
            tested_notification_ids.add(args[0].notification_id)

        all_notification_ids_wo_npcs = get_all_notification_ids()
        all_notification_ids_wo_npcs.remove(1000010601)
        all_notification_ids_wo_npcs.remove(1000010509)
        self.assertSetEqual(
            all_notification_ids_wo_npcs,
            tested_notification_ids
        )

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch('structures.models.Notification.send_to_webhook', autospec=True)    
    def test_send_new_notifications_to_multiple_webhooks(
        self, 
        mock_send_to_webhook, 
        mock_esi_client_factory,
        mock_token
    ):
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()

        notification_types = ','.join([str(x) for x in [
            NTYPE_OWNERSHIP_TRANSFERRED,
            NTYPE_STRUCTURE_ANCHORING,
            NTYPE_STRUCTURE_DESTROYED,
            NTYPE_STRUCTURE_FUEL_ALERT,
            NTYPE_STRUCTURE_LOST_ARMOR,
            NTYPE_STRUCTURE_LOST_SHIELD,
            NTYPE_STRUCTURE_ONLINE,
            NTYPE_STRUCTURE_SERVICES_OFFLINE,
            NTYPE_STRUCTURE_UNANCHORING,
            NTYPE_STRUCTURE_UNDER_ATTACK,
            NTYPE_STRUCTURE_WENT_HIGH_POWER,
            NTYPE_STRUCTURE_WENT_LOW_POWER
        ]])
        wh_structures = Webhook.objects.create(
            name='Structures',
            url='dummy-url-1',
            notification_types=notification_types
        )

        notification_types = ','.join([str(x) for x in [
            NTYPE_MOONS_AUTOMATIC_FRACTURE,
            NTYPE_MOONS_EXTRACTION_CANCELED,
            NTYPE_MOONS_EXTRACTION_FINISHED,
            NTYPE_MOONS_EXTRACTION_STARTED,
            NTYPE_MOONS_LASER_FIRED
        ]])
        wh_mining = Webhook.objects.create(
            name='Mining',
            url='dummy-url-2',
            notification_types=notification_types
        )

        self.owner.webhooks.clear()
        self.owner.webhooks.add(wh_structures)
        self.owner.webhooks.add(wh_mining)
        
        tasks.send_all_new_notifications(rate_limited=False)
        results = {            
            wh_mining.pk: set(),
            wh_structures.pk: set()
        }
        for x in mock_send_to_webhook.call_args_list:
            first = x[0]
            notification = first[0]
            hook = first[1]
            results[hook.pk].add(notification.notification_id)

        self.assertSetEqual(
            results[wh_mining.pk],
            {
                1000000401,
                1000000402,
                1000000403,
                1000000404,
                1000000405
            }
        )

        self.assertSetEqual(
            results[wh_structures.pk],
            {
                1000000501,
                1000000502,
                1000000503,
                1000000504,
                1000000505,
                1000000506,
                1000000507,
                1000000508,
                1000000509,
                1000000510,
                1000000511,
                1000000513,
                1000010509
            }
        )

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch('structures.models.Notification.send_to_webhook', autospec=True)    
    def test_send_new_notifications_to_multiple_webhooks_2(
        self, 
        mock_send_to_webhook, 
        mock_esi_client_factory,
        mock_token
    ):
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()

        notification_types_1 = ','.join([str(x) for x in sorted([            
            NTYPE_MOONS_EXTRACTION_CANCELED,
            NTYPE_STRUCTURE_DESTROYED,            
            NTYPE_STRUCTURE_LOST_ARMOR,
            NTYPE_STRUCTURE_LOST_SHIELD,            
            NTYPE_STRUCTURE_UNDER_ATTACK
        ])])
        wh_structures = Webhook.objects.create(
            name='Structures',
            url='dummy-url-1',
            notification_types=notification_types_1,
            is_active=True
        )

        notification_types_2 = ','.join([str(x) for x in sorted([
            NTYPE_MOONS_EXTRACTION_CANCELED,
            NTYPE_MOONS_AUTOMATIC_FRACTURE,            
            NTYPE_MOONS_EXTRACTION_FINISHED,
            NTYPE_MOONS_EXTRACTION_STARTED,
            NTYPE_MOONS_LASER_FIRED
        ])])
        wh_mining = Webhook.objects.create(
            name='Mining',
            url='dummy-url-2',
            notification_types=notification_types_2,
            is_default=True,
            is_active=True
        )

        self.owner.webhooks.clear()
        self.owner.webhooks.add(wh_structures)
        self.owner.webhooks.add(wh_mining)

        owner2 = Owner.objects.get(
            corporation__corporation_id=2002           
        )
        owner2.webhooks.add(wh_structures)
        owner2.webhooks.add(wh_mining)

        # move most mining notification to 2nd owner
        notifications = Notification.objects.filter(
            notification_id__in=[
                1000000401,                
                1000000403,
                1000000404,
                1000000405
            ]
        )
        for x in notifications:
            x.owner = owner2
            x.save()
        
        # send notifications for 1st owner only
        tasks.send_new_notifications_for_owner(
            self.owner.pk, 
            rate_limited=False
        )
        results = {            
            wh_mining.pk: set(),
            wh_structures.pk: set()
        }
        for x in mock_send_to_webhook.call_args_list:
            first = x[0]
            notification = first[0]
            hook = first[1]
            results[hook.pk].add(notification.notification_id)

        # structure notifications should have been sent
        self.assertSetEqual(
            results[wh_structures.pk],
            {
                1000000402,
                1000000502,
                1000000504,
                1000000505,                
                1000000509,
                1000010509
            }
        )
        # but mining notifications should NOT have been sent
        self.assertSetEqual(
            results[wh_mining.pk],
            {
                1000000402
            }
        )
      
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_new_notifications_no_structures_preloaded(
        self, 
        mock_execute, 
        mock_esi_client_factory,
        mock_token
    ):        
        logger.debug('test_send_new_notifications_no_structures_preloaded')
        mock_client = Mock()        
        mock_client.Universe.get_universe_structures_structure_id.side_effect \
            = esi_get_universe_structures_structure_id
        mock_esi_client_factory.return_value = mock_client
        
        # remove structures from setup so we can start from scratch
        Structure.objects.all().delete()
        
        # user needs permission to run tasks
        p = Permission.objects.get(
            codename='add_structure_owner', 
            content_type__app_label='structures'
        )
        self.user.user_permissions.add(p)
        self.user.save()
        
        tasks.send_all_new_notifications(rate_limited=False)
        
        # should have sent all notifications
        self.assertEqual(
            mock_execute.call_count, 
            len(get_all_notification_ids())
        )

        # should have created structures on the fly        
        structure_ids = {
            x['id'] for x in Structure.objects.values('id')
        }
        self.assertSetEqual(
            structure_ids,
            {1000000000002, 1000000000001}
        )

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_notifications(
        self, 
        mock_execute, 
        mock_esi_client_factory,
        mock_token
    ):
        logger.debug('test_send_notifications')
        ids = {1000000401, 1000000402, 1000000403}
        notification_pks = [
            x.pk for x in Notification.objects.filter(notification_id__in=ids)
        ]        
        tasks.send_notifications(notification_pks)

        # should have sent notification
        self.assertEqual(mock_execute.call_count, 3)

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_test_notification(
        self, 
        mock_execute, 
        mock_esi_client_factory,
        mock_token
    ):        
        logger.debug('test_send_test_notification')
        mock_response = Mock()
        mock_response.status_ok = True
        mock_response.content = {"dummy_response": True}
        mock_execute.return_value = mock_response
        my_webhook = self.owner.webhooks.first()
        tasks.send_test_notifications_to_webhook(my_webhook.pk, self.user.pk)

        # should have sent notification
        self.assertEqual(mock_execute.call_count, 1)
    
    @patch(MODULE_PATH + '.send_new_notifications_for_owner')
    def test_send_all_new_notifications(
        self, 
        mock_send_new_notifications_for_owner
    ):
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        owner_2002 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002)
        )
        tasks.send_all_new_notifications()
        self.assertEqual(mock_send_new_notifications_for_owner.call_count, 2)
        call_args_list = mock_send_new_notifications_for_owner.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)
        args, kwargs = call_args_list[1]
        self.assertEqual(args[0], owner_2002.pk)

    @patch(MODULE_PATH + '.send_new_notifications_for_owner')
    def test_send_all_new_notifications_not_active(
        self, 
        mock_send_new_notifications_for_owner
    ):
        """no notifications are sent for non active owners"""
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001),
            is_active=True
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            is_active=False
        )
        tasks.send_all_new_notifications()
        self.assertEqual(mock_send_new_notifications_for_owner.call_count, 1)
        call_args_list = mock_send_new_notifications_for_owner.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)
