from datetime import timedelta
import inspect
import json
import logging
import math
import os
from random import randrange
import sys
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth.models import User, Permission 
from django.urls import reverse
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils.timezone import now

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo, \
    EveAllianceInfo
from allianceauth.authentication.models import CharacterOwnership
from bravado.exception import *
from esi.models import Token, Scope
from esi.errors import TokenExpiredError, TokenInvalidError

from . import tasks
from .app_settings import *
from .models import *
from . import views

# reconfigure logger so we get logging from tasks to console during test
c_handler = logging.StreamHandler(sys.stdout)
logger = logging.getLogger('structures.models')
logger.level = logging.DEBUG
logger.addHandler(c_handler)


class TestTasksStructures(TestCase):
    
    # note: setup is making calls to ESI to get full info for entities
    # all ESI calls in the tested module are mocked though

    
    def setUp(self):        
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
            self.corp_structures = json.load(f)

        # ESI universe structures
        with open(
            currentdir + '/testdata/universe_structures.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            self.universe_structures = json.load(f)

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
     
    def test_run_unknown_owner(self):        
        with self.assertRaises(Owner.DoesNotExist):
            tasks.update_structures_for_owner(owner_pk=1)
        

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
        self.assertEqual(mock_operation.result.call_count, 1)
        
        # should only contain the right structures
        structure_ids = [
            x['id'] for x in Structure.objects.values('id')
        ]
        self.assertCountEqual(
            structure_ids,
            [1000000000002, 1000000000001]
        )


class TestTasksNotifications(TestCase):    

    def setUp(self): 

        # load test data
        currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
            inspect.currentframe()
        )))

        # ESI notifications
        with open(
            currentdir + '/testdata/notifications.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            notifications = json.load(f)

        self.notifications = list()
        for notification in notifications:
            notification['timestamp'] =  now() - timedelta(
                hours=randrange(3), 
                minutes=randrange(60), 
                seconds=randrange(60)
            )
            self.notifications.append(notification)            

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

        for x in entities['Structure']:
            x['owner'] = self.owner
            del x['owner_corporation_id']
            Structure.objects.create(**x)
                

    def test_run_unknown_owner(self):
        owner_pks = [x.pk for x in Owner.objects.all()]
        
        with self.assertRaises(Owner.DoesNotExist):
            tasks.update_structures_for_owner(owner_pk=max(owner_pks) + 1)
   

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
        
    # "structures.tests.TestTasksNotifications.test_fetch_notifications_for_owner_normal"
    # normal synch of new structures, mode my_alliance                
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
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
            tasks.fetch_notifications_for_owner(
                owner_pk=self.owner.pk
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
            ]
        )
            
        
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    def test_fetch_notifications_for_owner_esi_error(
            self, 
            mock_esi_client_factory,             
            mock_Token
        ):
        
        # create mocks        
        def get_characters_character_id_notifications(            
            *args, 
            **kwargs
        ):            
            raise HTTPBadGateway()
        
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
        self.assertFalse(
            tasks.fetch_notifications_for_owner(owner_pk=self.owner.pk)
        )

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, 
            Owner.ERROR_UNKNOWN
        )
        

class TestProcessNotifications(TestCase):    

    def setUp(self): 

        # load test data
        currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
            inspect.currentframe()
        )))

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

        for x in entities['Structure']:
            x['owner'] = self.owner
            del x['owner_corporation_id']
            Structure.objects.create(**x)

        # ESI universe structures
        with open(
            currentdir + '/testdata/universe_structures.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            self.universe_structures = json.load(f)

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
    

    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.tasks.Notification.send_to_webhook', autospec=True)
    def test_run_unknown_owner(
        self,         
        mock_esi_client_factory,
        mock_send_to_webhook,
        mock_token
    ):      
        owner_pks = [x.pk for x in Owner.objects.all()]
        
        with self.assertRaises(Owner.DoesNotExist):
            tasks.update_structures_for_owner(owner_pk=max(owner_pks) + 1)


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


    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_new_notifications(
        self, 
        mock_execute, 
        mock_esi_client_factory,
        mock_token
    ):
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        
        tasks.send_all_new_notifications(rate_limited = False)
        self.assertEqual(mock_execute.call_count, 17)

    
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
    
    
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory', autospec=True)
    @patch('structures.models.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_new_notifications_no_structures_preloaded(
        self, 
        mock_execute, 
        mock_esi_client_factory,
        mock_token
    ):
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

        mock_client = Mock()        
        mock_client.Universe.get_universe_structures_structure_id.side_effect =\
            get_universe_structure
        mock_esi_client_factory.return_value = mock_client
        
        # remove structures from setup so we can start from scratch
        Structure.objects.all().delete()
        
        # user needs permission to run tasks
        p = Permission.objects.get(
            codename='add_structure_owner', 
            content_type__app_label=__package__
        )
        self.user.user_permissions.add(p)
        self.user.save()
        
        tasks.send_all_new_notifications(rate_limited = False)
        
        # should have sent all notifications
        self.assertEqual(mock_execute.call_count, 17)

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
        tasks.send_test_notifications_to_webhook(self.webhook.pk, self.user.pk)

        # should have sent notification
        self.assertEqual(mock_execute.call_count, 1)


class TestViews(TestCase):
    
    def setUp(self):        
        # load test data
        currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
            inspect.currentframe()
        )))

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
            content_type__app_label=__package__
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
        structure_ids = [x['structure_id'] for x in data]
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
            content_type__app_label=__package__
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
            content_type__app_label=__package__
        )
        user.user_permissions.add(p)
        p = Permission.objects.get(
            codename='view_alliance_structures', 
            content_type__app_label=__package__
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
            content_type__app_label=__package__
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
            content_type__app_label=__package__
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
        # load test data
        currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
            inspect.currentframe()
        )))

        # entities
        with open(
            currentdir + '/testdata/entities.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            self.entities = json.load(f)
    

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

