from copy import deepcopy
from datetime import timedelta, datetime
from unittest.mock import patch, Mock

from bravado.exception import HTTPBadGateway

from django.utils.timezone import now, utc

from allianceauth.eveonline.models import (
    EveCharacter, EveCorporationInfo, EveAllianceInfo
)
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.timerboard.models import Timer
from allianceauth.tests.auth_utils import AuthUtils

from esi.errors import TokenExpiredError, TokenInvalidError

from .. import to_json
from ...models import (
    EveCategory,
    EveGroup,
    EveType,
    EveRegion,
    EveConstellation,
    EveSolarSystem,
    EveMoon,
    EvePlanet,
    EveEntity,
    StructureTag,
    StructureService,
    Webhook,    
    Owner,
    Notification,
    Structure    
)
from ...models.notifications import (   
    NTYPE_STRUCTURE_DESTROYED,    
    NTYPE_STRUCTURE_LOST_ARMOR,
    NTYPE_STRUCTURE_LOST_SHIELD,    
    NTYPE_STRUCTURE_UNDER_ATTACK,    
    NTYPE_MOONS_AUTOMATIC_FRACTURE,
    NTYPE_MOONS_EXTRACTION_CANCELED,
    NTYPE_MOONS_EXTRACTION_FINISHED,
    NTYPE_MOONS_EXTRACTION_STARTED,
    NTYPE_MOONS_LASER_FIRED
)
from ..testdata import (
    esi_get_corporations_corporation_id_structures,     
    esi_get_corporations_corporation_id_customs_offices,
    esi_post_corporations_corporation_id_assets_names,
    esi_get_universe_structures_structure_id,
    entities_testdata,
    esi_corp_structures_data,
    load_entities,
    load_notification_entities,
    get_all_notification_ids,
    create_structures,
    set_owner_character,
    esi_mock_client,
    create_user
)
from ...utils import set_test_logger, NoSocketsTestCase

MODULE_PATH = 'structures.models.owners'
logger = set_test_logger(MODULE_PATH, __file__)


class TestOwner(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
        obj = Owner.objects.get(corporation__corporation_id=2001)
        self.assertEqual(str(obj), 'Wayne Technologies')
    
    def test_repr(self):
        obj = Owner.objects.get(corporation__corporation_id=2001)
        expected = 'Owner(pk=%d, corporation=\'Wayne Technologies\')' % obj.pk
        self.assertEqual(repr(obj), expected)
    
    @patch(MODULE_PATH + '.STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES', 30)
    def test_is_structure_sync_ok(self):
        x = Owner.objects.get(
            corporation__corporation_id=2001
        )
        # no errors and recent sync
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now()
        self.assertTrue(x.is_structure_sync_ok)

        # no errors and sync within grace period
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now() - timedelta(minutes=29)
        self.assertTrue(x.is_structure_sync_ok)

        # recent sync error 
        x.structures_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
        x.structures_last_sync = now()
        self.assertFalse(x.is_structure_sync_ok)
        
        # no error, but no sync within grace period
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now() - timedelta(minutes=31)
        self.assertFalse(x.is_structure_sync_ok)
    
    @patch(MODULE_PATH + '.STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES', 30)
    def test_is_notification_sync_ok(self):
        x = Owner.objects.get(
            corporation__corporation_id=2001
        )
        # no errors and recent sync
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now()
        self.assertTrue(x.is_notification_sync_ok)

        # no errors and sync within grace period
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now() - timedelta(minutes=29)
        self.assertTrue(x.is_notification_sync_ok)

        # recent sync error 
        x.notifications_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
        x.notifications_last_sync = now()
        self.assertFalse(x.is_notification_sync_ok)
        
        # no error, but no sync within grace period
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now() - timedelta(minutes=31)
        self.assertFalse(x.is_notification_sync_ok)

    @patch(MODULE_PATH + '.STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES', 30)
    def test_is_forwarding_sync_ok(self):
        x = Owner.objects.get(
            corporation__corporation_id=2001
        )
        # no errors and recent sync
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now()
        self.assertTrue(x.is_forwarding_sync_ok)

        # no errors and sync within grace period
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now() - timedelta(minutes=29)
        self.assertTrue(x.is_forwarding_sync_ok)

        # recent sync error 
        x.forwarding_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
        x.forwarding_last_sync = now()
        self.assertFalse(x.is_forwarding_sync_ok)
        
        # no error, but no sync within grace period
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now() - timedelta(minutes=31)
        self.assertFalse(x.is_forwarding_sync_ok)

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
        self.assertTrue(x.are_all_syncs_ok)

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


class TestUpdateStructuresEsi(NoSocketsTestCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # test data
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
        cls.character = EveCharacter.objects.get(character_id=1001)
                
        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        cls.user = AuthUtils.create_user(cls.character.character_name)
        AuthUtils.add_permission_to_user_by_name(
            'structures.add_structure_owner', cls.user
        )
        
        cls.main_ownership = CharacterOwnership.objects.create(
            character=cls.character,
            owner_hash='x1',
            user=cls.user
        )        
        Structure.objects.all().delete()
        
        # create StructureTag objects
        StructureTag.objects.all().delete()
        for x in entities_testdata['StructureTag']:
            StructureTag.objects.create(**x)
    
    def setUp(self):
        # reset data that might be overridden        
        esi_get_corporations_corporation_id_structures.override_data = None
        esi_get_corporations_corporation_id_customs_offices.override_data = \
            None
        
    def test_returns_error_when_no_sync_char_defined(self):
        owner = Owner.objects.create(
            corporation=self.corporation            
        )
        self.assertFalse(
            owner.update_structures_esi()
        )
        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_NO_CHARACTER
        )

    def test_returns_error_when_char_has_no_permission(self):
        user_2 = create_user(1002)        
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=user_2.character_ownerships.first()
        )        
        self.assertFalse(
            owner.update_structures_esi()
        )
        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_INSUFFICIENT_PERMISSIONS
        )    

    @patch(MODULE_PATH + '.Token')    
    def test_returns_error_when_token_is_expired(self, mock_Token):
        mock_Token.objects.filter.side_effect = TokenExpiredError()        
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )
        
        # run update task
        self.assertFalse(owner.update_structures_esi())

        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_TOKEN_EXPIRED            
        )
        
    @patch(MODULE_PATH + '.Token')
    def test_returns_error_when_token_is_invalid(self, mock_Token):
        mock_Token.objects.filter.side_effect = TokenInvalidError()        
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )
        
        # run update task
        self.assertFalse(owner.update_structures_esi())

        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, 
            Owner.ERROR_TOKEN_INVALID            
        )
    
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)    
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_can_sync_upwell_structures(
        self, mock_esi_client_factory, mock_Token
    ):
        mock_esi_client_factory.return_value = esi_mock_client()
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )        
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)
        
        # must contain all expected structures
        structure_ids = {x['id'] for x in Structure.objects.values('id')}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

        # verify attributes for structure
        structure = Structure.objects.get(id=1000000000001)
        self.assertEqual(structure.name, 'Test Structure Alpha')
        self.assertEqual(structure.position_x, 55028384780.0)
        self.assertEqual(structure.position_y, 7310316270.0)
        self.assertEqual(structure.position_z, -163686684205.0)
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(structure.eve_type_id, 35832)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.state, Structure.STATE_SHIELD_VULNERABLE)
        self.assertEqual(structure.reinforce_hour, 18)
        self.assertEqual(structure.fuel_expires, datetime(
            2020, 3, 5, 5, 0, 0, tzinfo=utc
        ))
        self.assertEqual(structure.state_timer_start, datetime(
            2020, 4, 5, 6, 30, 0, tzinfo=utc
        ))
        self.assertEqual(structure.state_timer_end, datetime(
            2020, 4, 5, 7, 0, 0, tzinfo=utc
        ))
        self.assertEqual(structure.unanchors_at, datetime(
            2020, 5, 5, 6, 30, 0, tzinfo=utc
        ))
        
        # must have created services with localizations
        # structure 1000000000001        
        expected = {
            to_json({
                'name': 'Clone Bay', 
                'name_de': 'Clone Bay_de',
                'name_ko': 'Clone Bay_ko',
                'name_ru': 'Clone Bay_ru',
                'name_zh': 'Clone Bay_zh',
                'state': StructureService.STATE_ONLINE 
            }),
            to_json({
                'name': 'Market Hub', 
                'name_de': 'Market Hub_de',
                'name_ko': 'Market Hub_ko',
                'name_ru': 'Market Hub_ru',
                'name_zh': 'Market Hub_zh',
                'state': StructureService.STATE_OFFLINE, 
            }) 
        }
        structure = Structure.objects.get(id=1000000000001)
        services = {
            to_json({
                'name': x.name,
                'name_de': x.name_de,
                'name_ko': x.name_ko,
                'name_ru': x.name_ru,
                'name_zh': x.name_zh,
                'state': x.state
            }) 
            for x in structure.structureservice_set.all()
        }
        self.assertEqual(services, expected)

        # must have created services with localizations
        # structure 1000000000002       
        expected = {
            to_json({
                'name': 'Reprocessing', 
                'name_de': 'Reprocessing_de',
                'name_ko': 'Reprocessing_ko',
                'name_ru': 'Reprocessing_ru',
                'name_zh': 'Reprocessing_zh',
                'state': StructureService.STATE_ONLINE 
            }),
            to_json({
                'name': 'Moon Drilling', 
                'name_de': 'Moon Drilling_de',
                'name_ko': 'Moon Drilling_ko',
                'name_ru': 'Moon Drilling_ru',
                'name_zh': 'Moon Drilling_zh',
                'state': StructureService.STATE_ONLINE, 
            }) 
        }
        structure = Structure.objects.get(id=1000000000002)
        services = {
            to_json({
                'name': x.name,
                'name_de': x.name_de,
                'name_ko': x.name_ko,
                'name_ru': x.name_ru,
                'name_zh': x.name_zh,
                'state': x.state
            }) 
            for x in structure.structureservice_set.all()
        }
        self.assertEqual(services, expected)

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)    
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_can_sync_pocos(self, mock_esi_client_factory, mock_Token):
        mock_esi_client_factory.return_value = esi_mock_client()
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )        
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)
        
        # must contain all expected structures
        structure_ids = {x['id'] for x in Structure.objects.values('id')}
        expected = {
            1000000000001, 
            1000000000002, 
            1000000000003, 
            1200000000003, 
            1200000000004, 
            1200000000005
        }
        self.assertSetEqual(structure_ids, expected)

        # verify attributes for POCO
        structure = Structure.objects.get(id=1200000000003)        
        self.assertEqual(structure.name, 'Planet (Barren)')
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, EveType.EVE_TYPE_ID_POCO)
        self.assertEqual(structure.reinforce_hour, 20)
        self.assertEqual(structure.state, Structure.STATE_UNKNOWN)
        self.assertEqual(structure.eve_planet_id, 40161472)

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', True)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)    
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_can_sync_starbases(self, mock_esi_client_factory, mock_Token):
        mock_esi_client_factory.return_value = esi_mock_client()
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )        
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)
        
        # must contain all expected structures
        structure_ids = {x['id'] for x in Structure.objects.values('id')}
        expected = {
            1000000000001, 
            1000000000002, 
            1000000000003, 
            1300000000001, 
            1300000000002
        }
        self.assertSetEqual(structure_ids, expected)

        # verify attributes for POS
        structure = Structure.objects.get(id=1300000000001)        
        self.assertEqual(structure.name, 'Home Sweat Home')
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 16213)        
        self.assertEqual(structure.state, Structure.STATE_POS_ONLINE)
        self.assertEqual(structure.eve_moon_id, 40161465)
        self.assertEqual(structure.state_timer_end, datetime(
            2020, 4, 5, 7, 0, 0, tzinfo=utc
        ))
        self.assertEqual(structure.unanchors_at, datetime(
            2020, 5, 5, 7, 0, 0, tzinfo=utc
        ))

        structure = Structure.objects.get(id=1300000000002)        
        self.assertEqual(structure.name, 'Bat cave')
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 16214)        
        self.assertEqual(structure.state, Structure.STATE_POS_OFFLINE)
        self.assertEqual(structure.eve_moon_id, 40161466)
    
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', True)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_can_sync_all_structures(
        self, mock_esi_client_factory, mock_Token, mock_notify
    ):                                       
        mock_esi_client_factory.return_value = esi_mock_client()
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )        
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)
        
        # must contain all expected structures
        structure_ids = {x['id'] for x in Structure.objects.values('id')}
        expected = {
            1000000000001, 
            1000000000002, 
            1000000000003, 
            1200000000003,
            1200000000004,
            1200000000005,
            1300000000001,
            1300000000002,
        }
        self.assertSetEqual(structure_ids, expected)
                
        # user report has been sent
        self.assertTrue(mock_notify.called)

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_removes_old_structures(
        self, mock_esi_client_factory, mock_Token
    ):                       
        mock_esi_client_factory.return_value = esi_mock_client()        
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )        
        
        # run update task with all structures
        owner.update_structures_esi()        
        
        # should contain the right structures
        structure_ids = {x['id'] for x in Structure.objects.values('id')}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

        # run update task 2nd time with one less structure
        my_corp_structures_data = deepcopy(esi_corp_structures_data)
        del(my_corp_structures_data["2001"][1])
        esi_get_corporations_corporation_id_structures.override_data = \
            my_corp_structures_data
        owner.update_structures_esi()

        # should contain only the remaining structures        
        structure_ids = {x['id'] for x in Structure.objects.values('id')}
        expected = {1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_tags_are_not_modified_by_update(
        self, mock_esi_client_factory, mock_Token
    ):                               
        mock_client = Mock()        
        mock_client.Corporation\
            .get_corporations_corporation_id_structures.side_effect = \
            esi_get_corporations_corporation_id_structures
        mock_client.Universe\
            .get_universe_structures_structure_id.side_effect =\
            esi_get_universe_structures_structure_id
        mock_esi_client_factory.return_value = mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )        
        
        # run update task with all structures
        owner.update_structures_esi()
        # should contain the right structures        
        structure_ids = {x['id'] for x in Structure.objects.values('id')}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

        # adding tags
        tag_a = StructureTag.objects.get(name='tag_a')
        s = Structure.objects.get(id=1000000000001)
        s.tags.add(tag_a)
        s.save()
        
        # run update task 2nd time
        owner.update_structures_esi()
        
        # should still contain alls structures
        structure_ids = {x['id'] for x in Structure.objects.values('id')}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

        # should still contain the tag
        s_new = Structure.objects.get(id=1000000000001)
        self.assertEqual(s_new.tags.get(name='tag_a'), tag_a)
    
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_remove_current_structures_when_esi_returns_none(
        self, mock_esi_client_factory, mock_Token
    ):                               
        esi_get_corporations_corporation_id_structures.override_data = \
            {'2001': []}
        esi_get_corporations_corporation_id_customs_offices.override_data = \
            {'2001': []}        
        mock_esi_client_factory.return_value = esi_mock_client()       
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        
        # run update task
        self.assertTrue(owner.update_structures_esi())
        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, Owner.ERROR_NONE            
        )                
        # must be empty
        self.assertEqual(Structure.objects.count(), 0)

    @patch(MODULE_PATH + '.settings.DEBUG', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.notify')
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_reports_error_to_user_when_update_fails(
        self, mock_esi_client_factory, mock_Token, mock_notify
    ):                               
        esi_get_corporations_corporation_id_structures.override_data = \
            {'2001': []}
        esi_get_corporations_corporation_id_customs_offices.override_data = \
            {'2001': []}        
        mock_esi_client_factory.return_value = esi_mock_client()
        mock_notify.side_effect = RuntimeError    
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
    
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_removes_outdated_services(
        self, mock_esi_client_factory, mock_Token
    ):                       
        mock_esi_client_factory.return_value = esi_mock_client()
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )        
        
        # run update task with all structures
        owner.update_structures_esi(user=self.user)
        structure = Structure.objects.get(id=1000000000002)        
        self.assertEqual(
            {
                x.name 
                for x in StructureService.objects.filter(structure=structure)
            },
            {'Reprocessing', 'Moon Drilling'}
        )
        
        # run update task 2nd time after removing a service
        my_corp_structures_data = deepcopy(esi_corp_structures_data)
        del(my_corp_structures_data['2001'][0]['services'][0])
        esi_get_corporations_corporation_id_structures.override_data = \
            my_corp_structures_data
        owner.update_structures_esi(user=self.user)     
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
    def test_define_poco_name_from_assets_if_not_match_with_planets(
        self, mock_esi_client_factory, mock_Token, mock_notify
    ):                               
        mock_esi_client_factory.return_value = esi_mock_client()
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        EvePlanet.objects.all().delete()
        
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))

        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, 'Amamake V')

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_define_poco_name_from_planet_type_if_found(
        self, mock_esi_client_factory, mock_Token, mock_notify
    ):                               
        mock_esi_client_factory.return_value = esi_mock_client()        
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )                
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))

        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, 'Planet (Barren)')

    @patch(MODULE_PATH + '.STRUCTURES_DEFAULT_LANGUAGE', 'de')
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_define_poco_name_from_planet_type_localized(
        self, mock_esi_client_factory, mock_Token, mock_notify
    ):                               
        mock_esi_client_factory.return_value = esi_mock_client()        
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )                
        # run update task        
        self.assertTrue(owner.update_structures_esi(user=self.user))

        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, 'Planet (Barren)_de')

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_update_pocos_no_asset_name_match(
        self, mock_esi_client_factory, mock_Token, mock_notify
    ):
        esi_post_corporations_corporation_id_assets_names.override_data = {
            "2001": []
        }
        mock_esi_client_factory.return_value = esi_mock_client()      
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        EvePlanet.objects.all().delete()
        
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, '')
        esi_post_corporations_corporation_id_assets_names.override_data = None

    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Structure.objects.update_or_create_from_dict')
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_reports_error_during_storing(
        self, 
        mock_esi_client_factory,
        mock_Token,
        mock_update_or_create_from_dict
    ):                       
        mock_esi_client_factory.return_value = esi_mock_client()
        mock_update_or_create_from_dict.side_effect = RuntimeError

        # create test data        
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )        
        
        # run update task with all structures        
        self.assertFalse(owner.update_structures_esi())


class TestUpdateStructuresEsi2(NoSocketsTestCase):

    def setUp(self):
        self.default_lang = 'en-us'
        self.structures_w_lang = {
            'en-us': [
                {
                    'structure_id': 1001,
                    'services':
                    [
                        {
                            'name': 'alpha',
                            'state': 'online'
                        },
                        {
                            'name': 'bravo',
                            'state': 'online'
                        }
                    ],
                },
                {
                    'structure_id': 1002,
                    'services':
                    [
                        {
                            'name': 'bravo',
                            'state': 'offline'
                        }
                    ],
                }
            ],
            'ko': [
                {
                    'structure_id': 1001,
                    'services':
                    [
                        {
                            'name': 'alpha_ko',
                            'state': 'online'
                        },
                        {
                            'name': 'bravo_ko',
                            'state': 'online'
                        }
                    ],
                },
                {
                    'structure_id': 1002,
                    'services':
                    [
                        {
                            'name': 'bravo_ko',
                            'state': 'offline'
                        }
                    ],
                }
            ],
            'de': [
                {
                    'structure_id': 1001,
                    'services':
                    [
                        {
                            'name': 'alpha_de',
                            'state': 'online'
                        },
                        {
                            'name': 'bravo_de',
                            'state': 'online'
                        }
                    ],
                },
                {
                    'structure_id': 1002,
                    'services':
                    [
                        {
                            'name': 'bravo_de',
                            'state': 'offline'
                        }
                    ],
                }
            ]
        }

    def test_collect_services_with_localizations(self):        
        structures_services = \
            Owner._collect_services_with_localizations(
                self.structures_w_lang, self.default_lang
            )
        expected = {
            1001: {
                'de': ['alpha_de', 'bravo_de'], 
                'ko': ['alpha_ko', 'bravo_ko']
            },
            1002: {
                'de': ['bravo_de'], 
                'ko': ['bravo_ko']
            }
        }
        self.maxDiff = None
        self.assertEqual(to_json(structures_services), to_json(expected))

    def test_condense_services_localizations_into_structures(self):
        structures_services = {
            1001: {
                'de': ['alpha_de', 'bravo_de'], 
                'ko': ['alpha_ko', 'bravo_ko']
            },
            1002: {
                'de': ['bravo_de'], 
                'ko': ['bravo_ko']
            }
        }
        structures = Owner._condense_services_localizations_into_structures(
            self.structures_w_lang, self.default_lang, structures_services
        )
        excepted = [
            {
                'structure_id': 1001,
                'services':
                [                    
                    {
                        'name': 'alpha',
                        'name_de': 'alpha_de',
                        'name_ko': 'alpha_ko',
                        'state': 'online'
                    },
                    {
                        'name': 'bravo',
                        'name_de': 'bravo_de',
                        'name_ko': 'bravo_ko',
                        'state': 'online'
                    }
                ]
            },
            {
                'structure_id': 1002,
                'services':
                [
                    {
                        'name': 'bravo',
                        'name_de': 'bravo_de',
                        'name_ko': 'bravo_ko',
                        'state': 'offline'
                    }
                ]
            }               
        ]    
        self.maxDiff = None
        self.assertEqual(to_json(structures), to_json(excepted))

    def test_condense_services_localizations_into_structures_2(self):
        structures_services = {
            1001: {
                'de': ['alpha_de', 'bravo_de']
            },
            1002: {
                'de': ['bravo_de']
            }
        }
        structures = Owner._condense_services_localizations_into_structures(
            self.structures_w_lang, self.default_lang, structures_services
        )
        excepted = [
            {
                'structure_id': 1001,
                'services':
                [                    
                    {
                        'name': 'alpha',
                        'name_de': 'alpha_de',                        
                        'state': 'online'
                    },
                    {
                        'name': 'bravo',
                        'name_de': 'bravo_de',                        
                        'state': 'online'
                    }
                ]
            },
            {
                'structure_id': 1002,
                'services':
                [
                    {
                        'name': 'bravo',
                        'name_de': 'bravo_de',                        
                        'state': 'offline'
                    }
                ]
            }               
        ]    
        self.maxDiff = None
        self.assertEqual(to_json(structures), to_json(excepted))


class TestFetchNotificationsEsi(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
       
    def test_report_error_when_run_without_char(self):        
        my_owner = Owner.objects.get(corporation__corporation_id=2002)
        self.assertFalse(my_owner.fetch_notifications_esi())
        my_owner.refresh_from_db()
        self.assertEqual(
            my_owner.notifications_last_error, Owner.ERROR_NO_CHARACTER
        )
        
    @patch(MODULE_PATH + '.Token')    
    def test_report_error_when_run_with_expired_token(self, mock_Token):
        mock_Token.objects.filter.side_effect = TokenExpiredError()        
                        
        # create test data
        AuthUtils.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
                
        # run update task
        self.assertFalse(self.owner.fetch_notifications_esi())

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, Owner.ERROR_TOKEN_EXPIRED
        )
    
    # test invalid token    
    @patch(MODULE_PATH + '.Token')
    def test_report_error_when_run_with_invalid_token(self, mock_Token):
        mock_Token.objects.filter.side_effect = TokenInvalidError()
         
        # create test data
        AuthUtils.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
                
        # run update task
        self.assertFalse(self.owner.fetch_notifications_esi())

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, Owner.ERROR_TOKEN_INVALID
        )
        
    # normal synch of new structures, mode my_alliance                    
    @patch(
        'structures.models.notifications.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED', 
        False
    )
    @patch(MODULE_PATH + '.STRUCTURES_ADD_TIMERS', True)    
    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_can_fetch_notifications_correctly(
        self, mock_esi_client_factory, mock_Token, mock_notify
    ):
        mock_esi_client_factory.return_value = esi_mock_client()

        # create test data
        Timer.objects.all().delete()
        AuthUtils.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
                
        # run update task
        self.assertTrue(
            self.owner.fetch_notifications_esi(user=self.user)
        )
        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, Owner.ERROR_NONE
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
        self.assertTrue(self.owner.fetch_notifications_esi())

        # should not have more timers
        self.assertEqual(Timer.objects.count(), 5)
        
    @patch(MODULE_PATH + '.STRUCTURES_ADD_TIMERS', False)        
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    def test_report_error_when_esi_returns_error_during_sync(
        self, mock_esi_client_factory, mock_Token
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
        AuthUtils.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
                
        # run update task
        self.assertFalse(self.owner.fetch_notifications_esi())

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, Owner.ERROR_UNKNOWN
        )


class TestSendNewNotifications(NoSocketsTestCase):    

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.owner.is_alliance_main = True
        cls.owner.save()
        load_notification_entities(cls.owner)

        my_webhook = Webhook.objects.create(
            name='Dummy',
            url='dummy-url',            
            is_active=True
        )
        cls.owner.webhooks.add(my_webhook)

    @staticmethod
    def my_send_to_webhook_success(self, webhook):
        """simulates successful sending of a notification"""
        self.is_sent = True
        self.save()
        return True

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(
        'structures.models.notifications.Notification.send_to_webhook', autospec=True
    )
    def test_can_send_all_notifications(
        self, mock_send_to_webhook, mock_esi_client_factory, mock_token
    ):
        mock_send_to_webhook.side_effect = self.my_send_to_webhook_success
        AuthUtils.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )        
        self.assertTrue(self.owner.send_new_notifications(rate_limited=False))

        notification_ids = set()
        for x in mock_send_to_webhook.call_args_list:
            first = x[0]
            notification = first[0]
            notification_ids.add(notification.notification_id)
        
        expected = {
            x.notification_id 
            for x in Notification.objects.filter(owner=self.owner)
        }
        self.assertSetEqual(notification_ids, expected)

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(
        'structures.models.notifications.Notification.send_to_webhook', 
        autospec=True
    )
    def test_can_send_notifications_to_multiple_webhooks_but_same_owner(
        self, mock_send_to_webhook, mock_esi_client_factory, mock_token
    ):               
        mock_send_to_webhook.side_effect = self.my_send_to_webhook_success
        
        AuthUtils.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
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

        # send notifications        
        self.assertTrue(self.owner.send_new_notifications(rate_limited=False))
        results = {            
            wh_mining.pk: set(),
            wh_structures.pk: set()
        }
        for x in mock_send_to_webhook.call_args_list:
            first = x[0]
            notification = first[0]
            hook = first[1]
            results[hook.pk].add(notification.notification_id)

        # notifications for structures webhook
        expected = {
            1000000402,
            1000000502,
            1000000504,
            1000000505,                
            1000000509,
            1000010509
        }
        self.assertSetEqual(results[wh_structures.pk], expected)
        
        # notifications for mining webhook
        expected = {
            1000000402,
            1000000401,
            1000000403,
            1000000404,
            1000000405
        }
        self.assertSetEqual(results[wh_mining.pk], expected)

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(
        'structures.models.notifications.Notification.send_to_webhook', 
        autospec=True
    )
    def test_can_send_notifications_to_multiple_owners(
        self, mock_send_to_webhook, mock_esi_client_factory, mock_token
    ):        
        mock_send_to_webhook.side_effect = self.my_send_to_webhook_success
        AuthUtils.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
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
        self.assertTrue(self.owner.send_new_notifications(rate_limited=False))
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
    
    @patch(MODULE_PATH + '.Owner._send_notifications_to_webhook', autospec=True)
    def test_reports_unexpected_error(self, mock_send):
        mock_send.side_effect = RuntimeError()
        self.assertFalse(self.owner.send_new_notifications(rate_limited=False))
        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.forwarding_last_error, 
            Owner.ERROR_UNKNOWN
        )
