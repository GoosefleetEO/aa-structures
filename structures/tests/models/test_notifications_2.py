import datetime as dt
from unittest.mock import patch

from django.utils.timezone import now

from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from ...constants import EveTypeId
from ...models import (
    FuelAlert,
    FuelAlertConfig,
    JumpFuelAlert,
    JumpFuelAlertConfig,
    Notification,
    NotificationType,
    Structure,
    StructureItem,
    Webhook,
)
from ..testdata import (
    create_structures,
    load_entities,
    load_notification_by_type,
    load_notification_entities,
    set_owner_character,
)
from ..testdata.factories import (
    create_notification,
    create_owner_from_user,
    create_structure,
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
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
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

    def test_should_handle_no_fuel_situation(self, mock_send_message):
        # given
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        Structure.objects.get(id=1000000000004)
        mock_send_message.reset_mock()
        # when
        config.send_new_notifications()
        # then
        self.assertFalse(mock_send_message.called)

    def test_should_not_send_fuel_notification_that_already_exists(
        self, mock_send_message
    ):
        # given
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
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
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
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
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
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
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
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
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
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


class TestNotificationRelatedStructures(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        user, _ = create_user_from_evecharacter(
            1001, permissions=["structures.add_structure_owner"]
        )
        cls.owner = create_owner_from_user(user=user)

    def test_related_structures_for_structure_notifications(self):
        # given
        structure = create_structure(owner=self.owner, id=1000000000001)
        for notif_type in [
            NotificationType.STRUCTURE_ONLINE,
            NotificationType.STRUCTURE_FUEL_ALERT,
            NotificationType.STRUCTURE_SERVICES_OFFLINE,
            NotificationType.STRUCTURE_WENT_LOW_POWER,
            NotificationType.STRUCTURE_WENT_HIGH_POWER,
            NotificationType.STRUCTURE_UNANCHORING,
            NotificationType.STRUCTURE_UNDER_ATTACK,
            NotificationType.STRUCTURE_LOST_SHIELD,
            NotificationType.STRUCTURE_LOST_ARMOR,
            NotificationType.STRUCTURE_DESTROYED,
            NotificationType.OWNERSHIP_TRANSFERRED,
            NotificationType.STRUCTURE_ANCHORING,
        ]:
            with self.subTest(notif_type=notif_type):
                notif = load_notification_by_type(
                    owner=self.owner, notif_type=notif_type
                )
                # when
                result_qs = notif.calc_related_structures()
                # then
                self.assertQuerysetEqual(
                    result_qs, Structure.objects.filter(id=structure.id)
                )

    def test_related_structures_for_moon_notifications(self):
        # given
        structure = create_structure(owner=self.owner, id=1000000000002)
        for notif_type in [
            NotificationType.MOONMINING_EXTRACTION_STARTED,
            NotificationType.MOONMINING_EXTRACTION_FINISHED,
            NotificationType.MOONMINING_AUTOMATIC_FRACTURE,
            NotificationType.MOONMINING_EXTRACTION_CANCELLED,
            NotificationType.MOONMINING_LASER_FIRED,
        ]:
            with self.subTest(notif_type=notif_type):
                notif = load_notification_by_type(
                    owner=self.owner, notif_type=notif_type
                )
                # when
                result_qs = notif.calc_related_structures()
                # then
                self.assertQuerysetEqual(
                    result_qs, Structure.objects.filter(id=structure.id)
                )

    def test_related_structures_for_orbital_notifications(self):
        # given
        structure = create_structure(
            owner=self.owner, eve_planet_id=40161469, eve_type_id=2233
        )
        for notif_type in [
            NotificationType.ORBITAL_ATTACKED,
            NotificationType.ORBITAL_REINFORCED,
        ]:
            with self.subTest(notif_type=notif_type):
                notif = load_notification_by_type(
                    owner=self.owner, notif_type=notif_type
                )
                # when
                result_qs = notif.calc_related_structures()
                # then
                self.assertQuerysetEqual(
                    result_qs, Structure.objects.filter(id=structure.id)
                )

    def test_related_structures_for_tower_notifications(self):
        # given
        structure = create_structure(
            owner=self.owner, eve_moon_id=40161465, eve_type_id=16213
        )
        for notif_type in [
            NotificationType.TOWER_ALERT_MSG,
            NotificationType.TOWER_RESOURCE_ALERT_MSG,
        ]:
            with self.subTest(notif_type=notif_type):
                notif = load_notification_by_type(
                    owner=self.owner, notif_type=notif_type
                )
                # when
                result_qs = notif.calc_related_structures()
                # then
                self.assertQuerysetEqual(
                    result_qs, Structure.objects.filter(id=structure.id)
                )

    def test_related_structures_for_generated_notifications(self):
        # given
        structure = create_structure(
            owner=self.owner, eve_moon_id=40161465, eve_type_id=16213
        )
        for notif_type in [
            NotificationType.STRUCTURE_JUMP_FUEL_ALERT,
            NotificationType.STRUCTURE_REFUELED_EXTRA,
            NotificationType.TOWER_REFUELED_EXTRA,
        ]:
            with self.subTest(notif_type=notif_type):
                notif = Notification.create_from_structure(
                    structure, notif_type=notif_type
                )
                # when
                result_qs = notif.calc_related_structures()
                # then
                self.assertQuerysetEqual(
                    result_qs, Structure.objects.filter(id=structure.id)
                )

    def test_should_update_related_structure_when_it_exists(self):
        # given
        structure = create_structure(owner=self.owner)
        notif = create_notification(owner=self.owner)
        # when
        with patch(MODULE_PATH + ".Notification.calc_related_structures") as m:
            m.return_value = Structure.objects.filter(id=structure.id)
            result = notif.update_related_structures()
        # then
        structure_ids = notif.structures.values_list("id", flat=True)
        self.assertSetEqual(set(structure_ids), {structure.id})
        self.assertTrue(result)

    def test_should_not_update_related_structure_when_not_found(self):
        # given
        notif = create_notification(owner=self.owner)
        # when
        with patch(MODULE_PATH + ".Notification.calc_related_structures") as m:
            m.return_value = Structure.objects.none()
            result = notif.update_related_structures()
        # then
        self.assertFalse(result)
