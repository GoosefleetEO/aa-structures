import datetime as dt
from unittest.mock import patch

from django.utils.timezone import now

from app_utils.testing import NoSocketsTestCase

from ... import constants
from ...models import (
    FuelAlert,
    FuelAlertConfig,
    JumpFuelAlert,
    JumpFuelAlertConfig,
    NotificationType,
    Structure,
    Webhook,
)
from ..testdata import (
    create_structures,
    load_notification_entities,
    set_owner_character,
)

MODULE_PATH = "structures.models.notifications"


@patch(MODULE_PATH + ".Webhook.send_message", spec=True)
class TestStructureFuelAlerts(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)
        cls.webhook = Webhook.objects.get(name="Test Webhook 1")
        Structure.objects.update(fuel_expires_at=None)

    def test_should_output_str(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        alert = FuelAlert.objects.create(structure=structure, config=config, hours=36)
        # when
        result = str(alert)
        # then
        self.assertIsInstance(result, str)

    def test_should_send_fuel_notification_for_structure(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=25)
        structure.save()
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertTrue(mock_send_message.called)
        obj = FuelAlert.objects.first()
        self.assertEqual(obj.hours, 36)

    def test_should_not_send_fuel_notification_that_already_exists(
        self, mock_send_message
    ):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=25)
        structure.save()
        mock_send_message.reset_mock()
        FuelAlert.objects.create(structure=structure, config=config, hours=36)
        # when
        config.send_new_notifications()
        # then
        self.assertFalse(mock_send_message.called)
        self.assertEqual(FuelAlert.objects.count(), 1)

    def test_should_send_fuel_notification_for_starbase(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1300000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=25)
        structure.save()
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertTrue(mock_send_message.called)
        obj = FuelAlert.objects.first()
        self.assertEqual(obj.hours, 36)

    def test_should_use_configured_ping_type_for_notifications(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(
            start=48,
            end=0,
            repeat=12,
            channel_ping_type=Webhook.PingType.EVERYONE,
        )
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=25)
        structure.save()
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertTrue(mock_send_message.called)
        _, kwargs = mock_send_message.call_args
        self.assertIn("@everyone", kwargs["content"])

    def test_should_use_configured_level_for_notifications(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(
            start=48,
            end=0,
            repeat=12,
            color=Webhook.Color.SUCCESS,
        )
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=25)
        structure.save()
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertTrue(mock_send_message.called)
        _, kwargs = mock_send_message.call_args
        embed = kwargs["embeds"][0]
        self.assertEqual(embed.color, Webhook.Color.SUCCESS)

    def test_should_send_fuel_notification_at_start(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(start=12, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(
            hours=11, minutes=59, seconds=59
        )
        structure.save()
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertTrue(mock_send_message.called)
        obj = FuelAlert.objects.first()
        self.assertEqual(obj.hours, 12)

    def test_should_not_send_fuel_notifications_before_start(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(start=12, end=6, repeat=1)
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=12, minutes=0, seconds=1)
        structure.save()
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertFalse(mock_send_message.called)

    def test_should_not_send_fuel_notifications_after_end(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(start=12, end=6, repeat=1)
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(
            hours=5, minutes=59, seconds=59
        )
        structure.save()
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertFalse(mock_send_message.called)

    def test_should_send_fuel_notification_at_start_when_repeat_is_0(
        self, mock_send_message
    ):
        # given
        config = FuelAlertConfig.objects.create(start=12, end=0, repeat=0)
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(
            hours=11, minutes=59, seconds=59
        )
        structure.save()
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertTrue(mock_send_message.called)
        obj = FuelAlert.objects.first()
        self.assertEqual(obj.hours, 12)

    @patch(MODULE_PATH + ".Notification.send_to_webhook")
    def test_should_send_structure_fuel_notification_to_configured_webhook_only(
        self, mock_send_to_webhook, mock_send_message
    ):
        # given
        webhook_2 = Webhook.objects.create(
            name="Test 2", url="http://www.example.com/dummy-2/", is_active=True
        )
        webhook_2.notification_types = [
            NotificationType.STRUCTURE_DESTROYED,
            NotificationType.TOWER_RESOURCE_ALERT_MSG,
        ]
        webhook_2.save()
        self.owner.webhooks.add(webhook_2)
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=25)
        structure.save()
        mock_send_to_webhook.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertEqual(config.structure_fuel_alerts.count(), 1)
        self.assertEqual(mock_send_to_webhook.call_count, 1)
        args, _ = mock_send_to_webhook.call_args
        self.assertEqual(args[0], self.webhook)

    @patch(MODULE_PATH + ".Notification.send_to_webhook")
    def test_should_send_starbase_fuel_notification_to_configured_webhook_only(
        self, mock_send_to_webhook, mock_send_message
    ):
        # given
        webhook_2 = Webhook.objects.create(
            name="Test 2", url="http://www.example.com/dummy-2/", is_active=True
        )
        webhook_2.notification_types = [
            NotificationType.STRUCTURE_DESTROYED,
            NotificationType.STRUCTURE_FUEL_ALERT,
        ]
        webhook_2.save()
        self.owner.webhooks.add(webhook_2)
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1300000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=25)
        structure.save()
        mock_send_to_webhook.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertEqual(config.structure_fuel_alerts.count(), 1)
        self.assertEqual(mock_send_to_webhook.call_count, 1)
        args, _ = mock_send_to_webhook.call_args
        self.assertEqual(args[0], self.webhook)

    def test_should_remove_alerts_when_config_changes_1(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        FuelAlert.objects.create(structure=structure, config=config, hours=36)
        # when
        config.start = 36
        config.save()
        # then
        self.assertEqual(structure.structure_fuel_alerts.count(), 0)

    def test_should_remove_alerts_when_config_changes_2(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        FuelAlert.objects.create(structure=structure, config=config, hours=36)
        # when
        config.end = 2
        config.save()
        # then
        self.assertEqual(structure.structure_fuel_alerts.count(), 0)

    def test_should_remove_alerts_when_config_changes_3(self, mock_send_message):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        FuelAlert.objects.create(structure=structure, config=config, hours=36)
        # when
        config.repeat = 4
        config.save()
        # then
        self.assertEqual(structure.structure_fuel_alerts.count(), 0)

    def test_should_keep_alerts_when_config_updated_without_change(
        self, mock_send_message
    ):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        FuelAlert.objects.create(structure=structure, config=config, hours=36)
        # when
        config.save()
        # then
        self.assertEqual(structure.structure_fuel_alerts.count(), 1)


@patch(MODULE_PATH + ".Webhook.send_message", spec=True)
class TestJumpFuelAlerts(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)
        cls.webhook = Webhook.objects.get(name="Test Webhook 1")

    def test_should_output_str(self, mock_send_message):
        # given
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure = Structure.objects.get(id=1000000000004)
        alert = structure.jump_fuel_alerts.create(config=config)
        # when
        result = str(alert)
        # then
        self.assertIsInstance(result, str)

    def test_should_send_fuel_notification_for_structure(self, mock_send_message):
        # given
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=constants.EVE_TYPE_ID_LIQUID_OZONE,
            location_flag="StructureFuel",
            is_singleton=False,
            quantity=99,
        )
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertTrue(mock_send_message.called)
        alert = JumpFuelAlert.objects.first()
        self.assertEqual(alert.structure, structure)
        self.assertEqual(alert.config, config)

    def test_should_not_send_fuel_notification_that_already_exists(
        self, mock_send_message
    ):
        # given
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=constants.EVE_TYPE_ID_LIQUID_OZONE,
            location_flag="StructureFuel",
            is_singleton=False,
            quantity=99,
        )
        alert = structure.jump_fuel_alerts.create(config=config)
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertFalse(mock_send_message.called)
        self.assertEqual(structure.jump_fuel_alerts.count(), 1)
        self.assertEqual(structure.jump_fuel_alerts.first(), alert)

    def test_should_not_send_fuel_notification_if_above_threshold(
        self, mock_send_message
    ):
        # given
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=constants.EVE_TYPE_ID_LIQUID_OZONE,
            location_flag="StructureFuel",
            is_singleton=False,
            quantity=101,
        )
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertFalse(mock_send_message.called)
        self.assertEqual(structure.jump_fuel_alerts.count(), 0)

    def test_should_use_configured_ping_type_for_notifications(self, mock_send_message):
        # given
        config = JumpFuelAlertConfig.objects.create(
            threshold=100, channel_ping_type=Webhook.PingType.EVERYONE
        )
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=constants.EVE_TYPE_ID_LIQUID_OZONE,
            location_flag="StructureFuel",
            is_singleton=False,
            quantity=99,
        )
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertTrue(mock_send_message.called)
        _, kwargs = mock_send_message.call_args
        self.assertIn("@everyone", kwargs["content"])

    def test_should_use_configured_level_for_notifications(self, mock_send_message):
        # given
        config = JumpFuelAlertConfig.objects.create(
            threshold=100, color=Webhook.Color.SUCCESS
        )
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=constants.EVE_TYPE_ID_LIQUID_OZONE,
            location_flag="StructureFuel",
            is_singleton=False,
            quantity=99,
        )
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertTrue(mock_send_message.called)
        _, kwargs = mock_send_message.call_args
        embed = kwargs["embeds"][0]
        self.assertEqual(embed.color, Webhook.Color.SUCCESS)

    @patch(MODULE_PATH + ".Notification.send_to_webhook")
    def test_should_send_fuel_notification_to_configured_webhook_only(
        self, mock_send_to_webhook, mock_send_message
    ):
        # given
        webhook_2 = Webhook.objects.create(
            name="Test 2", url="http://www.example.com/dummy-2/", is_active=True
        )
        webhook_2.notification_types = [
            NotificationType.STRUCTURE_DESTROYED,
            NotificationType.TOWER_RESOURCE_ALERT_MSG,
        ]
        webhook_2.save()
        self.owner.webhooks.add(webhook_2)
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=constants.EVE_TYPE_ID_LIQUID_OZONE,
            location_flag="StructureFuel",
            is_singleton=False,
            quantity=99,
        )
        mock_send_to_webhook.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertEqual(config.jump_fuel_alerts.count(), 1)
        self.assertEqual(mock_send_to_webhook.call_count, 1)
        args, _ = mock_send_to_webhook.call_args
        self.assertEqual(args[0], self.webhook)

    def test_should_remove_alerts_when_config_changes(self, mock_send_message):
        # given
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure = Structure.objects.get(id=1000000000004)
        structure.jump_fuel_alerts.create(config=config)
        # when
        config.threshold = 50
        config.save()
        # then
        self.assertEqual(structure.jump_fuel_alerts.count(), 0)

    def test_should_keep_alerts_when_config_updated_without_change(
        self, mock_send_message
    ):
        # given
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure = Structure.objects.get(id=1000000000004)
        structure.jump_fuel_alerts.create(config=config)
        # when
        config.save()
        # then
        self.assertEqual(structure.jump_fuel_alerts.count(), 1)
