from datetime import timedelta
from random import randrange
from unittest.mock import Mock, patch

from bravado.requests_client import IncomingResponse

from django.conf import settings
from django.contrib.auth.models import User, Permission 
from django.test import TestCase, RequestFactory
from django.utils.timezone import now

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo
from allianceauth.authentication.models import CharacterOwnership
from bravado.exception import *
from esi.models import Token, Scope
from esi.errors import TokenExpiredError, TokenInvalidError

from . import set_logger
from .. import tasks
from ..tasks import _fetch_custom_offices
from ..app_settings import *
from ..models import *

from .testdata import \
    esi_get_corporations_corporation_id_structures, \
    esi_get_universe_structures_structure_id, \
    esi_get_characters_character_id_notifications, \
    esi_get_corporations_corporation_id_customs_offices, \
    esi_post_corporations_corporation_id_assets_locations, \
    esi_post_corporations_corporation_id_assets_names, \
    entities_testdata,\
    notifications_testdata,\
    corp_structures_data,\
    load_entities

logger = set_logger('structures.tasks', __file__)


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
        esi_get_corporations_corporation_id_customs_offices.override_data = None
        
        load_entities([
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,            
            EveCorporationInfo,
            EveCharacter
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
    @patch('structures.tasks.Token')    
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
    @patch('structures.tasks.Token')
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
        
    
    #normal synch of new structures, mode my_alliance
    @patch('structures.tasks.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch('structures.tasks.notify', autospec=True)
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory')
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
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
                esi_get_universe_structures_structure_id
        mock_esi_client_factory.return_value = mock_client
        mock_client.Planetary_Interaction\
            .get_corporations_corporation_id_customs_offices = \
                esi_get_corporations_corporation_id_customs_offices
        mock_client.Assets\
            .post_corporations_corporation_id_assets_locations = \
                esi_post_corporations_corporation_id_assets_locations
        mock_client.Assets\
            .post_corporations_corporation_id_assets_names = \
                esi_post_corporations_corporation_id_assets_names

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
        ))
        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_NONE            
        )        
        # should have tried to fetch structures
        self.assertEqual(
            mock_client.Corporation\
                .get_corporations_corporation_id_structures.call_count, 
            2
        )                
        # must contain all expected structures
        self.assertSetEqual(
            { x['id'] for x in Structure.objects.values('id') },
            {
                1000000000001, 
                1000000000002, 
                1000000000003, 
                1200000000003,
                1200000000004,
                1200000000005
            }
        )
        # user report has been sent
        self.assertTrue(mock_notify.called)
    

    # synch of structures, ensure old structures are removed
    @patch('structures.tasks.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory')
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
            { x['id'] for x in Structure.objects.values('id') },
            {1000000000001, 1000000000002, 1000000000003}
        )

        # run update task 2nd time with one less structure
        my_corp_structures_data = corp_structures_data.copy()
        del(my_corp_structures_data["2001"][1])
        esi_get_corporations_corporation_id_structures.override_data = \
            my_corp_structures_data
        tasks.update_structures_for_owner(
            owner_pk=owner.pk
        )        
        # should contain only the remaining structure
        self.assertSetEqual(
            { x['id'] for x in Structure.objects.values('id') },
            {1000000000002, 1000000000003}
        )
    
    # synch of structures, ensure tags are not removed
    @patch('structures.tasks.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory')
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
            { x['id'] for x in Structure.objects.values('id') },
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
            { x['id'] for x in Structure.objects.values('id') },
            {1000000000001, 1000000000002, 1000000000003}
        )
        # should still contain the tag
        s_new = Structure.objects.get(id=1000000000001)
        self.assertEqual(s_new.tags.get(name='tag_a'), tag_a)
    
    
    #no structures retrieved from ESI during sync
    @patch('structures.tasks.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory')
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
        mock_esi_client_factory.return_value = mock_client
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
        ))
        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_NONE            
        )                
        # must be empty
        self.assertEqual(Structure.objects.count(), 0)


    # error during user report
    @patch('structures.tasks.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch('structures.tasks.notify')
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory')
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
        mock_esi_client_factory.return_value = mock_client
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
        ))       


    # synch of structures, ensure old structures are removed
    @patch('structures.tasks.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory')
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
            owner_pk=owner.pk, 
            user_pk=self.user.pk
        )        
        # should contain the right structures
        self.assertSetEqual(
            { x['id'] for x in Structure.objects.values('id') },
            {1000000000001, 1000000000002, 1000000000003}
        )

        # run update task 2nd time with one less structure
        my_corp_structures_data = corp_structures_data.copy()
        del(my_corp_structures_data["2001"][1])
        esi_get_corporations_corporation_id_structures.override_data = \
            my_corp_structures_data
        tasks.update_structures_for_owner(
            owner_pk=owner.pk, 
            user_pk=self.user.pk
        )        
        # should contain only the remaining structure
        self.assertSetEqual(
            { x['id'] for x in Structure.objects.values('id') },
            {1000000000002, 1000000000003}
        )

    # catch exception during storing of structures
    @patch('structures.tasks.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch('structures.tasks.Structure.objects.update_or_create_from_dict')
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory')
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

    
    @patch('structures.tasks.update_structures_for_owner')
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


class TestSyncNotifications(TestCase):    

    def setUp(self): 

        # entities        
        load_entities()
    
        for x in EveCorporationInfo.objects.all():
            EveEntity.objects.get_or_create(
                id = x.corporation_id,
                defaults={
                    'category': EveEntity.CATEGORY_CORPORATION,
                    'name': x.corporation_name
                }
            )

        for x in EveCharacter.objects.all():
            EveEntity.objects.get_or_create(
                id = x.character_id,
                defaults={
                    'category': EveEntity.CATEGORY_CHARACTER,
                    'name': x.character_name
                }
            )
                
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

        self.owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )

        self.webhook = Webhook.objects.create(
            name='Test',
            url='dummy-url'
        )
        self.owner.webhooks.add(self.webhook)
        self.owner.save()

        for structure in entities_testdata['Structure']:
            x = structure.copy()
            x['owner'] = self.owner
            del x['owner_corporation_id']
            Structure.objects.create(**x)
                

    def test_run_unknown_owner(self):
        with self.assertRaises(Owner.DoesNotExist):
            tasks.fetch_notifications_for_owner(owner_pk=_get_invalid_owner_pk())
   

    # run without char        
    def test_run_no_sync_char(self):
        owner = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002)
        )
        self.assertFalse(
            tasks.fetch_notifications_for_owner(owner_pk=owner.pk)
        )
        owner.refresh_from_db()
        self.assertEqual(
            owner.notifications_last_error, 
            Owner.ERROR_NO_CHARACTER
        )

    
    # test expired token    
    @patch('structures.tasks.Token')    
    def test_check_expired_token(
            self,             
            mock_Token
        ):                        
        mock_Token.objects.filter.side_effect = TokenExpiredError()        

        owner = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            character=self.main_ownership
        )
                        
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
                
        # run update task
        self.assertFalse(
            tasks.fetch_notifications_for_owner(owner_pk=owner.pk)
        )

        owner.refresh_from_db()
        self.assertEqual(
            owner.notifications_last_error, 
            Owner.ERROR_TOKEN_EXPIRED            
        )

    
    # test invalid token    
    @patch('structures.tasks.Token')
    def test_check_invalid_token(
            self,             
            mock_Token
        ):                        
        mock_Token.objects.filter.side_effect = TokenInvalidError()

        owner = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            character=self.main_ownership
        )
                        
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
                
        # run update task
        self.assertFalse(
            tasks.fetch_notifications_for_owner(owner_pk=owner.pk)
        )

        owner.refresh_from_db()
        self.assertEqual(
            owner.notifications_last_error, 
            Owner.ERROR_TOKEN_INVALID            
        )
        
    
    # normal synch of new structures, mode my_alliance                
    @patch('structures.tasks.notify', autospec=True)
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
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
        notification_ids = [
            x['notification_id'] 
            for x in Notification.objects.values('notification_id')
        ]
        self.assertCountEqual(
            notification_ids,
            [
                1000000401,
                1000000402,
                1000000403,
                1000000404,
                1000000405,
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
                1000000601,
                1000000602,
            ]
        )
        # user report has been sent
        self.assertTrue(mock_notify.called)
            
            
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
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

           
    @patch('structures.tasks.fetch_notifications_for_owner')
    def test_fetch_all_notifications(
        self, 
        mock_fetch_notifications_for_owner
    ):
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        owner_2002 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002)
        )
        tasks.fetch_all_notifications()
        self.assertEqual(mock_fetch_notifications_for_owner.delay.call_count, 2)
        call_args_list = mock_fetch_notifications_for_owner.delay.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)
        args, kwargs = call_args_list[1]
        self.assertEqual(args[0], owner_2002.pk)
        

class TestProcessNotifications(TestCase):    

    def setUp(self):         
        load_entities()
                
        for x in EveCorporationInfo.objects.all():
            EveEntity.objects.get_or_create(
                id = x.corporation_id,
                defaults={
                    'category': EveEntity.CATEGORY_CORPORATION,
                    'name': x.corporation_name
                }
            )

        for x in EveCharacter.objects.all():
            EveEntity.objects.get_or_create(
                id = x.character_id,
                defaults={
                    'category': EveEntity.CATEGORY_CHARACTER,
                    'name': x.character_name
                }
            )
               
        self.factory = RequestFactory()
        
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

        self.owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership,            
        )
        self.webhook = Webhook.objects.create(
            name='Test',
            url='dummy-url'
        )
        self.owner.webhooks.add(self.webhook)
        self.owner.save()

        for structure in entities_testdata['Structure']:
            x = structure.copy()
            x['owner'] = self.owner
            del x['owner_corporation_id']
            Structure.objects.create(**x)
        
        for notification in notifications_testdata:                        
            notification_type = \
                Notification.get_matching_notification_type(
                    notification['type']
                )
            if notification_type:
                sender_type = \
                    EveEntity.get_matching_entity_type(
                        notification['sender_type']
                    )                
                sender = EveEntity.objects.get(id=notification['sender_id'])                
                text = notification['text'] \
                    if 'text' in notification else None
                is_read = notification['is_read'] \
                    if 'is_read' in notification else None
                obj = Notification.objects.update_or_create(
                    notification_id=notification['notification_id'],
                    owner=self.owner,
                    defaults={
                        'sender': sender,
                        'timestamp': now() - timedelta(
                            hours=randrange(3), 
                            minutes=randrange(60), 
                            seconds=randrange(60)
                        ),
                        'notification_type': notification_type,
                        'text': text,
                        'is_read': is_read,
                        'last_updated': now(),
                        'is_sent': False
                    }
                )   
    
    
    def test_run_unknown_owner(self):      
        with self.assertRaises(Owner.DoesNotExist):
            tasks.send_new_notifications_for_owner(
                owner_pk=_get_invalid_owner_pk()
            )


    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.tasks.Notification.send_to_webhook', autospec=True)
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
                rate_limited = False
            )
        )
        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.forwarding_last_error, 
            Owner.ERROR_NO_CHARACTER
        )

    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.tasks.Notification.send_to_webhook', autospec=True)
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
                rate_limited = False
            )
        )

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.forwarding_last_error, 
            Owner.ERROR_TOKEN_EXPIRED            
        )

    
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.tasks.Notification.send_to_webhook', autospec=True)
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
                rate_limited = False
            )
        )

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.forwarding_last_error, 
            Owner.ERROR_TOKEN_INVALID            
        )


    @patch('structures.tasks.STRUCTURES_ADD_TIMERS', False)
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_new_notifications_normal(
        self, 
        mock_execute, 
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
        
        tasks.send_all_new_notifications(rate_limited = False)
        self.assertEqual(mock_execute.call_count, 19)

    
    @patch('structures.tasks.STRUCTURES_ADD_TIMERS', False)
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
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
            NTYPE_MOONMINING_AUTOMATIC_FRACTURE,
            NTYPE_MOONMINING_EXTRACTION_CANCELED,
            NTYPE_MOONMINING_EXTRACTION_FINISHED,
            NTYPE_MOONMINING_EXTRACTION_STARTED,
            NTYPE_MOONMINING_LASER_FIRED
        ]])
        wh_mining = Webhook.objects.create(
            name='Mining',
            url='dummy-url-2',
            notification_types=notification_types
        )

        self.owner.webhooks.clear()
        self.owner.webhooks.add(wh_structures)
        self.owner.webhooks.add(wh_mining)
        
        tasks.send_all_new_notifications(rate_limited = False)
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
                1000000513
            }
        )


    @patch('structures.tasks.STRUCTURES_ADD_TIMERS', False)
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
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
            NTYPE_MOONMINING_EXTRACTION_CANCELED,
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
            NTYPE_MOONMINING_EXTRACTION_CANCELED,
            NTYPE_MOONMINING_AUTOMATIC_FRACTURE,            
            NTYPE_MOONMINING_EXTRACTION_FINISHED,
            NTYPE_MOONMINING_EXTRACTION_STARTED,
            NTYPE_MOONMINING_LASER_FIRED
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

        owner2 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            character=self.main_ownership,            
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
        ])
        for x in notifications:
            x.owner = owner2
            x.save()
        
        # send notifications for 1st owner only
        tasks.send_new_notifications_for_owner(
            self.owner.pk, 
            rate_limited = False
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
                1000000509
            }
        )
        # but mining notifications should NOT have been sent
        self.assertSetEqual(
            results[wh_mining.pk],
            {
                1000000402
            }
        )

    
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.tasks.Notification.send_to_webhook', autospec=True)
    def test_add_timers_normal(
        self,         
        mock_esi_client_factory,
        mock_send_to_webhook,
        mock_token
    ):
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        
        if 'allianceauth.timerboard' in settings.INSTALLED_APPS:            
            from allianceauth.timerboard.models import Timer
        
            tasks.send_all_new_notifications(rate_limited = False)
            self.assertEqual(Timer.objects.count(), 3)


    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.tasks.Notification.send_to_webhook', autospec=True)
    def test_add_timers_already_added(
        self,         
        mock_esi_client_factory,
        mock_send_to_webhook,
        mock_token
    ):
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        
        if 'allianceauth.timerboard' in settings.INSTALLED_APPS:            
            from allianceauth.timerboard.models import Timer
        
            for x in Notification.objects.all():
                x.is_timer_added = True
                x.save()

            tasks.send_all_new_notifications(rate_limited = False)
            self.assertEqual(Timer.objects.count(), 0)
    
    
    @patch('structures.tasks.STRUCTURES_ADD_TIMERS', False)
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_new_notifications_no_structures_preloaded(
        self, 
        mock_execute, 
        mock_esi_client_factory,
        mock_token
    ):        
        logger.debug('test_send_new_notifications_no_structures_preloaded')
        mock_client = Mock()        
        mock_client.Universe.get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id
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
        
        tasks.send_all_new_notifications(rate_limited = False)
        
        # should have sent all notifications
        self.assertEqual(mock_execute.call_count, 19)

        # should have created structures on the fly        
        structure_ids = {
            x['id'] for x in Structure.objects.values('id')
        }
        self.assertSetEqual(
            structure_ids,
            {1000000000002, 1000000000001}
        )


    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_single_notification(
        self, 
        mock_execute, 
        mock_esi_client_factory,
        mock_token
    ):
        logger.debug('test_send_single_notification')
        notification = Notification.objects.first()
        tasks.send_notification(notification.pk)

        # should have sent notification
        self.assertEqual(mock_execute.call_count, 1)


    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
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
        tasks.send_test_notifications_to_webhook(self.webhook.pk, self.user.pk)

        # should have sent notification
        self.assertEqual(mock_execute.call_count, 1)

    
    @patch('structures.models.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_to_webhook_normal(
        self, 
        mock_execute, 
        mock_esi_client_factory
    ):                                
        logger.debug('test_send_to_webhook_normal')
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.status_ok = True
        mock_response.content = None        
        mock_execute.return_value = mock_response

        x = Notification.objects.get(notification_id=1000000502)
        self.assertFalse(x.is_sent)
        self.assertTrue(
            x.send_to_webhook(self.webhook, mock_esi_client_factory)
        )
        self.assertTrue(x.is_sent)


    @patch('structures.models.STRUCTURES_NOTIFICATION_WAIT_SEC', 0)
    @patch('structures.models.STRUCTURES_NOTIFICATION_MAX_RETRIES', 2)
    @patch('structures.models.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_to_webhook_http_error(
        self, 
        mock_execute, 
        mock_esi_client_factory
    ):                                
        logger.debug('test_send_to_webhook_http_error')
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.status_ok = False
        mock_response.content = None        
        mock_execute.return_value = mock_response
        
        x = Notification.objects.get(notification_id=1000000502)
        self.assertFalse(
            x.send_to_webhook(self.webhook, mock_esi_client_factory)
        )


    @patch('structures.models.STRUCTURES_NOTIFICATION_MAX_RETRIES', 2)
    @patch('structures.models.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_to_webhook_too_many_requests(
        self, 
        mock_execute, 
        mock_esi_client_factory
    ):                                
        logger.debug('test_send_to_webhook_too_many_requests')
        mock_response = Mock()
        mock_response.status_code = Notification.HTTP_CODE_TOO_MANY_REQUESTS
        mock_response.status_ok = False
        mock_response.content = {'retry_after': 100}        
        mock_execute.return_value = mock_response

        x = Notification.objects.get(notification_id=1000000502)
        self.assertFalse(
            x.send_to_webhook(self.webhook, mock_esi_client_factory)
        )

        
    @patch('structures.models.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_to_webhook_exception(
        self, 
        mock_execute, 
        mock_esi_client_factory
    ):                                        
        logger.debug('test_send_to_webhook_exception')
        mock_execute.side_effect = RuntimeError('Dummy exception')

        x = Notification.objects.get(notification_id=1000000502)
        self.assertFalse(
            x.send_to_webhook(self.webhook, mock_esi_client_factory)
        )


    @patch('structures.tasks.send_new_notifications_for_owner')
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