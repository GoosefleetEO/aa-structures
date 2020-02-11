from unittest.mock import patch, Mock

from django.test import TestCase
from django.contrib.admin.sites import AdminSite

from . import set_logger
from ..admin import NotificationAdmin, OwnerAdmin
from ..models import Webhook, Notification, Owner, Structure
from .testdata import \
    create_structures, set_owner_character, load_notification_entities


MODULE_PATH = 'structures.admin'
logger = set_logger(MODULE_PATH, __file__)


class MockRequest(object):
    
    def __init__(self, user=None):
        self.user = user


class TestNotificationAdmin(TestCase):

    def setUp(self):
        self.my_model_admin = NotificationAdmin(
            model=Notification, admin_site=AdminSite()
        )
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        load_notification_entities(self.owner)        
        self.my_notification = Notification.objects\
            .get(notification_id=1000000404)

    def test_webhook_list(self):
        self.owner.webhooks.add(Webhook.objects.get(name='Test Webhook 2'))
        self.assertEqual(
            self.my_model_admin._webhooks(self.my_notification),
            'Test Webhook 1, Test Webhook 2'
        )


class TestOwnerAdmin(TestCase):

    def setUp(self):
        self.my_model_admin = OwnerAdmin(
            model=Owner, admin_site=AdminSite()
        )
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)        

    def test_alliance_normal(self):
        self.assertEqual(
            self.my_model_admin.alliance(self.owner), 'Wayne Enterprises'
        )

    def test_alliance_none(self):
        my_owner = Owner.objects.get(corporation__corporation_id=2102)
        self.assertIsNone(self.my_model_admin.alliance(my_owner))

    @patch(MODULE_PATH + '.OwnerAdmin.message_user', auto_spec=True)
    @patch(MODULE_PATH + '.tasks.update_structures_for_owner')
    def test_update_structures(
        self, mock_update_structures_for_owner, mock_message_user
    ):
        owner_qs = Owner.objects\
            .filter(corporation__corporation_id__in=[2001, 2002])
        self.my_model_admin.update_structures(
            MockRequest(self.user), owner_qs
        )
        self.assertEqual(
            mock_update_structures_for_owner.delay.call_count, 2
        )
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + '.OwnerAdmin.message_user', auto_spec=True)
    @patch(MODULE_PATH + '.tasks.fetch_notifications_for_owner')
    def test_fetch_notifications(
        self, mock_fetch_notifications_for_owner, mock_message_user
    ):
        owner_qs = Owner.objects\
            .filter(corporation__corporation_id__in=[2001, 2002])
        self.my_model_admin.fetch_notifications(
            MockRequest(self.user), owner_qs
        )
        self.assertEqual(
            mock_fetch_notifications_for_owner.delay.call_count, 2
        )
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + '.OwnerAdmin.message_user', auto_spec=True)
    @patch(MODULE_PATH + '.tasks.send_new_notifications_for_owner')
    def test_send_notifications(
        self, mock_send_new_notifications_for_owner, mock_message_user
    ):
        owner_qs = Owner.objects\
            .filter(corporation__corporation_id__in=[2001, 2002])
        self.my_model_admin.send_notifications(
            MockRequest(self.user), owner_qs
        )
        self.assertEqual(
            mock_send_new_notifications_for_owner.delay.call_count, 2
        )
        self.assertTrue(mock_message_user.called)
