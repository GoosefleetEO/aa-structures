from datetime import timedelta, datetime
import json
from unittest.mock import Mock, patch

import pytz

from django.test import TestCase
from django.utils.timezone import now

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo
from allianceauth.timerboard.models import Timer

from . import set_logger
from .testdata import (
    load_entities,
    load_notification_entities,
    create_structures,
    set_owner_character
)
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
    EveEntity,
    Owner,
    Notification,
    Structure
)

MODULE_PATH = 'structures.models'
logger = set_logger(MODULE_PATH, __file__)


class TestWebhook(TestCase):

    def setUp(self):
        self.my_webhook = Webhook(
            name='Dummy Webhook',
            url='https://www.example.com'
        )

    def test_str(self):
        self.assertEqual(str(self.my_webhook), 'Dummy Webhook')

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


class TestOwner(TestCase):

    def setUp(self):
        load_entities([
            EveAllianceInfo,
            EveCorporationInfo,
            EveCharacter
        ])

        for corporation in EveCorporationInfo.objects.all():
            EveEntity.objects.get_or_create(
                id=corporation.corporation_id,
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
                id=character.character_id,
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

        set_owner_character(character_id=1001)

    def test_str(self):
        x = Owner.objects.get(
            corporation__corporation_id=2001
        )
        self.assertEqual(str(x), 'Wayne Technologies')
    
    @patch(MODULE_PATH + '.STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES', 30)
    def test_is_structure_sync_ok(self):
        x = Owner.objects.get(
            corporation__corporation_id=2001
        )
        # no errors and recent sync
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now()
        self.assertTrue(x.is_structure_sync_ok())

        # no errors and sync within grace period
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now() - timedelta(minutes=29)
        self.assertTrue(x.is_structure_sync_ok())

        # recent sync error 
        x.structures_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
        x.structures_last_sync = now()
        self.assertFalse(x.is_structure_sync_ok())
        
        # no error, but no sync within grace period
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now() - timedelta(minutes=31)
        self.assertFalse(x.is_structure_sync_ok())
    
    @patch(MODULE_PATH + '.STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES', 30)
    def test_is_notification_sync_ok(self):
        x = Owner.objects.get(
            corporation__corporation_id=2001
        )
        # no errors and recent sync
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now()
        self.assertTrue(x.is_notification_sync_ok())

        # no errors and sync within grace period
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now() - timedelta(minutes=29)
        self.assertTrue(x.is_notification_sync_ok())

        # recent sync error 
        x.notifications_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
        x.notifications_last_sync = now()
        self.assertFalse(x.is_notification_sync_ok())
        
        # no error, but no sync within grace period
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now() - timedelta(minutes=31)
        self.assertFalse(x.is_notification_sync_ok())

    @patch(MODULE_PATH + '.STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES', 30)
    def test_is_forwarding_sync_ok(self):
        x = Owner.objects.get(
            corporation__corporation_id=2001
        )
        # no errors and recent sync
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now()
        self.assertTrue(x.is_forwarding_sync_ok())

        # no errors and sync within grace period
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now() - timedelta(minutes=29)
        self.assertTrue(x.is_forwarding_sync_ok())

        # recent sync error 
        x.forwarding_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
        x.forwarding_last_sync = now()
        self.assertFalse(x.is_forwarding_sync_ok())
        
        # no error, but no sync within grace period
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now() - timedelta(minutes=31)
        self.assertFalse(x.is_forwarding_sync_ok())

    @patch(MODULE_PATH + '.STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES', 30)
    @patch(MODULE_PATH + '.STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES', 30)
    @patch(MODULE_PATH + '.STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES', 30)
    def test_is_all_syncs_ok(self):
        x = Owner.objects.get(
            corporation__corporation_id=2001
        )
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now()
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now()
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now()
        self.assertTrue(x.is_all_syncs_ok())

    def test_to_friendly_error_message(self):
        # normal error
        self.assertEqual(
            Owner.to_friendly_error_message(Owner.ERROR_NO_CHARACTER), 
            'No character set for fetching data from ESI'
        )
        # normal error
        self.assertEqual(
            Owner.to_friendly_error_message(0), 
            'No error'
        )
        # undefined error
        self.assertEqual(
            Owner.to_friendly_error_message(9876), 
            'Undefined error'
        )
        # undefined error
        self.assertEqual(
            Owner.to_friendly_error_message(-1), 
            'Undefined error'
        )

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    def test_get_esi_scopes_pocos_off(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                'esi-corporations.read_structures.v1',
                'esi-universe.read_structures.v1',
                'esi-characters.read_notifications.v1'
            }
        )

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    def test_get_esi_scopes_pocos_on(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                'esi-corporations.read_structures.v1',
                'esi-universe.read_structures.v1',
                'esi-characters.read_notifications.v1',
                'esi-planets.read_customs_offices.v1',
                'esi-assets.read_corporation_assets.v1'
            }
        )

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', True)
    def test_get_esi_scopes_starbases_on(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                'esi-corporations.read_structures.v1',
                'esi-universe.read_structures.v1',
                'esi-characters.read_notifications.v1',
                'esi-corporations.read_starbases.v1'
            }
        )

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', True)
    def test_get_esi_scopes_starbases_and_custom_offices(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                'esi-corporations.read_structures.v1',
                'esi-universe.read_structures.v1',
                'esi-characters.read_notifications.v1',
                'esi-corporations.read_starbases.v1',
                'esi-planets.read_customs_offices.v1',
                'esi-assets.read_corporation_assets.v1'
            }
        )


class TestEveType(TestCase):

    def setUp(self):                          
        load_entities([
            EveCategory,
            EveGroup,
            EveType,          
        ])
        self.type_astrahus = EveType.objects.get(id=35832)
        self.type_poco = EveType.objects.get(id=2233)
        self.type_starbase = EveType.objects.get(id=16213)

    def test_str(self):
        self.assertEqual(str(self.type_astrahus), self.type_astrahus.name)

    def test_is_poco(self):
        self.assertFalse(self.type_astrahus.is_poco)
        self.assertTrue(self.type_poco.is_poco)
        self.assertFalse(self.type_starbase.is_poco)

    def test_is_starbase(self):
        self.assertFalse(self.type_astrahus.is_starbase)
        self.assertFalse(self.type_poco.is_starbase)
        self.assertTrue(self.type_starbase.is_starbase)

    def test_is_upwell_structure(self):
        self.assertTrue(self.type_astrahus.is_upwell_structure)
        self.assertFalse(self.type_poco.is_upwell_structure)
        self.assertFalse(self.type_starbase.is_upwell_structure)

    def test_generic_icon_url_normal(self):
        self.assertEqual(
            EveType.generic_icon_url(self.type_astrahus.id),
            'https://images.evetech.net/types/35832/icon?size=64'
        )

    def test_generic_icon_url_w_size(self):
        self.assertEqual(
            EveType.generic_icon_url(self.type_astrahus.id, 128),
            'https://images.evetech.net/types/35832/icon?size=128'
        )

    def test_generic_icon_url_invalid_size(self):
        with self.assertRaises(ValueError):
            EveType.generic_icon_url(self.type_astrahus.id, 127)
            
    def test_icon_url(self):
        self.assertEqual(
            EveType.generic_icon_url(self.type_astrahus.id),
            self.type_astrahus.icon_url()
        )


class TestEveEntities(TestCase):

    def setUp(self):
                          
        load_entities([
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveMoon,            
            EvePlanet,            
            EveEntity    
        ])

    def test_region_str(self):
        x = EveRegion.objects.get(id=10000005)
        self.assertEqual(str(x), 'Detorid')

    def test_constellation_str(self):
        x = EveConstellation.objects.get(id=20000069)
        self.assertEqual(str(x), '1RG-GU')

    def test_solar_system_str(self):
        x = EveSolarSystem.objects.get(id=30002537)
        self.assertEqual(str(x), 'Amamake')

    def test_moon_str(self):
        x = EveMoon.objects.get(id=40161465)
        self.assertEqual(str(x), 'Amamake II - Moon 1')

    def test_planet_str(self):
        x = EvePlanet.objects.get(id=40161469)
        self.assertEqual(str(x), 'Amamake IV')

    def test_group_str(self):
        x = EveGroup.objects.get(id=1406)
        self.assertEqual(str(x), 'Refinery')

    def test_type_str(self):
        x = EveType.objects.get(id=35835)
        self.assertEqual(str(x), 'Athanor')

    def test_type_icon_url(self):
        x = EveType.objects.get(id=35835)
        self.assertEqual(
            x.icon_url(), 
            'https://images.evetech.net/types/35835/icon?size=64'
        )
        self.assertEqual(
            x.icon_url(size=128), 
            'https://images.evetech.net/types/35835/icon?size=128'
        )

    def test_is_poco(self):
        x = EveType.objects.get(id=2233) 
        self.assertTrue(x.is_poco)

        x = EveType.objects.get(id=35835) 
        self.assertFalse(x.is_poco)

    def test_eveentity_str(self):
        x = EveEntity.objects.get(id=3011)
        self.assertEqual(str(x), 'Big Bad Alliance')
    
    def test_eveentity_get_matching_entity_type(self):
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
        

class TestStructureTag(TestCase):
    
    def test_str(self):        
        x = StructureTag(
            name='Super cool tag'
        )
        self.assertEqual(str(x), 'Super cool tag')

    def test_list_sorted(self):                
        x1 = StructureTag(name='Alpha')
        x2 = StructureTag(name='charlie')
        x3 = StructureTag(name='bravo')
        tags = [x1, x2, x3]
        
        self.assertListEqual(
            StructureTag.sorted(tags),
            [x1, x3, x2]
        )
        self.assertListEqual(
            StructureTag.sorted(tags, reverse=True),
            [x2, x3, x1]
        )
        
    def test_html_default(self):
        x = StructureTag(
            name='Super cool tag'
        )
        self.assertEqual(
            x.html, 
            '<span class="label label-default">Super cool tag</span>'
        )

    def test_html_primary(self):
        x = StructureTag(
            name='Super cool tag',
            style='primary'
        )
        self.assertEqual(
            x.html, 
            '<span class="label label-primary">Super cool tag</span>'
        )


class TestStructure(TestCase):

    def setUp(self):                  
        create_structures()        
        set_owner_character(character_id=1001)
        
    def test_state_str(self):
        x = Structure.objects.get(id=1000000000001)
        x.state = Structure.STATE_ANCHORING
        self.assertEqual(x.state_str, 'anchoring')

    def test_is_low_power(self):
        x = Structure.objects.get(id=1000000000001)
        
        x.fuel_expires = None
        self.assertTrue(x.is_low_power)
        
        x.fuel_expires = now() + timedelta(days=3)
        self.assertFalse(x.is_low_power)

    def test_is_reinforced(self):
        x = Structure.objects.get(id=1000000000001)

        x.state = Structure.STATE_SHIELD_VULNERABLE
        self.assertFalse(x.is_reinforced)

        for state in [
            Structure.STATE_ARMOR_REINFORCE, 
            Structure.STATE_HULL_REINFORCE,
            Structure.STATE_ANCHOR_VULNERABLE,
            Structure.STATE_HULL_VULNERABLE
        ]:
            x.state = state
            self.assertTrue(x.is_reinforced)

    def test_str(self):
        x = Structure.objects.get(id=1000000000001)
        self.assertEqual(str(x), 'Amamake - Test Structure Alpha')

    def test_structure_service_str(self):
        structure = Structure.objects.get(id=1000000000001)
        x = StructureService(
            structure=structure,
            name='Dummy',
            state=StructureService.STATE_ONLINE
        )
        self.assertEqual(str(x), 'Amamake - Test Structure Alpha - Dummy')


class TestStructureNoSetup(TestCase):
    
    def test_structure_get_matching_state(self):
        self.assertEqual(
            Structure.get_matching_state('anchoring'), 
            Structure.STATE_ANCHORING
        )
        self.assertEqual(
            Structure.get_matching_state('not matching name'), 
            Structure.STATE_UNKNOWN
        )
    
    def test_structure_service_get_matching_state(self):
        self.assertEqual(
            StructureService.get_matching_state('online'), 
            StructureService.STATE_ONLINE
        )
        self.assertEqual(
            StructureService.get_matching_state('offline'), 
            StructureService.STATE_OFFLINE
        )
        self.assertEqual(
            StructureService.get_matching_state('not matching'), 
            StructureService.STATE_OFFLINE
        )
  

class TestNotification(TestCase):
    
    def setUp(self):         
        create_structures()
        my_user, self.owner = set_owner_character(character_id=1001)        
        load_notification_entities(self.owner)
        
        self.webhook = Webhook.objects.create(
            name='Test',
            url='dummy-url'
        )
        self.owner.webhooks.add(self.webhook)
        self.owner.save()
      
    def test_str(self):
        x = Notification.objects.get(notification_id=1000000403)
        self.assertEqual(str(x), '1000000403')

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
        pass
        # tbd

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

    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', autospec=True)
    def test_send_to_webhook_all_notification_types(
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

        types_tested = set()
        for x in Notification.objects.all():
            self.assertFalse(x.is_sent)
            self.assertTrue(
                x.send_to_webhook(self.webhook, mock_esi_client_factory)
            )
            self.assertTrue(x.is_sent)
            types_tested.add(x.notification_type)

        # make sure we have tested all existing notification types
        self.assertSetEqual(
            Notification.get_all_types(),
            types_tested
        )

    @patch(MODULE_PATH + '.STRUCTURES_NOTIFICATION_WAIT_SEC', 0)
    @patch(MODULE_PATH + '.STRUCTURES_NOTIFICATION_MAX_RETRIES', 2)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', autospec=True)
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

    @patch(MODULE_PATH + '.STRUCTURES_NOTIFICATION_MAX_RETRIES', 2)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', autospec=True)
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
        
    @patch(MODULE_PATH + '.settings.DEBUG', False)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(MODULE_PATH + '.dhooks_lite.Webhook.execute', autospec=True)
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

    @patch(MODULE_PATH + '.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED', False)
    @patch('allianceauth.timerboard.models.Timer', autospec=True)
    def test_add_to_timerboard_setting_disabled(self, mock_Timer):
        x = Notification.objects.get(notification_id=1000000404)
        self.assertFalse(x.process_for_timerboard())
        self.assertFalse(mock_Timer.objects.create.called)

        x = Notification.objects.get(notification_id=1000000402)
        self.assertFalse(x.process_for_timerboard())
        self.assertFalse(mock_Timer.delete.called)
    
    @patch(MODULE_PATH + '.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED', True)
    def test_add_to_timerboard_normal(self):
        Timer.objects.all().delete()        
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
    def test_add_to_timerboard_run_all(self):        
        for x in Notification.objects.all():
            x.process_for_timerboard()

    @patch(MODULE_PATH + '.STRUCTURES_TIMERS_ARE_CORP_RESTRICTED', False)
    def test_add_to_timerboard_corp_restriction_1(self):
        Timer.objects.all().delete()  

        x = Notification.objects.get(notification_id=1000000504)
        self.assertTrue(x.process_for_timerboard())
        t = Timer.objects.first()
        self.assertFalse(t.corp_timer)
        
    @patch(MODULE_PATH + '.STRUCTURES_TIMERS_ARE_CORP_RESTRICTED', True)
    def test_add_to_timerboard_corp_restriction_2(self):
        Timer.objects.all().delete()  

        x = Notification.objects.get(notification_id=1000000504)
        self.assertTrue(x.process_for_timerboard())
        t = Timer.objects.first()
        self.assertTrue(t.corp_timer)
