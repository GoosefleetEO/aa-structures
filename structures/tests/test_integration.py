import datetime as dt
from unittest.mock import patch

from django.test import override_settings
from django.utils.timezone import now

from app_utils.testing import NoSocketsTestCase

from .. import tasks
from ..models import FuelAlert, FuelAlertConfig, Structure, Webhook
from .testdata import create_structures, load_notification_entities, set_owner_character

TASKS_PATH = "structures.tasks"
OWNERS_PATH = "structures.models.owners"
NOTIFICATIONS_PATH = "structures.models.notifications"


@override_settings(CELERY_ALWAYS_EAGER=True)
class TestFuelNotification(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)
        cls.webhook = Webhook.objects.get(name="Test Webhook 1")
        Structure.objects.update(fuel_expires_at=None)

    @patch(NOTIFICATIONS_PATH + ".Webhook.send_message", spec=True)
    def test_should_send_fuel_notification_for_structure(self, mock_send_message):
        # given
        FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        structure.state = Structure.State.ARMOR_REINFORCE
        structure.state_timer_start = now() - dt.timedelta(days=1)
        structure.state_timer_end = now() + dt.timedelta(days=2)
        structure.fuel_expires_at = now() + dt.timedelta(hours=25)
        structure.save()
        mock_send_message.reset_mock()
        # when
        with patch(TASKS_PATH + ".process_notifications_for_owner"):
            tasks.fetch_all_notifications()
        # then
        self.assertTrue(mock_send_message.called)
        obj = FuelAlert.objects.first()
        self.assertEqual(obj.hours, 36)
