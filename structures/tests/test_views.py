from datetime import timedelta
import json
from unittest.mock import patch, Mock
from urllib.parse import urlparse, parse_qs

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.urls import reverse
from django.utils.timezone import now

from allianceauth.tests.auth_utils import AuthUtils
from allianceauth.eveonline.models import (
    EveCharacter, EveCorporationInfo, EveAllianceInfo
)

from esi.models import Token

from ..app_settings import (
    STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES,
    STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES,
    STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES
)
from ..models import Owner, StructureTag, Webhook
from .testdata import \
    create_structures, set_owner_character, load_entities, create_user
from ..utils import set_test_logger, NoSocketsTestCase
from .. import views


MODULE_PATH = 'structures.views'
logger = set_test_logger(MODULE_PATH, __file__)


class TestStructureList(NoSocketsTestCase):
    
    def setUp(self):   
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        AuthUtils.add_permission_to_user_by_name(
            'structures.basic_access', self.user
        )
        self.factory = RequestFactory()
    
    def test_basic_access_main_view(self):
        request = self.factory.get(reverse('structures:structure_list'))
        request.user = self.user
        response = views.structure_list(request)
        self.assertEqual(response.status_code, 200)

    @patch(MODULE_PATH + '.STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED', True)
    def test_default_filter_enabled(self):
        request = self.factory.get(reverse('structures:index'))
        request.user = self.user
        response = views.index(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/structures/list/?tags=tag_a')

    @patch(MODULE_PATH + '.STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED', False)
    def test_default_filter_disabled(self):
        request = self.factory.get(reverse('structures:index'))
        request.user = self.user
        response = views.index(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/structures/list/')
        
    def test_basic_access_own_structures_only(self):
        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        structure_ids = {x['structure_id'] for x in data}
        self.assertSetEqual(
            structure_ids, 
            {
                1000000000001, 
                1200000000003, 
                1200000000004, 
                1200000000005,
                1300000000001,
                1300000000002,
                1300000000003,
            }
        )
        
    def test_perm_view_alliance_structures_normal(self):        
        AuthUtils.add_permission_to_user_by_name(
            'structures.view_alliance_structures', self.user
        )
        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))
        structure_ids = {x['structure_id'] for x in data}
        self.assertSetEqual(
            structure_ids, 
            {
                1000000000001, 
                1000000000002, 
                1200000000003, 
                1200000000004, 
                1200000000005,
                1300000000001,
                1300000000002,
                1300000000003,
            }
        )

    def test_perm_view_alliance_structures_no_alliance(self):
        # run with a user that is not a member of an alliance        
        character = EveCharacter.objects.get(character_id=1011)
        user = create_user(character.character_id)        
        AuthUtils.add_permission_to_user_by_name(
            'structures.basic_access', user
        )
        AuthUtils.add_permission_to_user_by_name(
            'structures.view_alliance_structures', user
        )

        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))
        structure_ids = {x['structure_id'] for x in data}
        self.assertSetEqual(
            structure_ids, 
            {1000000000003}
        )
            
    def test_perm_view_all_structures(self):        
        AuthUtils.add_permission_to_user_by_name(
            'structures.view_all_structures', self.user
        )
        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))
        structure_ids = {x['structure_id'] for x in data}
        self.assertSetEqual(
            structure_ids, 
            {
                1000000000001, 
                1000000000002, 
                1000000000003, 
                1200000000003,
                1200000000004, 
                1200000000005,
                1300000000001,
                1300000000002,
                1300000000003,
            }
        )

    def test_list_filter_by_tag_1(self):               
        StructureTag.objects.get(name='tag_a')
        StructureTag.objects.get(name='tag_b')
        StructureTag.objects.get(name='tag_c')       
        AuthUtils.add_permission_to_user_by_name(
            'structures.view_all_structures', self.user
        )

        # no filter
        request = self.factory.get('{}'.format(
            reverse('structures:structure_list_data')
        ))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        self.assertSetEqual(
            {x['structure_id'] for x in data}, 
            {
                1000000000001, 
                1000000000002, 
                1000000000003, 
                1200000000003, 
                1200000000004, 
                1200000000005,
                1300000000001,
                1300000000002,
                1300000000003,
            }
        )

        # filter for tag_c
        request = self.factory.get('{}?tags=tag_c'.format(
            reverse('structures:structure_list_data')
        ))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        self.assertSetEqual(
            {x['structure_id'] for x in data}, 
            {1000000000002, 1000000000003}
        )

        # filter for tag_b
        request = self.factory.get('{}?tags=tag_b'.format(
            reverse('structures:structure_list_data')
        ))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        self.assertSetEqual(
            {x['structure_id'] for x in data}, 
            {1000000000003}
        )

        # filter for tag_c, tag_b
        request = self.factory.get('{}?tags=tag_c,tag_b'.format(
            reverse('structures:structure_list_data')
        ))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        self.assertSetEqual(
            {x['structure_id'] for x in data}, 
            {1000000000002, 1000000000003}
        )

    def test_call_with_raw_tags(self):                
        request = self.factory.get('{}?tags=tag_c,tag_b'.format(
            reverse('structures:structure_list')
        ))
        request.user = self.user
        response = views.structure_list(request)
        self.assertEqual(response.status_code, 200)

    def test_set_tags_filter(self):
        request = self.factory.post(
            reverse('structures:structure_list'),
            data={                
                'tag_b': True,
                'tag_c': True,
            }
        )
        request.user = self.user
        response = views.structure_list(request)
        self.assertEqual(response.status_code, 302)        
        parts = urlparse(response.url)
        path = parts[2]
        query_dict = parse_qs(parts[4])
        self.assertEqual(
            path, reverse('structures:structure_list')
        )
        self.assertIn('tags', query_dict)
        params = query_dict['tags'][0].split(',')
        self.assertSetEqual(set(params), {'tag_c', 'tag_b'})
        

class TestAddStructureOwner(NoSocketsTestCase):
    
    @staticmethod
    def _create_test_user(character_id):
        """create test user with all permission from character ID"""
        my_user = create_user(character_id)       
        AuthUtils.add_permission_to_user_by_name(
            'structures.basic_access', my_user
        )
        AuthUtils.add_permission_to_user_by_name(
            'structures.add_structure_owner', my_user
        )
        return my_user

    @classmethod
    def setUpClass(cls):
        super().setUpClass()        
        load_entities(
            [EveCorporationInfo, EveAllianceInfo, EveCharacter, Webhook]
        )        
        cls.user = cls._create_test_user(1001)
        cls.character = cls.user.profile.main_character
        cls.factory = RequestFactory()
        
    def setUp(self):        
        Owner.objects.all().delete()
    
    @patch(MODULE_PATH + '.STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED', True)
    @patch(MODULE_PATH + '.tasks.update_structures_for_owner')
    @patch(MODULE_PATH + '.notify_admins')
    @patch(MODULE_PATH + '.messages_plus')
    def test_view_add_structure_owner_normal(
        self, 
        mock_messages, 
        mock_notify_admins, 
        mock_update_structures_for_owner
    ):        
        token = Mock(spec=Token)                
        token.character_id = self.character.character_id
        request = self.factory.get(reverse('structures:add_structure_owner'))
        request.user = self.user
        request.token = token
        middleware = SessionMiddleware()
        middleware.process_request(request)
        orig_view = views.add_structure_owner\
            .__wrapped__.__wrapped__.__wrapped__
        response = orig_view(request, token)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('structures:index'))
        self.assertTrue(mock_messages.info.called)
        self.assertTrue(mock_notify_admins.called)
        my_ownership = self.user.character_ownerships.get(
            character__character_id=self.character.character_id
        )
        my_owner = Owner.objects.get(character=my_ownership)
        self.assertEqual(my_owner.webhooks.first().name, 'Test Webhook 1')
        self.assertTrue(mock_update_structures_for_owner.delay.called)

    @patch(MODULE_PATH + '.STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED', False)
    @patch(MODULE_PATH + '.tasks.update_structures_for_owner')
    @patch(MODULE_PATH + '.notify_admins')
    @patch(MODULE_PATH + '.messages_plus')
    def test_view_add_structure_owner_normal_no_admins_notify(
        self, 
        mock_messages, 
        mock_notify_admins, 
        mock_update_structures_for_owner
    ):
        token = Mock(spec=Token)        
        token.character_id = self.user.profile.main_character.character_id
        request = self.factory.get(reverse('structures:add_structure_owner'))
        request.user = self.user
        request.token = token
        middleware = SessionMiddleware()
        middleware.process_request(request)
        orig_view = views.add_structure_owner\
            .__wrapped__.__wrapped__.__wrapped__
        response = orig_view(request, token)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('structures:index'))
        self.assertTrue(mock_messages.info.called)
        self.assertFalse(mock_notify_admins.called)
        self.assertTrue(mock_update_structures_for_owner.delay.called)

    @patch(MODULE_PATH + '.STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED', False)
    @patch(MODULE_PATH + '.tasks.update_structures_for_owner')
    @patch(MODULE_PATH + '.notify_admins')
    @patch(MODULE_PATH + '.messages_plus')
    def test_view_add_structure_owner_normal_no_default_webhook(
        self, 
        mock_messages, 
        mock_notify_admins, 
        mock_update_structures_for_owner
    ):
        Webhook.objects.filter(name='Test Webhook 1').delete()
        token = Mock(spec=Token)
        token.character_id = self.user.profile.main_character.character_id
        request = self.factory.get(reverse('structures:add_structure_owner'))
        request.user = self.user
        request.token = token
        middleware = SessionMiddleware()
        middleware.process_request(request)
        orig_view = views.add_structure_owner\
            .__wrapped__.__wrapped__.__wrapped__
        response = orig_view(request, token)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('structures:index'))
        self.assertTrue(mock_messages.info.called)
        self.assertFalse(mock_notify_admins.called)
        my_ownership = self.user.character_ownerships.get(
            character__character_id=self.character.character_id
        )
        my_owner = Owner.objects.get(character=my_ownership)
        self.assertIsNone(my_owner.webhooks.first())
        self.assertTrue(mock_update_structures_for_owner.delay.called)

    @patch(MODULE_PATH + '.messages_plus')
    def test_view_add_structure_owner_wrong_ownership(self, mock_messages):
        token = Mock(spec=Token)        
        token.character_id = 1011
        request = self.factory.get(reverse('structures:add_structure_owner'))
        request.user = self.user
        request.token = token
        middleware = SessionMiddleware()
        middleware.process_request(request)
        orig_view = views.add_structure_owner\
            .__wrapped__.__wrapped__.__wrapped__
        response = orig_view(request, token)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('structures:index'))
        self.assertTrue(mock_messages.error.called)


class TestStatus(NoSocketsTestCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        my_user, _ = set_owner_character(character_id=1001)
        AuthUtils.add_permission_to_user_by_name(
            'structures.basic_access', my_user
        )        
        cls.factory = RequestFactory()   

    def test_view_service_status_ok(self):
        for owner in Owner.objects.filter(
            is_included_in_service_status=True
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
        for owner in Owner.objects.filter(is_included_in_service_status=True):
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

        for owner in Owner.objects.filter(is_included_in_service_status=True):
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
            is_included_in_service_status=True
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

        for owner in Owner.objects.filter(is_included_in_service_status=True):
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

        for owner in Owner.objects.filter(is_included_in_service_status=True):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now() - timedelta(
                minutes=STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES + 1
            )
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(is_included_in_service_status=True):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now() - timedelta(
                minutes=STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES + 1
            )
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)
