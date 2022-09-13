from unittest.mock import patch

from app_utils.testing import NoSocketsTestCase

from ..models import GeneratedNotification, Notification, NotificationType
from .testdata.factories_2 import (
    GeneratedNotificationFactory,
    NotificationFactory,
    OwnerFactory,
)
from .testdata.load_eveuniverse import load_eveuniverse

MANAGERS_PATH = "structures.managers"


@patch(
    "structures.models.notifications.NotificationBase.add_or_remove_timer",
    spec=True,
)
class TestNotificationBaseAddOrRemoveTimers(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_create_new_timers_from_notifications(
        self, mock_add_or_remove_timer_from_notification
    ):
        # given
        owner = OwnerFactory()
        NotificationFactory(
            owner=owner, notif_type=NotificationType.STRUCTURE_LOST_SHIELD
        )
        NotificationFactory(
            owner=owner, notif_type=NotificationType.WAR_CORPORATION_BECAME_ELIGIBLE
        )
        # when
        Notification.objects.add_or_remove_timers()
        # then
        self.assertEqual(mock_add_or_remove_timer_from_notification.call_count, 1)

    def test_should_create_new_timers_from_generated_notifications(
        self, mock_add_or_remove_timer_from_notification
    ):
        # given
        GeneratedNotificationFactory()
        # when
        GeneratedNotification.objects.add_or_remove_timers()
        # then
        self.assertEqual(mock_add_or_remove_timer_from_notification.call_count, 1)
