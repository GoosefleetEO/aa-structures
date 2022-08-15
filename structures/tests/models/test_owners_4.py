from unittest.mock import patch

from app_utils.testing import NoSocketsTestCase

from ...models import NotificationType
from ..testdata.factories_2 import NotificationFactory, OwnerFactory
from ..testdata.helpers import load_eveuniverse

OWNERS_PATH = "structures.models.owners"


@patch(OWNERS_PATH + ".Notification.add_or_remove_timer_from_notification", spec=True)
class TestOwnerAddOrRemoveTimersFromNotifications(NoSocketsTestCase):
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
        owner.add_or_remove_timers_from_notifications()
        # then
        self.assertEqual(mock_add_or_remove_timer_from_notification.call_count, 1)
