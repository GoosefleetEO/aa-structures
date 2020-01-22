from datetime import timedelta
from random import randrange
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo

from . import set_logger
from .testdata import entities_testdata, notifications_testdata
from ..models import *


logger = set_logger('structures.views', __file__)


class TestWebhook(TestCase):

    def setUp(self):
        self.my_webhook = Webhook(
            name='Dummy Webhook',
            url='https://www.example.com'
        )
    
    def test_str(self):        
        self.assertEqual(str(self.my_webhook), 'Dummy Webhook')

    
    @patch('structures.models.dhooks_lite.Webhook.execute')
    def test_send_test_notification_ok(self, mock_execute):        
        mock_response = Mock()
        mock_response.status_ok = True        
        expected_send_report = {'dummy': 'abc123'}
        mock_response.content = expected_send_report
        mock_execute.return_value = mock_response

        response = self.my_webhook.send_test_notification()
        self.assertDictEqual(json.loads(response), expected_send_report)


    @patch('structures.models.dhooks_lite.Webhook.execute')
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
        entities_def = [            
            EveAllianceInfo,
            EveCorporationInfo,
            EveCharacter 
        ]
    
        for EntityClass in entities_def:
            entity_name = EntityClass.__name__
            for x in entities_testdata[entity_name]:
                EntityClass.objects.create(**x)
            assert(len(entities_testdata[entity_name]) == EntityClass.objects.count())
                
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
    

    def test_str(self):
        x = Owner.objects.get(
            corporation__corporation_id=2001
        )
        self.assertEqual(str(x), 'Wayne Technologies')
    

    @patch('structures.models.STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES', 30)
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

    
    @patch('structures.models.STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES', 30)
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


    @patch('structures.models.STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES', 30)
    def test_is_notification_sync_ok(self):
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


    @patch('structures.models.STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES', 30)
    @patch('structures.models.STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES', 30)
    @patch('structures.models.STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES', 30)
    def test_is_notification_sync_ok(self):
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
        
        #normal error
        self.assertEqual(
            Owner.to_friendly_error_message(Owner.ERROR_NO_CHARACTER), 
            'No character set for fetching data from ESI'
        )

        #normal error
        self.assertEqual(
            Owner.to_friendly_error_message(0), 
            'No error'
        )

        #undefined error
        self.assertEqual(
            Owner.to_friendly_error_message(9876), 
            'Undefined error'
        )

        #undefined error
        self.assertEqual(
            Owner.to_friendly_error_message(-1), 
            'Undefined error'
        )

    
    @patch('structures.models.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    def test_get_esi_scopes_pocos_off(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                'esi-corporations.read_structures.v1',
                'esi-universe.read_structures.v1',
                'esi-characters.read_notifications.v1'
            }
        )

    @patch('structures.models.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
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


class TestEveEntities(TestCase):

    def setUp(self):
                  
        entities_def = [
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveMoon,
            EveGroup,
            EveType,            
            EveEntity    
        ]
    
        for EntityClass in entities_def:
            entity_name = EntityClass.__name__
            for x in entities_testdata[entity_name]:
                EntityClass.objects.create(**x)
            assert(len(entities_testdata[entity_name]) == EntityClass.objects.count())


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
            EveEntity.get_matching_entity_type('character'),
            EveEntity.CATEGORY_CHARACTER
        )
        self.assertEqual(
            EveEntity.get_matching_entity_type('corporation'),
            EveEntity.CATEGORY_CORPORATION
        )
        self.assertEqual(
            EveEntity.get_matching_entity_type('alliance'),
            EveEntity.CATEGORY_ALLIANCE
        )
        self.assertEqual(
            EveEntity.get_matching_entity_type('faction'),
            EveEntity.CATEGORY_FACTION
        )
        self.assertEqual(
            EveEntity.get_matching_entity_type('other'),
            EveEntity.CATEGORY_OTHER
        )
        with self.assertRaises(ValueError):
            EveEntity.get_matching_entity_type('does not exist')


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
            for x in entities_testdata[entity_name]:
                EntityClass.objects.create(**x)
            assert(len(entities_testdata[entity_name]) == EntityClass.objects.count())
                
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

        # create Structure objects
        for structure in entities_testdata['Structure']:
            x = structure.copy()
            x['owner'] = Owner.objects.get(
                corporation__corporation_id=x['owner_corporation_id']
            )
            del x['owner_corporation_id']
            Structure.objects.create(**x)

        # create StructureTag objects
        StructureTag.objects.all().delete()
        for x in entities_testdata['StructureTag']:
            StructureTag.objects.create(**x)


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


    def test_get_matching_state(self):
        self.assertEqual(
            Structure.get_matching_state('anchoring'), 
            Structure.STATE_ANCHORING
        )
        self.assertEqual(
            Structure.get_matching_state('not matching name'), 
            Structure.STATE_UNKNOWN
        )

    def test_structure_service_str(self):
        structure = Structure.objects.get(id=1000000000001)
        x = StructureService(
            structure=structure,
            name='Dummy',
            state=StructureService.STATE_ONLINE
        )
        self.assertEqual(str(x), 'Amamake - Test Structure Alpha - Dummy')


    def test_get_matching_state(self):
        self.assertEqual(
            StructureService.get_matching_state('online'), 
            StructureService.STATE_ONLINE
        )
        self.assertEqual(
            StructureService.get_matching_state('offline'), 
            StructureService.STATE_OFFLINE
        )


class TestNotification(TestCase):
    
    def setUp(self):         
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
            for x in entities_testdata[entity_name]:
                EntityClass.objects.create(**x)
            assert(
                len(entities_testdata[entity_name]) == EntityClass.objects.count()
            )
                
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

    def test_str(self):
        x = Notification.objects.get(notification_id=1000000403)
        self.assertEqual(str(x), '1000000403')