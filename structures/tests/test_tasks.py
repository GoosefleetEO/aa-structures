from unittest.mock import patch

from celery import Celery

from django.contrib.auth.models import User
from django.test import TestCase

from allianceauth.eveonline.models import EveCorporationInfo
from structures.models.notifications import Notification

from app_utils.testing import NoSocketsTestCase, generate_invalid_pk
from .. import tasks
from ..models import Owner, Webhook
from .testdata import (
    load_notification_entities,
    create_structures,
    set_owner_character,
)


MODULE_PATH = "structures.tasks"
MODULE_PATH_MODELS_OWNERS = "structures.models.owners"

app = Celery("myauth")


@patch(MODULE_PATH + ".Webhook.send_queued_messages", spec=True)
class TestSendMessagesForWebhook(TestCase):
    def setUp(self) -> None:
        self.webhook = Webhook.objects.create(
            name="Dummy", url="https://www.example.com/webhook"
        )

    def test_normal(self, mock_send_queued_messages):
        tasks.send_messages_for_webhook(self.webhook.pk)
        self.assertEqual(mock_send_queued_messages.call_count, 1)

    def test_invalid_pk(self, mock_send_queued_messages):
        tasks.send_messages_for_webhook(generate_invalid_pk(Webhook))
        self.assertEqual(mock_send_queued_messages.call_count, 0)

    def test_disabled_webhook(self, mock_send_queued_messages):
        self.webhook.is_active = False
        self.webhook.save()

        tasks.send_messages_for_webhook(self.webhook.pk)
        self.assertEqual(mock_send_queued_messages.call_count, 0)


class TestUpdateStructures(NoSocketsTestCase):
    def setUp(self):
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)

    @patch(MODULE_PATH + ".Owner.update_structures_esi")
    def test_call_structure_update_with_owner_and_user(
        self, mock_update_structures_esi
    ):
        tasks.update_structures_for_owner(self.owner.pk, self.user.pk)
        first, second = mock_update_structures_esi.call_args
        self.assertEqual(first[0], self.user)

    @patch(MODULE_PATH + ".Owner.update_structures_esi")
    def test_call_structure_update_with_owner_and_ignores_invalid_user(
        self, mock_update_structures_esi
    ):
        tasks.update_structures_for_owner(self.owner.pk, generate_invalid_pk(User))
        first, second = mock_update_structures_esi.call_args
        self.assertIsNone(first[0])

    def test_raises_exception_if_owner_is_unknown(self):
        with self.assertRaises(Owner.DoesNotExist):
            tasks.update_structures_for_owner(owner_pk=generate_invalid_pk(Owner))

    @patch(MODULE_PATH + ".update_structures_for_owner")
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
        tasks.update_structures()
        self.assertEqual(mock_update_structures_for_owner.delay.call_count, 2)
        call_args_list = mock_update_structures_for_owner.delay.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)
        args, kwargs = call_args_list[1]
        self.assertEqual(args[0], owner_2002.pk)

    @patch(MODULE_PATH + ".update_structures_for_owner")
    def test_does_not_update_structures_for_non_active_owners(
        self, mock_update_structures_for_owner
    ):
        Owner.objects.filter().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001),
            is_active=True,
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            is_active=False,
        )
        tasks.update_structures()
        self.assertEqual(mock_update_structures_for_owner.delay.call_count, 1)
        call_args_list = mock_update_structures_for_owner.delay.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(args[0], owner_2001.pk)

    """
    TODO: Fix this test
    @patch(MODULE_PATH + ".EveSovereigntyMap.objects.update_from_esi")
    @patch(MODULE_PATH + ".update_structures_for_owner")
    def test_update_all_structures(
        self, mock_update_structures_for_owner, mock_update_from_esi
    ):
        Owner.objects.filter().delete()
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001),
            is_active=True,
        )
        tasks.update_all_structures()

        self.assertTrue(mock_update_structures_for_owner.delay.called)
        self.assertTrue(mock_update_from_esi.called)
    """


class TestFetchAllNotifications(NoSocketsTestCase):
    def setUp(self):
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)

    @patch(MODULE_PATH_MODELS_OWNERS + ".STRUCTURES_ADD_TIMERS", False)
    @patch(MODULE_PATH + ".process_notifications_for_owner")
    def test_fetch_all_notifications(self, mock_fetch_notifications_owner):
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        owner_2002 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002)
        )
        tasks.fetch_all_notifications()
        self.assertEqual(mock_fetch_notifications_owner.apply_async.call_count, 2)
        call_args_list = mock_fetch_notifications_owner.apply_async.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(kwargs["kwargs"]["owner_pk"], owner_2001.pk)
        args, kwargs = call_args_list[1]
        self.assertEqual(kwargs["kwargs"]["owner_pk"], owner_2002.pk)

    @patch(MODULE_PATH_MODELS_OWNERS + ".STRUCTURES_ADD_TIMERS", False)
    @patch(MODULE_PATH + ".process_notifications_for_owner")
    def test_fetch_all_notifications_not_active(self, mock_fetch_notifications_owner):
        """test that not active owners are not synced"""
        Owner.objects.all().delete()
        owner_2001 = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001),
            is_active=True,
        )
        Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002),
            is_active=False,
        )
        tasks.fetch_all_notifications()
        self.assertEqual(mock_fetch_notifications_owner.apply_async.call_count, 1)
        call_args_list = mock_fetch_notifications_owner.apply_async.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(kwargs["kwargs"]["owner_pk"], owner_2001.pk)


class TestProcessNotificationsForOwner(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)

    def test_raises_exception_if_owner_is_unknown(self):
        with self.assertRaises(Owner.DoesNotExist):
            tasks.process_notifications_for_owner(owner_pk=generate_invalid_pk(Owner))

    @patch(MODULE_PATH + ".send_messages_for_webhook")
    @patch(MODULE_PATH + ".Owner.fetch_notifications_esi")
    def test_normal(
        self,
        mock_fetch_notifications_esi,
        mock_send_messages_for_webhook,
    ):
        load_notification_entities(self.owner)
        Notification.objects.exclude(notification_id=1000000509).delete()
        self.owner.webhooks.first().clear_queue()

        tasks.process_notifications_for_owner(owner_pk=self.owner.pk)
        self.assertTrue(mock_fetch_notifications_esi.called)
        self.assertEqual(mock_send_messages_for_webhook.apply_async.call_count, 1)

    @patch(MODULE_PATH + ".send_messages_for_webhook")
    @patch(MODULE_PATH + ".Owner.fetch_notifications_esi")
    def test_dont_sent_if_queue_is_empty(
        self,
        mock_fetch_notifications_esi,
        mock_send_messages_for_webhook,
    ):
        self.owner.webhooks.first().clear_queue()

        tasks.process_notifications_for_owner(owner_pk=self.owner.pk)
        self.assertTrue(mock_fetch_notifications_esi.called)
        self.assertEqual(mock_send_messages_for_webhook.apply_async.call_count, 0)


@patch("structures.webhooks.core.sleep", lambda _: None)
@patch(MODULE_PATH + ".notify", spec=True)
@patch("structures.models.notifications.Webhook.send_test_message")
class TestSendTestNotification(NoSocketsTestCase):
    def setUp(self):
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        self.owner.is_alliance_main = True
        self.owner.save()
        load_notification_entities(self.owner)

    def test_send_test_notification(self, mock_send_test_message, mock_notify):
        mock_send_test_message.return_value = ("", True)
        my_webhook = self.owner.webhooks.first()
        tasks.send_test_notifications_to_webhook(my_webhook.pk, self.user.pk)

        # should have tried to sent notification
        self.assertEqual(mock_send_test_message.call_count, 1)

        # should have sent user report
        self.assertTrue(mock_notify.called)
        args = mock_notify.call_args[1]
        self.assertEqual(args["level"], "success")

    def test_send_test_notification_error(self, mock_send_test_message, mock_notify):
        mock_send_test_message.return_value = ("Error", False)
        my_webhook = self.owner.webhooks.first()
        tasks.send_test_notifications_to_webhook(my_webhook.pk, self.user.pk)

        # should have tried to sent notification
        self.assertEqual(mock_send_test_message.call_count, 1)

        # should have sent user report
        self.assertTrue(mock_notify.called)
        args = mock_notify.call_args[1]
        self.assertEqual(args["level"], "danger")


class TestSendNotifications(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)

    @patch(MODULE_PATH + ".send_messages_for_webhook")
    def test_normal(self, mock_send_messages_for_webhook):
        load_notification_entities(self.owner)

        notification_pk = Notification.objects.get(notification_id=1000000509).pk
        tasks.send_notifications([notification_pk])
        self.assertEqual(mock_send_messages_for_webhook.apply_async.call_count, 1)
