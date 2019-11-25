import logging
import inspect
import json
import math
import os
import sys
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth.models import User, Permission 
from django.urls import reverse
from django.test import TestCase
from django.test.client import Client
from django.utils.timezone import now

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.authentication.models import CharacterOwnership
from esi.models import Token, Scope
from esi.errors import TokenExpiredError, TokenInvalidError

from . import tasks
from .app_settings import *
from .models import *


# reconfigure logger so we get logging from tasks to console during test
c_handler = logging.StreamHandler(sys.stdout)
logger = logging.getLogger('structures.models')
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
            EveEntity    
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
            ]
        )


class TestProcessNotifications(TestCase):    

    @classmethod
    def setUpClass(cls):
        super(TestProcessNotifications, cls).setUpClass()

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
            notifications = json.load(f)

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
            EveMoon,
            EveGroup,
            EveType,
            EveCorporationInfo,
            EveCharacter,    
            EveEntity    
        ]
    
        for EntityClass in entities_def:
            entity_name = EntityClass.__name__
            for x in entities[entity_name]:
                EntityClass.objects.create(**x)
            assert(len(entities[entity_name]) == EntityClass.objects.count())
                
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
            character=cls.main_ownership,            
        )
        cls.webhook = Webhook.objects.create(
            name='Test',
            url='dummy-url'
        )
        cls.owner.webhooks.add(cls.webhook)
        cls.owner.save()

        for x in entities['Structure']:
            x['owner'] = cls.owner
            Structure.objects.create(**x)

        for notification in notifications:                        
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
                    owner=cls.owner,
                    defaults={
                        'sender': sender,
                        'timestamp': now(),
                        'notification_type': notification_type,
                        'text': text,
                        'is_read': is_read,
                        'last_updated': now(),
                        'is_sent': False
                    }
                )   
            
    @patch('structures.models.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_new_notifications(
        self, 
        mock_execute, 
        mock_esi_client_factory
    ):
        self.webhook.send_new_notifications(rate_limited = False)
        self.assertEqual(mock_execute.call_count, 17)

        
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.tasks.send_new_notifications_to_webhook', autospec=True)
    def test_add_timers_normal(
        self,         
        mock_esi_client_factory,
        mock_send_new_notifications_to_webhook
    ):
        if 'allianceauth.timerboard' in settings.INSTALLED_APPS:            
            from allianceauth.timerboard.models import Timer
        
            tasks.send_all_new_notifications()
            self.assertEqual(Timer.objects.count(), 3)


    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.tasks.send_new_notifications_to_webhook', autospec=True)
    def test_add_timers_already_added(
        self,         
        mock_esi_client_factory,
        mock_send_new_notifications_to_webhook
    ):
        if 'allianceauth.timerboard' in settings.INSTALLED_APPS:            
            from allianceauth.timerboard.models import Timer
        
            for x in Notification.objects.all():
                x.is_timer_added = True
                x.save()

            tasks.send_all_new_notifications()
            self.assertEqual(Timer.objects.count(), 0)
