from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.contrib import admin
from django.contrib.admin.sites import AdminSite

from allianceauth.eveonline.models import EveCorporationInfo

from . import set_logger
from ..admin import (
    NotificationAdmin, 
    OwnerAdmin, 
    StructureAdmin, 
    WebhookAdmin, 
    OwnerSyncStatusFilter,
    OwnerCorporationsFilter,
    OwnerAllianceFilter
)
from ..models import (
    Webhook, Notification, Owner, Structure, StructureTag
)
from .testdata import (
    create_structures, 
    create_user,    
    load_entities,
    load_notification_entities,    
    set_owner_character, 
)


MODULE_PATH = 'structures.admin'
logger = set_logger(MODULE_PATH, __file__)


class MockRequest(object):
    
    def __init__(self, user=None):
        self.user = user


class TestNotificationAdmin(TestCase):

    def setUp(self):
        self.modeladmin = NotificationAdmin(
            model=Notification, admin_site=AdminSite()
        )
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        load_notification_entities(self.owner)
        self.obj = Notification.objects.get(notification_id=1000000404)
        self.obj_qs = Notification.objects.filter(
            notification_id__in=[1000000404, 1000000405]
        )

    def test_webhooks(self):
        self.owner.webhooks.add(Webhook.objects.get(name='Test Webhook 2'))
        self.assertEqual(
            self.modeladmin._webhooks(self.obj),
            'Test Webhook 1, Test Webhook 2'
        )

    @patch(MODULE_PATH + '.NotificationAdmin.message_user', auto_spec=True)    
    def test_action_mark_as_sent(self, mock_message_user):
        for obj in self.obj_qs:
            obj.is_sent = False
            obj.save()
        self.modeladmin.mark_as_sent(MockRequest(self.user), self.obj_qs)
        for obj in self.obj_qs:
            self.assertTrue(obj.is_sent)        
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + '.NotificationAdmin.message_user', auto_spec=True)    
    def test_action_mark_as_unsent(self, mock_message_user):
        for obj in self.obj_qs:
            obj.is_sent = True
            obj.save()
        self.modeladmin.mark_as_unsent(MockRequest(self.user), self.obj_qs)
        for obj in self.obj_qs:
            self.assertFalse(obj.is_sent)        
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + '.NotificationAdmin.message_user', auto_spec=True)
    @patch(MODULE_PATH + '.tasks.send_notifications')    
    def test_action_send_to_webhook(self, mock_task, mock_message_user):
        self.modeladmin.send_to_webhook(
            MockRequest(self.user), self.obj_qs
        )
        self.assertEqual(mock_task.delay.call_count, 1)
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + '.NotificationAdmin.message_user', auto_spec=True)
    @patch(MODULE_PATH + '.Notification.process_for_timerboard')    
    def test_action_process_for_timerboard(
        self, mock_process_for_timerboard, mock_message_user
    ):
        self.modeladmin.process_for_timerboard(
            MockRequest(self.user), self.obj_qs
        )
        self.assertEqual(mock_process_for_timerboard.call_count, 2)
        self.assertTrue(mock_message_user.called)


class TestOwnerAdmin(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.modeladmin = OwnerAdmin(
            model=Owner, admin_site=AdminSite()
        )
        create_structures()
        self.user, self.obj = set_owner_character(character_id=1001)        

    def test_corporation(self):
        self.assertEqual(
            self.modeladmin._corporation(self.obj), 'Wayne Technologies'
        )
    
    def test_alliance_normal(self):
        self.assertEqual(
            self.modeladmin._alliance(self.obj), 'Wayne Enterprises'
        )

    def test_alliance_none(self):
        my_owner = Owner.objects.get(corporation__corporation_id=2102)
        self.assertIsNone(self.modeladmin._alliance(my_owner))

    def test_webhooks(self):
        self.obj.webhooks.add(Webhook.objects.get(name='Test Webhook 2'))
        self.assertEqual(
            self.modeladmin._webhooks(self.obj),
            'Test Webhook 1, Test Webhook 2'
        )

    @patch(MODULE_PATH + '.OwnerAdmin.message_user', auto_spec=True)
    @patch(MODULE_PATH + '.tasks.update_structures_for_owner')
    def test_action_update_structures(self, mock_task, mock_message_user):
        owner_qs = Owner.objects\
            .filter(corporation__corporation_id__in=[2001, 2002])
        self.modeladmin.update_structures(
            MockRequest(self.user), owner_qs
        )
        self.assertEqual(mock_task.delay.call_count, 2)
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + '.OwnerAdmin.message_user', auto_spec=True)
    @patch(MODULE_PATH + '.tasks.fetch_notifications_for_owner')
    def test_action_fetch_notifications(self, mock_task, mock_message_user):
        owner_qs = Owner.objects\
            .filter(corporation__corporation_id__in=[2001, 2002])
        self.modeladmin.fetch_notifications(
            MockRequest(self.user), owner_qs
        )
        self.assertEqual(
            mock_task.delay.call_count, 2
        )
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + '.OwnerAdmin.message_user', auto_spec=True)
    @patch(MODULE_PATH + '.tasks.send_new_notifications_for_owner')
    def test_action_send_notifications(self, mock_task, mock_message_user):
        owner_qs = Owner.objects\
            .filter(corporation__corporation_id__in=[2001, 2002])
        self.modeladmin.send_notifications(
            MockRequest(self.user), owner_qs
        )
        self.assertEqual(mock_task.delay.call_count, 2)
        self.assertTrue(mock_message_user.called)

    def test_owner_sync_status_filter(self):
        
        class OwnerAdminTest(admin.ModelAdmin): 
            list_filter = (OwnerSyncStatusFilter,)
                
        owner_2001 = Owner.objects.get(corporation__corporation_id=2001)
        owner_2001.structures_last_error = Owner.ERROR_TOKEN_EXPIRED
        owner_2001.save()

        owner_2002 = Owner.objects.get(corporation__corporation_id=2002)
        owner_2002.notifications_last_error = Owner.ERROR_TOKEN_EXPIRED
        owner_2002.save()

        owner_2102 = Owner.objects.get(corporation__corporation_id=2102)
        owner_2102.forwarding_last_error = Owner.ERROR_TOKEN_EXPIRED
        owner_2102.save()
        
        modeladmin = OwnerAdminTest(Owner, AdminSite())
        # Make sure the lookups are correct
        request = self.factory.get('/')
        request.user = self.user
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [('yes', 'Yes'), ('no', 'No')]
        self.assertEqual(filterspec.lookup_choices, expected)

        # Make sure the correct queryset is returned - 1
        request = self.factory.get('/', {'sync_status__exact': 'yes'})
        request.user = self.user                
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        expected = Owner.objects\
            .exclude(corporation__corporation_id__in=[2001, 2002, 2102])
        self.assertSetEqual(set(queryset), set(expected))

        # Make sure the correct queryset is returned - 2
        request = self.factory.get('/', {'sync_status__exact': 'no'})
        request.user = self.user                
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        expected = Owner.objects\
            .filter(corporation__corporation_id__in=[2001, 2002, 2102])
        self.assertSetEqual(set(queryset), set(expected))


class TestStructureAdmin(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.modeladmin = StructureAdmin(
            model=Structure, admin_site=AdminSite()
        )
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        self.obj = Structure.objects.get(id=1000000000001)
        self.obj_qs = Structure.objects\
            .filter(id__in=[1000000000001, 1000000000002])

    def test_owner(self):
        self.assertEqual(
            self.modeladmin._owner(self.obj),
            'Wayne Technologies<br>Wayne Enterprises'
        )

    def test_location(self):
        self.assertEqual(
            self.modeladmin._location(self.obj),
            'Amamake<br>Heimatar'
        )
        poco = Structure.objects.get(id=1200000000003)
        self.assertEqual(
            self.modeladmin._location(poco),
            'Amamake V<br>Heimatar'
        )
        starbase = Structure.objects.get(id=1300000000001)
        self.assertEqual(
            self.modeladmin._location(starbase),
            'Amamake II - Moon 1<br>Heimatar'
        )

    def test_type(self):
        self.assertEqual(
            self.modeladmin._type(self.obj),
            'Astrahus<br>Citadel'
        )

    def test_tags_1(self):
        self.assertListEqual(self.modeladmin._tags(self.obj), ['tag_a'])

    def test_tags_2(self):
        self.obj.tags.clear()
        self.assertIsNone(self.modeladmin._tags(self.obj))

    @patch(MODULE_PATH + '.StructureAdmin.message_user', auto_spec=True)    
    def test_action_add_default_tags(self, mock_message_user):        
        for obj in self.obj_qs:
            obj.tags.clear()
        self.modeladmin.add_default_tags(
            MockRequest(self.user), self.obj_qs
        )
        default_tags = StructureTag.objects.filter(is_default=True)
        for obj in self.obj_qs:
            self.assertSetEqual(set(obj.tags.all()), set(default_tags))
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + '.StructureAdmin.message_user', auto_spec=True)    
    def test_action_remove_all_tags(self, mock_message_user):               
        self.modeladmin.remove_all_tags(
            MockRequest(self.user), self.obj_qs
        )
        for obj in self.obj_qs:
            self.assertIsNone(obj.tags.first())
        self.assertTrue(mock_message_user.called)

    def test_owner_corporations_status_filter(self):
        
        class StructureAdminTest(admin.ModelAdmin): 
            list_filter = (OwnerCorporationsFilter,)
        
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002)
        )        
        my_modeladmin = StructureAdminTest(Structure, AdminSite())

        # Make sure the lookups are correct
        request = self.factory.get('/')
        request.user = self.user                
        changelist = my_modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [('2002', 'Wayne Foods'), ('2001', 'Wayne Technologies')]
        self.assertEqual(filterspec.lookup_choices, expected)

        # Make sure the correct queryset is returned
        request = self.factory.get('/', {'owner_corporation_id__exact': 2001})
        request.user = self.user                
        changelist = my_modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        expected = Structure.objects.filter(owner=owner_2001)
        self.assertSetEqual(set(queryset), set(expected))

    def test_owner_alliance_status_filter(self):
        
        class StructureAdminTest(admin.ModelAdmin): 
            list_filter = (OwnerAllianceFilter,)
                
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        owner_2002 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002)
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2102)
        )        
        modeladmin = StructureAdminTest(Structure, AdminSite())
        
        # Make sure the lookups are correct
        request = self.factory.get('/')
        request.user = self.user
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [('3001', 'Wayne Enterprises')]
        self.assertEqual(filterspec.lookup_choices, expected)        
        
        # Make sure the correct queryset is returned
        request = self.factory.get('/', {'owner_alliance_id__exact': 3001})
        request.user = self.user                
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        expected = Structure.objects.filter(owner__in=[owner_2001, owner_2002])
        self.assertSetEqual(set(queryset), set(expected))


class TestWebhookAdmin(TestCase):

    def setUp(self):
        self.modeladmin = WebhookAdmin(
            model=Webhook, admin_site=AdminSite()
        )
        load_entities([Webhook])
        self.user = create_user(character_id=1001, load_data=True)
        self.obj_qs = Webhook.objects.all()

    @patch(MODULE_PATH + '.WebhookAdmin.message_user', auto_spec=True)
    @patch(MODULE_PATH + '.tasks.send_test_notifications_to_webhook')    
    def test_action_test_notification(self, mock_task, mock_message_user):
        self.modeladmin.test_notification(
            MockRequest(self.user), self.obj_qs
        )
        self.assertEqual(mock_task.delay.call_count, 2)
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + '.WebhookAdmin.message_user', auto_spec=True)    
    def test_action_activate(self, mock_message_user):
        for obj in self.obj_qs:
            obj.is_active = False
            obj.save()
        self.modeladmin.activate(
            MockRequest(self.user), self.obj_qs
        )
        for obj in self.obj_qs:
            self.assertTrue(obj.is_active)
        
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + '.WebhookAdmin.message_user', auto_spec=True)    
    def test_action_deactivate(self, mock_message_user):
        for obj in self.obj_qs:
            obj.is_active = True
            obj.save()
        self.modeladmin.deactivate(
            MockRequest(self.user), self.obj_qs
        )
        for obj in self.obj_qs:
            self.assertFalse(obj.is_active)
        
        self.assertTrue(mock_message_user.called)
