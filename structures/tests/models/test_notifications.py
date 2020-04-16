from datetime import datetime, timedelta
import json
from unittest.mock import Mock, patch

import pytz

from allianceauth.timerboard.models import Timer

from ...models import EveEntity, Notification, Webhook, Structure
from ..testdata import (
    load_entities,
    load_notification_entities,
    create_structures,
    set_owner_character
)
from ...utils import set_test_logger, NoSocketsTestCase

MODULE_PATH = 'structures.models.notifications'
logger = set_test_logger(MODULE_PATH, __file__)


class TestWebhook(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass() 
        cls.my_webhook = Webhook(
            name='Dummy Webhook', url='https://www.example.com'
        )

    def test_str(self):
        self.assertEqual(str(self.my_webhook), 'Dummy Webhook')

    def test_repr(self):
        expected = 'Webhook(id=%s, name=\'Dummy Webhook\')' % self.my_webhook.id
        self.assertEqual(repr(self.my_webhook), expected)

    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute')
    def test_send_test_notification_ok(self, mock_execute):        
        mock_response = Mock()
        mock_response.status_ok = True
        expected_send_report = {'dummy': 'abc123'}
        mock_response.content = expected_send_report
        mock_execute.return_value = mock_response

        response = self.my_webhook.send_test_notification()
        self.assertDictEqual(json.loads(response), expected_send_report)

    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute')
    def test_send_test_notification_failed(self, mock_execute):        
        mock_response = Mock()
        mock_response.status_ok = False
        mock_response.status_code = 500
        mock_response.content = None
        mock_execute.return_value = mock_response

        response = self.my_webhook.send_test_notification()
        self.assertEqual(response, 'HTTP status code 500')


class TestEveEntities(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()                      
        load_entities([EveEntity])

    def test_str(self):
        obj = EveEntity.objects.get(id=3011)
        self.assertEqual(str(obj), 'Big Bad Alliance')

    def test_repr(self):
        obj = EveEntity.objects.get(id=3011)
        expected = (
            'EveEntity(id=3011, category=\'alliance\', name=\'Big Bad Alliance\')'
        )
        self.assertEqual(repr(obj), expected)
    
    def test_get_matching_entity_type(self):
        self.assertEqual(
            EveEntity.get_matching_entity_category('character'),
            EveEntity.CATEGORY_CHARACTER
        )
        self.assertEqual(
            EveEntity.get_matching_entity_category('corporation'),
            EveEntity.CATEGORY_CORPORATION
        )
        self.assertEqual(
            EveEntity.get_matching_entity_category('alliance'),
            EveEntity.CATEGORY_ALLIANCE
        )
        self.assertEqual(
            EveEntity.get_matching_entity_category('faction'),
            EveEntity.CATEGORY_FACTION
        )
        self.assertEqual(
            EveEntity.get_matching_entity_category('other'),
            EveEntity.CATEGORY_OTHER
        )
        self.assertEqual(
            EveEntity.get_matching_entity_category('does not exist'),
            EveEntity.CATEGORY_OTHER
        )

    def test_profile_url(self):
        x = EveEntity.objects.get(id=3001)
        self.assertEqual(
            x.profile_url(), 
            'http://evemaps.dotlan.net/alliance/Wayne_Enterprises'
        )

        x = EveEntity.objects.get(id=2001)
        self.assertEqual(
            x.profile_url(), 
            'http://evemaps.dotlan.net/corp/Wayne_Technologies'
        )
        x = EveEntity.objects.get(id=1011)
        self.assertEqual(
            x.profile_url(), 
            ''
        )
        

class TestNotification(NoSocketsTestCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        my_user, cls.owner = set_owner_character(character_id=1001)        
        load_notification_entities(cls.owner)        
        cls.webhook = Webhook.objects.create(
            name='Test', url='http://www.example.com/dummy/'
        )
        cls.owner.webhooks.add(cls.webhook)
      
    def test_str(self):
        obj = Notification.objects.get(notification_id=1000000403)
        self.assertEqual(str(obj), '1000000403')

    def test_repr(self):
        obj = Notification.objects.get(notification_id=1000000403)
        expected = (
            'Notification(notification_id=1000000403, '
            'owner=\'Wayne Technologies\', '
            'notification_type=\'MoonminingExtractionFinished\')'
        )
        self.assertEqual(repr(obj), expected)

    def test_ldap_datetime_2_dt(self):
        self.assertEqual(
            Notification._ldap_datetime_2_dt(131924601300000000),
            pytz.utc.localize(datetime(
                year=2019,
                month=1,
                day=20,
                hour=12,
                minute=15,
                second=30
            ))
        )

    def test_ldap_timedelta_2_timedelta(self):
        expected = timedelta(minutes=15)
        self.assertEqual(
            Notification._ldap_timedelta_2_timedelta(9000000000), expected
        )

    def test_get_parsed_text(self):
        obj = Notification.objects.get(notification_id=1000000404)
        parsed_text = obj.get_parsed_text()
        self.assertEqual(parsed_text['autoTime'], 132186924601059151)
        self.assertEqual(parsed_text['structureName'], 'Dummy')
        self.assertEqual(parsed_text['solarSystemID'], 30002537)
        
    def test_is_npc_attacking(self):
        x1 = Notification.objects.get(notification_id=1000000509)
        self.assertFalse(x1.is_npc_attacking())
        x2 = Notification.objects.get(notification_id=1000010509)
        self.assertTrue(x2.is_npc_attacking())
        x3 = Notification.objects.get(notification_id=1000010601)
        self.assertTrue(x3.is_npc_attacking())
        
    @patch(MODULE_PATH + '.STRUCTURES_REPORT_NPC_ATTACKS', True)
    def test_filter_npc_attacks_1(self):
        # NPC reporting allowed and not a NPC attacker                    
        x1 = Notification.objects.get(notification_id=1000000509)
        self.assertFalse(x1.filter_for_npc_attacks())

        # NPC reporting allowed and a NPC attacker        
        x1 = Notification.objects.get(notification_id=1000010509)
        self.assertFalse(x1.filter_for_npc_attacks())
       
    @patch(MODULE_PATH + '.STRUCTURES_REPORT_NPC_ATTACKS', False)
    def test_filter_npc_attacks_2(self):      
        # NPC reporting not allowed and not a NPC attacker        
        x1 = Notification.objects.get(notification_id=1000000509)
        self.assertFalse(x1.filter_for_npc_attacks())

        # NPC reporting not allowed and a NPC attacker        
        x1 = Notification.objects.get(notification_id=1000010509)
        self.assertTrue(x1.filter_for_npc_attacks())
        
    def test_filter_alliance_level(self):
        # notification is not and owner is not alliance level
        self.owner.is_alliance_main = False
        self.owner.save()
        x1 = Notification.objects.get(notification_id=1000000509)
        self.assertFalse(x1.filter_for_alliance_level())

        # notification is, but owner is not
        self.owner.is_alliance_main = False
        self.owner.save()
        x1 = Notification.objects.get(notification_id=1000000803)
        self.assertTrue(x1.filter_for_alliance_level())

        # notification is and owner is
        self.owner.is_alliance_main = True
        self.owner.save()
        x1 = Notification.objects.get(notification_id=1000000803)
        self.assertFalse(x1.filter_for_alliance_level())

        # notification is not, but owner is
        self.owner.is_alliance_main = True
        self.owner.save()
        x1 = Notification.objects.get(notification_id=1000000509)
        self.assertFalse(x1.filter_for_alliance_level())

    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_to_webhook_all_notification_types(self, mock_execute):
        logger.debug('test_send_to_webhook_normal')
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.status_ok = True
        mock_response.content = None        
        mock_execute.return_value = mock_response

        types_tested = set()
        for x in Notification.objects.all():
            self.assertFalse(x.is_sent)
            self.assertTrue(x.send_to_webhook(self.webhook))
            self.assertTrue(x.is_sent)
            types_tested.add(x.notification_type)

        # make sure we have tested all existing notification types
        self.assertSetEqual(
            Notification.get_all_types(), types_tested
        )

    @patch(MODULE_PATH + '.STRUCTURES_NOTIFICATION_WAIT_SEC', 0)
    @patch(MODULE_PATH + '.STRUCTURES_NOTIFICATION_MAX_RETRIES', 2)    
    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_to_webhook_http_error(self, mock_execute):
        logger.debug('test_send_to_webhook_http_error')        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.status_ok = False
        mock_response.content = None        
        mock_execute.return_value = mock_response
        
        x = Notification.objects.get(notification_id=1000000502)
        self.assertFalse(x.send_to_webhook(self.webhook))

    @patch(MODULE_PATH + '.STRUCTURES_NOTIFICATION_MAX_RETRIES', 2)    
    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_to_webhook_too_many_requests(self, mock_execute):                                
        logger.debug('test_send_to_webhook_too_many_requests')        
        mock_response = Mock()
        mock_response.status_code = Notification.HTTP_CODE_TOO_MANY_REQUESTS
        mock_response.status_ok = False
        mock_response.content = {'retry_after': 100}        
        mock_execute.return_value = mock_response

        x = Notification.objects.get(notification_id=1000000502)
        self.assertFalse(x.send_to_webhook(self.webhook))
        
    @patch(MODULE_PATH + '.settings.DEBUG', False)    
    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_to_webhook_exception(self, mock_execute):
        logger.debug('test_send_to_webhook_exception')        
        mock_execute.side_effect = RuntimeError('Dummy exception')

        x = Notification.objects.get(notification_id=1000000502)
        self.assertFalse(x.send_to_webhook(self.webhook))

    @patch(MODULE_PATH + '.STRUCTURES_DEFAULT_LANGUAGE', 'en')
    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', spec=True)
    def test_send_notification_without_existing_structure(self, mock_execute):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.status_ok = True
        mock_response.content = None        
        mock_execute.return_value = mock_response
        
        Structure.objects.all().delete()
        obj = Notification.objects.get(notification_id=1000000505)
        obj.send_to_webhook(self.webhook)
        embed = mock_execute.call_args[1]['embeds'][0]
        self.assertEqual(
            embed.description[:39], 'The Astrahus **(unknown)** in [Amamake]'
        )

    @patch(MODULE_PATH + '.STRUCTURES_DEFAULT_LANGUAGE', 'en')
    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', spec=True)
    def test_anchoring_in_low_sec_has_timer(self, mock_execute):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.status_ok = True
        mock_response.content = None        
        mock_execute.return_value = mock_response
                
        obj = Notification.objects.get(notification_id=1000000501)
        obj.send_to_webhook(self.webhook)
        embed = mock_execute.call_args[1]['embeds'][0]
        self.assertIn('The anchoring timer ends at', embed.description)

    @patch(MODULE_PATH + '.STRUCTURES_DEFAULT_LANGUAGE', 'en')
    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', spec=True)
    def test_anchoring_in_null_sec_no_timer(self, mock_execute):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.status_ok = True
        mock_response.content = None        
        mock_execute.return_value = mock_response
                
        obj = Notification.objects.get(notification_id=1000010501)
        obj.send_to_webhook(self.webhook)
        embed = mock_execute.call_args[1]['embeds'][0]
        self.assertNotIn('The anchoring timer ends at', embed.description)
        

class TestNotificationAddToTimerboard(NoSocketsTestCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        my_user, cls.owner = set_owner_character(character_id=1001)        
        load_notification_entities(cls.owner)        
        cls.webhook = Webhook.objects.create(
            name='Test', url='http://www.example.com/dummy/'
        )
        cls.owner.webhooks.add(cls.webhook)
        Timer.objects.all().delete()
        
    @patch(MODULE_PATH + '.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED', False)
    @patch('allianceauth.timerboard.models.Timer', spec=True)
    def test_setting_disabled(self, mock_Timer):
        x = Notification.objects.get(notification_id=1000000404)
        self.assertFalse(x.process_for_timerboard())
        self.assertFalse(mock_Timer.objects.create.called)

        x = Notification.objects.get(notification_id=1000000402)
        self.assertFalse(x.process_for_timerboard())
        self.assertFalse(mock_Timer.delete.called)
    
    @patch(MODULE_PATH + '.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED', True)
    def test_normal(self):        
        notification_without_timer_query = Notification.objects\
            .filter(notification_id__in=[
                1000000401,
                1000000403,                
                1000000405,                
                1000000502,
                1000000503,                
                1000000506,
                1000000507,
                1000000508,
                1000000509,
                1000000510,
                1000000511,
                1000000512,
                1000000513,                                                
                1000000601,
                1000010509,
                1000010601
            ])
        for x in notification_without_timer_query:
            self.assertFalse(x.process_for_timerboard())
            
        self.assertEqual(Timer.objects.count(), 0)

        x = Notification.objects.get(notification_id=1000000501)
        self.assertTrue(x.process_for_timerboard())
        self.assertEqual(Timer.objects.count(), 1)

        x = Notification.objects.get(notification_id=1000000504)
        self.assertTrue(x.process_for_timerboard())
        self.assertEqual(Timer.objects.count(), 2)

        x = Notification.objects.get(notification_id=1000000505)
        self.assertTrue(x.process_for_timerboard())
        self.assertEqual(Timer.objects.count(), 3)

        x = Notification.objects.get(notification_id=1000000602)
        self.assertTrue(x.process_for_timerboard())
        self.assertEqual(Timer.objects.count(), 4)
        
        ids_set_1 = {x.id for x in Timer.objects.all()}
        x = Notification.objects.get(notification_id=1000000404)
        self.assertTrue(x.process_for_timerboard())
        self.assertEqual(Timer.objects.count(), 5)
                
        # this should remove the right timer only
        x = Notification.objects.get(notification_id=1000000402)
        x.process_for_timerboard()
        self.assertEqual(Timer.objects.count(), 4)
        ids_set_2 = {x.id for x in Timer.objects.all()}
        self.assertSetEqual(ids_set_1, ids_set_2)

    @patch(MODULE_PATH + '.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED', True)
    def test_run_all(self):        
        for x in Notification.objects.all():
            x.process_for_timerboard()

    @patch(MODULE_PATH + '.STRUCTURES_TIMERS_ARE_CORP_RESTRICTED', False)
    def test_corp_restriction_1(self):        
        x = Notification.objects.get(notification_id=1000000504)
        self.assertTrue(x.process_for_timerboard())
        t = Timer.objects.first()
        self.assertFalse(t.corp_timer)
        
    @patch(MODULE_PATH + '.STRUCTURES_TIMERS_ARE_CORP_RESTRICTED', True)
    def test_corp_restriction_2(self):        
        x = Notification.objects.get(notification_id=1000000504)
        self.assertTrue(x.process_for_timerboard())
        t = Timer.objects.first()
        self.assertTrue(t.corp_timer)

    def test_anchoring_timer_created_for_low_sec(self):        
        obj = Notification.objects.get(notification_id=1000000501)        
        self.assertTrue(obj.process_for_timerboard())
        timer = Timer.objects.first()
        self.assertEqual(
            timer.eve_time, obj.timestamp + timedelta(hours=24)
        )

    def test_anchoring_timer_not_created_for_null_sec(self):        
        obj = Notification.objects.get(notification_id=1000010501)        
        self.assertFalse(obj.process_for_timerboard())
        self.assertIsNone(Timer.objects.first())
