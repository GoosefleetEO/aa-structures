import logging
import inspect
import json
import math
import os
import sys
from unittest.mock import Mock, patch

from django.contrib.auth.models import User, Permission 
from django.urls import reverse
from django.test import TestCase
from django.test.client import Client

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.authentication.models import CharacterOwnership
from esi.models import Token, Scope
from esi.errors import TokenExpiredError, TokenInvalidError

from . import tasks
from .app_settings import *
from .models import *


# reconfigure logger so we get logging from tasks to console during test
c_handler = logging.StreamHandler(sys.stdout)
logger = logging.getLogger('structures.tasks')
logger.level = logging.DEBUG
logger.addHandler(c_handler)


class TestTasksStructures(TestCase):
    
    # note: setup is making calls to ESI to get full info for entities
    # all ESI calls in the tested module are mocked though


    @classmethod
    def setUpClass(cls):
        super(TestTasksStructures, cls).setUpClass()

        # load test data
        currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
            inspect.currentframe()
        )))

        # ESI corp structures        
        with open(
            currentdir + '/testdata/corp_structures.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            cls.corp_structures = json.load(f)

        # ESI universe structures
        with open(
            currentdir + '/testdata/universe_structures.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            cls.universe_structures = json.load(f)

        # entities
        with open(
            currentdir + '/testdata/entities.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            entities = json.load(f)

        entities_def = [
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveGroup,
            EveType,
            EveCorporationInfo,
            EveCharacter
        ]
    
        for EntityClass in entities_def:
            entity_name = EntityClass.__name__
            for x in entities[entity_name]:
                EntityClass.objects.create(**x)
            assert(len(entities[entity_name]) == EntityClass.objects.count())
        
        # 1 user
        cls.character = EveCharacter.objects.get(character_id=1001)
                
        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        cls.user = User.objects.create_user(
            cls.character.character_name,
            'abc@example.com',
            'password'
        )

        cls.main_ownership = CharacterOwnership.objects.create(
            character=cls.character,
            owner_hash='x1',
            user=cls.user
        )        


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
    
    # normal synch of new structures, mode my_alliance            
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory')
    def test_update_structures_for_owner_normal(
            self, 
            mock_esi_client_factory,             
            mock_Token
        ):
        
        # create mocks
        def get_corp_structures_page(*args, **kwargs):
            #returns single page for operation.result(), first with header
            page_size = 2
            mock_calls_count = len(mock_operation.mock_calls)
            start = (mock_calls_count - 1) * page_size
            stop = start + page_size
            pages_count = int(math.ceil(len(self.corp_structures) / page_size))
            if mock_calls_count == 1:
                mock_response = Mock()
                mock_response.headers = {'x-pages': pages_count}
                return [self.corp_structures[start:stop], mock_response]
            else:
                return self.corp_structures[start:stop]

        def get_universe_structure(structure_id, *args, **kwargs):
            if str(structure_id) in self.universe_structures:
                x = Mock()
                x.result.return_value = \
                    self.universe_structures[str(structure_id)]
                return x
            else:
                raise RuntimeError(
                    'Can not find structure for {}'.format(structure_id)
                )

        # mock_Token.objects.filter.side_effect = [Token()]
        
        mock_client = Mock()
        mock_operation = Mock()
        mock_operation.result.side_effect = get_corp_structures_page        
        mock_client.Corporation.get_corporations_corporation_id_structures =\
            Mock(return_value=mock_operation)
        mock_client.Universe.get_universe_structures_structure_id.side_effect =\
            get_universe_structure
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
            tasks.update_structures_for_owner(owner_pk=owner.pk)
        )

        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_NONE            
        )
        
        # should have tried to fetch structures
        self.assertEqual(mock_operation.result.call_count, 1)
        
        # should only contain the right structures
        structure_ids = [
            x['id'] for x in Structure.objects.values('id')
        ]
        self.assertCountEqual(
            structure_ids,
            [1031369432897, 1028151259819]
        )


class TestTasksNotifications(TestCase):
    
    # note: setup is making calls to ESI to get full info for entities
    # all ESI calls in the tested module are mocked though


    @classmethod
    def setUpClass(cls):
        super(TestTasksNotifications, cls).setUpClass()

        # load test data
        currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
            inspect.currentframe()
        )))

        # ESI corp structures        
        with open(
            currentdir + '/testdata/corp_structures.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            cls.corp_structures = json.load(f)

        # ESI universe structures
        with open(
            currentdir + '/testdata/notifications.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            cls.notifications = json.load(f)

        # entities
        with open(
            currentdir + '/testdata/entities.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            entities = json.load(f)

        entities_def = [
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveGroup,
            EveType,
            EveCorporationInfo,
            EveCharacter,    
            NotificationEntity    
        ]
    
        for EntityClass in entities_def:
            entity_name = EntityClass.__name__
            for x in entities[entity_name]:
                EntityClass.objects.create(**x)
            assert(len(entities[entity_name]) == EntityClass.objects.count())
                
        # 1 user
        cls.character = EveCharacter.objects.get(character_id=1001)
                
        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        cls.user = User.objects.create_user(
            cls.character.character_name,
            'abc@example.com',
            'password'
        )

        cls.main_ownership = CharacterOwnership.objects.create(
            character=cls.character,
            owner_hash='x1',
            user=cls.user
        )

        cls.owner = Owner.objects.create(
            corporation=cls.corporation,
            character=cls.main_ownership
        )

        for x in entities['Structure']:
            x['owner'] = cls.owner
            Structure.objects.create(**x)
                
   
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
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory')
    def test_fetch_notifications_for_owner_normal(
            self, 
            mock_esi_client_factory,             
            mock_Token
        ):
        
        # create mocks        
        def get_characters_character_id_notifications(            
            *args, 
            **kwargs
        ):            
            x = Mock()
            x.result.return_value = self.notifications
            return x
        
        # mock_Token.objects.filter.side_effect = [Token()]
        
        mock_client = Mock()       
        mock_client.Character\
            .get_characters_character_id_notifications.side_effect =\
                get_characters_character_id_notifications
        mock_esi_client_factory.return_value = mock_client

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
                
        # run update task
        self.assertTrue(
            tasks.fetch_notifications_for_owner(owner_pk=self.owner.pk)
        )

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, 
            Owner.ERROR_NONE            
        )
                
        # should only contain the right notifications
        structure_ids = [
            x['notification_id'] 
            for x in Notification.objects.values('notification_id')
        ]
        self.assertCountEqual(
            structure_ids,
            [1045790513, 986823936, 1007801053, 1007802916, 1033521794]
        )
        