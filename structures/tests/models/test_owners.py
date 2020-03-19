from datetime import timedelta
from unittest.mock import patch, Mock

from bravado.exception import HTTPBadGateway

from django.utils.timezone import now

from allianceauth.eveonline.models import (
    EveCharacter, EveCorporationInfo, EveAllianceInfo
)
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.timerboard.models import Timer
from allianceauth.tests.auth_utils import AuthUtils

from esi.errors import TokenExpiredError, TokenInvalidError

from ..auth_utils_2 import AuthUtils2
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
    entities_testdata,
    esi_corp_structures_data,
    load_entities,
    load_notification_entities,
    get_all_notification_ids,
    create_structures,
    set_owner_character,
    esi_mock_client
)
from ...utils import set_test_logger, NoSocketsTestCase

MODULE_PATH = 'structures.models.owners'
logger = set_test_logger(MODULE_PATH, __file__)


class TestOwner(NoSocketsTestCase):

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


class TestUpdateStructuresEsi(NoSocketsTestCase):
    
    def setUp(self):        
        # reset data that might be overridden        
        esi_get_corporations_corporation_id_structures.override_data = None
        esi_get_corporations_corporation_id_customs_offices.override_data = \
            None
        
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
        self.character = EveCharacter.objects.get(character_id=1001)
                
        self.corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        self.user = AuthUtils.create_user(self.character.character_name)
        
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

    # test expired token    
    @patch(MODULE_PATH + '.Token')    
    def test_returns_error_when_token_is_expired(self, mock_Token):
        mock_Token.objects.filter.side_effect = TokenExpiredError()
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
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
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )        
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
    
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', True)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_can_sync_all_structures(
        self, mock_esi_client_factory, mock_Token, mock_notify
    ):                                       
        mock_esi_client_factory.return_value = esi_mock_client()

        # create test data
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, Owner.ERROR_NONE            
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
            structure.name, 'Planet (Barren)'
        )
        
        # user report has been sent
        self.assertTrue(mock_notify.called)
    
    """
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_STARBASES', False)
    @patch(MODULE_PATH + '.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory')
    def test_removes_old_structures(
        self, mock_esi_client_factory, mock_Token
    ):                       
        mock_esi_client_factory.return_value = esi_mock_client()

        # create test data
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )        
        
        # run update task with all structures
        owner.update_structures_esi()        
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
        owner.update_structures_esi()
        # should contain only the remaining structure
        self.assertSetEqual(
            {x['id'] for x in Structure.objects.values('id')},
            {1000000000002, 1000000000003}
        )
    """
    """
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

        # create test data
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )        
        
        # run update task with all structures
        owner.update_structures_esi()        
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
        update_structures_esi(
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
    """

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

        # create test data
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
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

        # create test data
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
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

        # create test data
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
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
        my_corp_structures_data = esi_corp_structures_data.copy()
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

        # create test data
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
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
        
        # create test data
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
                
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))

        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, 'Planet (Barren)')

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
        
        # create test data
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
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
        mock_esi_client_factory.return_value = esi_mock_client()
        mock_update_or_create_from_dict.side_effect = RuntimeError

        # create test data
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )        
        
        # run update task with all structures        
        self.assertFalse(owner.update_structures_esi())


class TestFetchNotificationsEsi(NoSocketsTestCase):

    def setUp(self): 
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
       
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
        AuthUtils2.add_permission_to_user_by_name(
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
        AuthUtils2.add_permission_to_user_by_name(
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
        AuthUtils2.add_permission_to_user_by_name(
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
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
                
        # run update task
        self.assertFalse(self.owner.fetch_notifications_esi())

        self.owner.refresh_from_db()
        self.assertEqual(
            self.owner.notifications_last_error, Owner.ERROR_UNKNOWN
        )


class TestSendNewNotifications(NoSocketsTestCase):    

    def setUp(self):         
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        self.owner.is_alliance_main = True
        self.owner.save()
        load_notification_entities(self.owner)

    @patch(MODULE_PATH + '.Token', autospec=True)
    @patch(MODULE_PATH + '.esi_client_factory', autospec=True)
    @patch(
        'structures.models.notifications.Notification.send_to_webhook', 
        autospec=True
    )    
    def test_send_new_notifications_to_multiple_webhooks_2(
        self, mock_send_to_webhook, mock_esi_client_factory, mock_token
    ):
        # create test data
        AuthUtils2.add_permission_to_user_by_name(
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
        self.owner.send_new_notifications(rate_limited=False)
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
