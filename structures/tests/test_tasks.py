from unittest.mock import Mock, patch

from celery import Celery

from django.contrib.auth.models import User
from allianceauth.eveonline.models import EveCorporationInfo

from .auth_utils_2 import AuthUtils2
from ..utils import set_test_logger, NoSocketsTestCase
from .. import tasks
from ..models import (
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
from .testdata import (    
    load_entities,
    load_notification_entities,
    get_all_notification_ids,
    create_structures,
    set_owner_character,
    esi_mock_client
)


MODULE_PATH = 'structures.tasks'
MODULE_PATH_MODELS_OWNERS = 'structures.models.owners'
logger = set_test_logger(MODULE_PATH, __file__)
app = Celery('myauth')


def _get_invalid_owner_pk():
    owner_pks = [x.pk for x in Owner.objects.all()]
    return (max(owner_pks) + 1) if owner_pks else 99


def _get_invalid_user_pk():
    pks = [x.pk for x in User.objects.all()]
    return (max(pks) + 1) if pks else 99


class TestUpdateStructures(NoSocketsTestCase):
    
    def setUp(self):
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
    
    @patch(MODULE_PATH + '.Owner.update_structures_esi')
    def test_call_structure_update_with_owner_and_user(
        self, mock_update_structures_esi
    ):        
        tasks.update_structures_for_owner(self.owner.pk, self.user.pk)
        first, second = mock_update_structures_esi.call_args
        self.assertEqual(first[0], self.user)

    @patch(MODULE_PATH + '.Owner.update_structures_esi')
    def test_call_structure_update_with_owner_and_ignores_invalid_user(
        self, mock_update_structures_esi
    ):        
        tasks.update_structures_for_owner(self.owner.pk, _get_invalid_user_pk())
        first, second = mock_update_structures_esi.call_args
        self.assertIsNone(first[0])
        
    def test_raises_exception_if_owner_is_unknown(self):
        with self.assertRaises(Owner.DoesNotExist):
            tasks.update_structures_for_owner(owner_pk=_get_invalid_owner_pk())

    @patch(MODULE_PATH + '.update_structures_for_owner')
    def test_can_update_structures_for_all_owners(
        self, mock_update_structures_for_owner
    ):
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
    
    @patch(MODULE_PATH + '.update_structures_for_owner')
    def test_does_not_update_structures_for_non_active_owners(
        self, mock_update_structures_for_owner
    ):        
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001),
            is_active=True
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            is_active=False
        )
        tasks.update_all_structures()
        self.assertEqual(mock_update_structures_for_owner.delay.call_count, 1)
        call_args_list = mock_update_structures_for_owner.delay.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)        


class TestSyncNotifications(NoSocketsTestCase):

    def setUp(self): 
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)

    def test_raises_exception_if_owner_is_unknown(self):
        with self.assertRaises(Owner.DoesNotExist):
            tasks.fetch_notifications_for_owner(
                owner_pk=_get_invalid_owner_pk()
            )

    @patch(MODULE_PATH_MODELS_OWNERS + '.STRUCTURES_ADD_TIMERS', False)
    @patch(MODULE_PATH + '.fetch_notifications_for_owner')
    def test_fetch_all_notifications(self, mock_fetch_notifications_owner):
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        owner_2002 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002)
        )
        tasks.fetch_all_notifications()
        self.assertEqual(
            mock_fetch_notifications_owner.delay.call_count, 2
        )
        call_args_list = mock_fetch_notifications_owner.delay.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)
        args, kwargs = call_args_list[1]
        self.assertEqual(args[0], owner_2002.pk)

    @patch(MODULE_PATH_MODELS_OWNERS + '.STRUCTURES_ADD_TIMERS', False)
    @patch(MODULE_PATH + '.fetch_notifications_for_owner')
    def test_fetch_all_notifications_not_active(
        self, 
        mock_fetch_notifications_owner
    ):
        """test that not active owners are not synced"""
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001),
            is_active=True
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            is_active=False
        )
        tasks.fetch_all_notifications()
        self.assertEqual(mock_fetch_notifications_owner.delay.call_count, 1)
        call_args_list = mock_fetch_notifications_owner.delay.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)     


class TestForwardNotifications(NoSocketsTestCase):

    def setUp(self):         
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        self.owner.is_alliance_main = True
        self.owner.save()
        load_notification_entities(self.owner)

    def test_raises_exception_if_owner_is_unknown(self):      
        with self.assertRaises(Owner.DoesNotExist):
            tasks.send_new_notifications_for_owner(
                owner_pk=_get_invalid_owner_pk()
            )

    @patch(MODULE_PATH_MODELS_OWNERS + '.Token', autospec=True)
    @patch(MODULE_PATH_MODELS_OWNERS + '.esi_client_factory', autospec=True)
    @patch(
        'structures.models.notifications.dhooks_lite.Webhook.execute',
        autospec=True
    )
    def test_send_new_notifications_no_structures_preloaded(
        self, mock_execute, mock_esi_client_factory, mock_token
    ):        
        logger.debug('test_send_new_notifications_no_structures_preloaded')
        mock_esi_client_factory.return_value = esi_mock_client()
        
        # remove structures from setup so we can start from scratch
        Structure.objects.all().delete()
        
        # user needs permission to run tasks
        AuthUtils2.add_permission_to_user_by_name(
            'structures.add_structure_owner', self.user
        )
        
        tasks.send_all_new_notifications(rate_limited=False)
        
        # should have sent all notifications
        self.assertEqual(
            mock_execute.call_count, len(get_all_notification_ids())
        )

        # should have created structures on the fly        
        structure_ids = {
            x['id'] for x in Structure.objects.values('id')
        }
        self.assertSetEqual(structure_ids, {1000000000002, 1000000000001})
        
    @patch(
        'structures.models.notifications.dhooks_lite.Webhook.execute',
        autospec=True
    )
    def test_send_notifications(self, mock_execute):
        logger.debug('test_send_notifications')
        ids = {1000000401, 1000000402, 1000000403}
        notification_pks = [
            x.pk for x in Notification.objects.filter(notification_id__in=ids)
        ]        
        tasks.send_notifications(notification_pks)

        # should have sent notification
        self.assertEqual(mock_execute.call_count, 3)
        
    @patch(MODULE_PATH + '.send_new_notifications_for_owner')
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

    @patch(MODULE_PATH + '.send_new_notifications_for_owner')
    def test_send_all_new_notifications_not_active(
        self, mock_send_new_notifications_for_owner
    ):
        """no notifications are sent for non active owners"""
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001),
            is_active=True
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            is_active=False
        )
        tasks.send_all_new_notifications()
        self.assertEqual(mock_send_new_notifications_for_owner.call_count, 1)
        call_args_list = mock_send_new_notifications_for_owner.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)


class TestAdminTasks(NoSocketsTestCase):

    @patch('structures.helpers.provider')
    def test_run_sde_update(self, mock_provider):        
        mock_provider.client = esi_mock_client()
        load_entities()
        
        eve_category = EveCategory.objects.get(id=65)
        eve_category.name = 'Superheros'
        eve_category.save()

        eve_group = EveGroup.objects.get(id=1657)
        eve_group.name = 'Fantastic Four'
        eve_group.save()

        eve_type = EveType.objects.get(id=35832)
        eve_type.name = 'Batcave'
        eve_type.save()

        eve_region = EveRegion.objects.get(id=10000005)
        eve_region.name = 'Toscana'
        eve_region.save()

        eve_constellation = EveConstellation.objects.get(id=20000069)
        eve_constellation.name = 'Dark'
        eve_constellation.save()

        eve_moon = EveMoon.objects.get(id=40161465)
        eve_moon.name = 'Alpha II - Moon 1'
        eve_moon.save()
        
        eve_planet = EvePlanet.objects.get(id=40029526)
        eve_planet.name = 'Alpha I'
        eve_planet.save()
        
        eve_solar_system = EveSolarSystem.objects.get(id=30000474)
        eve_solar_system.name = 'Alpha'
        eve_solar_system.save()
         
        app.conf.task_always_eager = True
        tasks.run_sde_update()
        app.conf.task_always_eager = False

        eve_category.refresh_from_db()
        self.assertEqual(eve_category.name, 'Structure')

        eve_group.refresh_from_db()
        self.assertEqual(eve_group.name, 'Citadel')

        eve_type.refresh_from_db()
        self.assertEqual(eve_type.name, 'Astrahus')

        eve_region.refresh_from_db()
        self.assertEqual(eve_region.name, 'Detorid')

        eve_constellation.refresh_from_db()
        self.assertEqual(eve_constellation.name, '1RG-GU')

        eve_moon.refresh_from_db()
        self.assertEqual(eve_moon.name, 'Amamake II - Moon 1')

        eve_planet.refresh_from_db()
        self.assertEqual(eve_planet.name, '1-PGSG I')

        eve_solar_system.refresh_from_db()
        self.assertEqual(eve_solar_system.name, '1-PGSG')

    def test_purge_all_data(self):
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        self.owner.is_alliance_main = True
        self.owner.save()
        load_notification_entities(self.owner)
        models = [
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
        ]
        for MyModel in models:            
            self.assertGreater(MyModel.objects.count(), 0)

        tasks.purge_all_data(i_am_sure=True)

        for MyModel in models:
            self.assertEqual(MyModel.objects.count(), 0)


class TestSendTestNotification(NoSocketsTestCase):

    def setUp(self):         
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        self.owner.is_alliance_main = True
        self.owner.save()
        load_notification_entities(self.owner)

    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(
        'structures.models.notifications.dhooks_lite.Webhook.execute',
        autospec=True
    )
    def test_send_test_notification(self, mock_execute, mock_notify):
        logger.debug('test_send_test_notification')
        mock_response = Mock()
        mock_response.status_ok = True
        mock_response.content = {"dummy_response": True}
        mock_execute.return_value = mock_response
        my_webhook = self.owner.webhooks.first()
        tasks.send_test_notifications_to_webhook(my_webhook.pk, self.user.pk)
        
        # should have sent notification
        self.assertEqual(mock_execute.call_count, 1)

        # should have sent user report
        self.assertTrue(mock_notify.called)
        args = mock_notify.call_args[1]
        self.assertEqual(args['level'], 'success')

    @patch(MODULE_PATH + '.notify', autospec=True)
    @patch(MODULE_PATH + '.Webhook.send_test_notification')
    def test_send_test_notification_error(
        self, mock_send_test_notification, mock_notify
    ):
        mock_send_test_notification.side_effect = RuntimeError
        my_webhook = self.owner.webhooks.first()        
        tasks.send_test_notifications_to_webhook(my_webhook.pk, self.user.pk)

        # should have sent user report
        self.assertTrue(mock_notify.called)
        args = mock_notify.call_args[1]
        self.assertEqual(args['level'], 'danger')
