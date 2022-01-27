import datetime as dt
import re
from unittest.mock import Mock, patch

import pytz
from requests.exceptions import HTTPError

from django.contrib.auth.models import Group
from django.utils.timezone import now

from allianceauth.eveonline.models import EveAllianceInfo, EveCorporationInfo
from app_utils.django import app_labels
from app_utils.testing import NoSocketsTestCase

from ...models import EveEntity, Notification, NotificationType, Structure, Webhook
from ..testdata import (
    create_structures,
    load_entities,
    load_notification_entities,
    set_owner_character,
)

MODULE_PATH = "structures.models.notifications"


if "structuretimers" in app_labels():
    from ..testdata.load_eveuniverse import load_eveuniverse


class TestEveEntities(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([EveEntity])

    def test_str(self):
        obj = EveEntity.objects.get(id=3011)
        self.assertEqual(str(obj), "Big Bad Alliance")

    def test_repr(self):
        obj = EveEntity.objects.get(id=3011)
        expected = "EveEntity(id=3011, category='alliance', name='Big Bad Alliance')"
        self.assertEqual(repr(obj), expected)

    def test_get_matching_entity_type(self):
        self.assertEqual(
            EveEntity.Category.from_esi_name("character"),
            EveEntity.Category.CHARACTER,
        )
        self.assertEqual(
            EveEntity.Category.from_esi_name("corporation"),
            EveEntity.Category.CORPORATION,
        )
        self.assertEqual(
            EveEntity.Category.from_esi_name("alliance"),
            EveEntity.Category.ALLIANCE,
        )
        self.assertEqual(
            EveEntity.Category.from_esi_name("faction"),
            EveEntity.Category.FACTION,
        )
        self.assertEqual(
            EveEntity.Category.from_esi_name("other"),
            EveEntity.Category.OTHER,
        )
        self.assertEqual(
            EveEntity.Category.from_esi_name("does not exist"),
            EveEntity.Category.OTHER,
        )

    def test_profile_url(self):
        x = EveEntity.objects.get(id=3001)
        self.assertEqual(
            x.profile_url(), "http://evemaps.dotlan.net/alliance/Wayne_Enterprises"
        )

        x = EveEntity.objects.get(id=2001)
        self.assertEqual(
            x.profile_url(), "http://evemaps.dotlan.net/corp/Wayne_Technologies"
        )
        x = EveEntity.objects.get(id=1011)
        self.assertEqual(x.profile_url(), "")


class TestNotification(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)
        cls.webhook = Webhook.objects.create(
            name="Test", url="http://www.example.com/dummy/"
        )
        cls.owner.webhooks.add(cls.webhook)

    def test_str(self):
        obj = Notification.objects.get(notification_id=1000000403)
        self.assertEqual(str(obj), "1000000403")

    def test_repr(self):
        obj = Notification.objects.get(notification_id=1000000403)
        expected = (
            "Notification(notification_id=1000000403, "
            "owner='Wayne Technologies', "
            "notif_type='MoonminingExtractionFinished')"
        )
        self.assertEqual(repr(obj), expected)

    def test_get_parsed_text(self):
        obj = Notification.objects.get(notification_id=1000000404)
        parsed_text = obj.get_parsed_text()
        self.assertEqual(parsed_text["autoTime"], 132186924601059151)
        self.assertEqual(parsed_text["structureName"], "Dummy")
        self.assertEqual(parsed_text["solarSystemID"], 30002537)

    def test_is_npc_attacking(self):
        x1 = Notification.objects.get(notification_id=1000000509)
        self.assertFalse(x1.is_npc_attacking())
        x2 = Notification.objects.get(notification_id=1000010509)
        self.assertTrue(x2.is_npc_attacking())
        x3 = Notification.objects.get(notification_id=1000010601)
        self.assertTrue(x3.is_npc_attacking())

    @patch(MODULE_PATH + ".STRUCTURES_REPORT_NPC_ATTACKS", True)
    def test_filter_npc_attacks_1(self):
        # NPC reporting allowed and not a NPC attacker
        x1 = Notification.objects.get(notification_id=1000000509)
        self.assertFalse(x1.filter_for_npc_attacks())

        # NPC reporting allowed and a NPC attacker
        x1 = Notification.objects.get(notification_id=1000010509)
        self.assertFalse(x1.filter_for_npc_attacks())

    @patch(MODULE_PATH + ".STRUCTURES_REPORT_NPC_ATTACKS", False)
    def test_filter_npc_attacks_2(self):
        # NPC reporting not allowed and not a NPC attacker
        x1 = Notification.objects.get(notification_id=1000000509)
        self.assertFalse(x1.filter_for_npc_attacks())

        # NPC reporting not allowed and a NPC attacker
        x1 = Notification.objects.get(notification_id=1000010509)
        self.assertTrue(x1.filter_for_npc_attacks())

    def test_can_be_rendered_1(self):
        for ntype in NotificationType.values:
            with self.subTest(notification_type=ntype):
                notif = Notification.objects.filter(notif_type=ntype).first()
                if notif:
                    self.assertTrue(notif.can_be_rendered)

    def test_can_be_rendered_2(self):
        structure = Structure.objects.get(id=1000000000001)
        for ntype in [
            NotificationType.STRUCTURE_REFUELED_EXTRA,
            NotificationType.TOWER_REFUELED_EXTRA,
        ]:
            with self.subTest(notification_type=ntype):
                notif = Notification.create_from_structure(structure, ntype)
                if notif:
                    self.assertTrue(notif.can_be_rendered)

    def test_can_be_rendered_3(self):
        for ntype in ["DeclareWar"]:
            with self.subTest(notification_type=ntype):
                notif = Notification.objects.filter(notif_type=ntype).first()
                if notif:
                    self.assertFalse(notif.can_be_rendered)


class TestNotificationFilterForAllianceLevel(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)

    def test_should_not_filter_non_alliance_notifications_1(self):
        # given
        self.owner.is_alliance_main = False
        self.owner.save()
        notif = self.owner.notifications.get(notification_id=1000000509)
        # when/then
        self.assertFalse(notif.filter_for_alliance_level())

    def test_should_not_filter_non_alliance_notifications_2(self):
        # given
        self.owner.is_alliance_main = True
        self.owner.save()
        notif = self.owner.notifications.get(notification_id=1000000509)
        # when/then
        self.assertFalse(notif.filter_for_alliance_level())

    def test_should_filter_alliance_notifications(self):
        # given
        self.owner.is_alliance_main = False
        self.owner.save()
        notif = self.owner.notifications.get(notification_id=1000000803)
        # when/then
        self.assertTrue(notif.filter_for_alliance_level())

    def test_should_not_filter_alliance_notifications_1(self):
        # given
        self.owner.is_alliance_main = True
        self.owner.save()
        # when/then
        notif = self.owner.notifications.get(notification_id=1000000803)
        self.assertFalse(notif.filter_for_alliance_level())

    def test_should_not_filter_alliance_notifications_2(self):
        # given
        self.owner.is_alliance_main = True
        self.owner.save()
        notif = self.owner.notifications.get(notification_id=1000000803)
        self.assertFalse(notif.filter_for_alliance_level())

    def test_should_not_filter_alliance_notifications_3(self):
        # given
        _, owner = set_owner_character(character_id=1102)  # corp with no alliance
        load_notification_entities(owner)
        notif = owner.notifications.get(notification_id=1000000803)
        self.assertFalse(notif.filter_for_alliance_level())


class TestNotificationCreateFromStructure(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)

    def test_should_create_notification_for_structure_fuel_alerts(self):
        # given
        structure = Structure.objects.get(id=1000000000001)
        # when
        notif = Notification.create_from_structure(
            structure, notif_type=NotificationType.STRUCTURE_FUEL_ALERT
        )
        # then
        self.assertIsInstance(notif, Notification)
        self.assertTrue(notif.is_generated)
        self.assertAlmostEqual(notif.timestamp, now(), delta=dt.timedelta(seconds=10))
        self.assertAlmostEqual(
            notif.last_updated, now(), delta=dt.timedelta(seconds=10)
        )
        self.assertEqual(notif.owner, structure.owner)
        self.assertEqual(notif.sender_id, 1000137)
        self.assertEqual(notif.notif_type, NotificationType.STRUCTURE_FUEL_ALERT)

    def test_should_create_notification_for_tower_fuel_alerts(self):
        # given
        structure = Structure.objects.get(id=1300000000001)
        # when
        notif = Notification.create_from_structure(
            structure, notif_type=NotificationType.TOWER_RESOURCE_ALERT_MSG
        )
        # then
        self.assertIsInstance(notif, Notification)
        self.assertTrue(notif.is_generated)
        self.assertAlmostEqual(notif.timestamp, now(), delta=dt.timedelta(seconds=10))
        self.assertAlmostEqual(
            notif.last_updated, now(), delta=dt.timedelta(seconds=10)
        )
        self.assertEqual(notif.owner, structure.owner)
        self.assertEqual(notif.sender_id, 1000137)
        self.assertEqual(notif.notif_type, NotificationType.TOWER_RESOURCE_ALERT_MSG)

    def test_should_create_notification_with_additional_params(self):
        # given
        structure = Structure.objects.get(id=1000000000001)
        # when
        notif = Notification.create_from_structure(
            structure, notif_type=NotificationType.STRUCTURE_FUEL_ALERT, is_read=True
        )
        # then
        self.assertIsInstance(notif, Notification)
        self.assertEqual(notif.notif_type, NotificationType.STRUCTURE_FUEL_ALERT)
        self.assertTrue(notif.is_read)

    def test_should_raise_error_when_text_is_missing(self):
        # given
        structure = Structure.objects.get(id=1000000000001)
        # when/then
        with self.assertRaises(ValueError):
            Notification.create_from_structure(
                structure, notif_type=NotificationType.STRUCTURE_LOST_ARMOR
            )


class TestNotificationSendToWebhooks(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        cls.structure = Structure.objects.get(id=1000000000001)
        webhook_2 = Webhook.objects.create(name="Dummy 2", url="dummy-2")
        cls.owner.webhooks.add(webhook_2)

    def setUp(self) -> None:
        Webhook.objects.update(is_active=False, notification_types=[])

    @patch(MODULE_PATH + ".Webhook.send_message")
    def test_should_send_to_wehook(self, mock_send_message):
        # given
        webhook = self.owner.webhooks.first()
        webhook.is_active = True
        webhook.notification_types = [NotificationType.STRUCTURE_REFUELED_EXTRA]
        webhook.save()
        notif = Notification.create_from_structure(
            self.structure, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertTrue(result)
        self.assertTrue(mock_send_message.called)
        _, kwargs = mock_send_message.call_args
        self.assertEqual(kwargs["content"], "")

    @patch(MODULE_PATH + ".Notification.send_to_webhook")
    def test_should_send_to_multiple_webhooks(self, mock_send_to_webhook):
        # given
        Webhook.objects.update(is_active=True)
        webhook_1 = self.owner.webhooks.first()
        webhook_1.notification_types = [
            NotificationType.STRUCTURE_REFUELED_EXTRA,
            NotificationType.STRUCTURE_ANCHORING,
        ]
        webhook_1.save()
        webhook_2 = self.owner.webhooks.last()
        webhook_2.notification_types = [
            NotificationType.STRUCTURE_REFUELED_EXTRA,
            NotificationType.STRUCTURE_DESTROYED,
        ]
        webhook_2.save()
        self.owner
        notif = Notification.create_from_structure(
            self.structure, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertTrue(result)
        self.assertEqual(mock_send_to_webhook.call_count, 2)
        webhook_pks = {call[0][0].pk for call in mock_send_to_webhook.call_args_list}
        self.assertSetEqual(webhook_pks, {webhook_1.pk, webhook_2.pk})

    @patch(MODULE_PATH + ".Webhook.send_message")
    def test_should_not_send_when_webhooks_are_inactive(self, mock_send_message):
        # given
        webhook = self.owner.webhooks.first()
        webhook.notification_types = [NotificationType.STRUCTURE_REFUELED_EXTRA]
        webhook.save()
        notif = Notification.create_from_structure(
            self.structure, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertIsNone(result)
        self.assertFalse(mock_send_message.called)

    @patch(MODULE_PATH + ".Webhook.send_message")
    def test_should_not_send_when_notif_types_dont_match(self, mock_send_message):
        # given
        webhook = self.owner.webhooks.first()
        webhook.is_active = True
        webhook.save()
        notif = Notification.create_from_structure(
            self.structure, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertIsNone(result)
        self.assertFalse(mock_send_message.called)

    @patch(MODULE_PATH + ".Webhook.send_message")
    def test_should_override_ping_type(self, mock_send_message):
        # given
        webhook = self.owner.webhooks.first()
        webhook.is_active = True
        webhook.notification_types = [NotificationType.STRUCTURE_REFUELED_EXTRA]
        webhook.save()
        notif = Notification.create_from_structure(
            self.structure, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        notif.send_to_configured_webhooks(ping_type_override=Webhook.PingType.HERE)
        # then
        self.assertTrue(mock_send_message.called)
        _, kwargs = mock_send_message.call_args
        self.assertIn("@here", kwargs["content"])

    @patch(MODULE_PATH + ".Webhook.send_message")
    def test_should_override_color(self, mock_send_message):
        # given
        webhook = self.owner.webhooks.first()
        webhook.is_active = True
        webhook.notification_types = [NotificationType.STRUCTURE_REFUELED_EXTRA]
        webhook.save()
        notif = Notification.create_from_structure(
            self.structure, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        notif.send_to_configured_webhooks(
            use_color_override=True, color_override=Webhook.Color.DANGER
        )
        # then
        self.assertTrue(mock_send_message.called)
        _, kwargs = mock_send_message.call_args
        self.assertEqual(kwargs["embeds"][0].color, Webhook.Color.DANGER)

    @patch(MODULE_PATH + ".Webhook.send_message")
    def test_should_return_false_when_sending_failed(self, mock_send_message):
        # given
        mock_send_message.return_value = False
        webhook = self.owner.webhooks.first()
        webhook.is_active = True
        webhook.notification_types = [NotificationType.STRUCTURE_REFUELED_EXTRA]
        webhook.save()
        notif = Notification.create_from_structure(
            self.structure, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertFalse(result)
        self.assertTrue(mock_send_message.called)


@patch(MODULE_PATH + ".Webhook.send_message", spec=True)
class TestNotificationSendMessage(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)
        cls.webhook = Webhook.objects.create(
            name="Test", url="http://www.example.com/dummy/"
        )
        cls.owner.webhooks.add(cls.webhook)

    def test_can_send_message_normal(self, mock_send_message):
        mock_send_message.return_value = True

        obj = Notification.objects.get(notification_id=1000020601)
        result = obj.send_to_webhook(self.webhook)
        self.assertTrue(result)
        _, kwargs = mock_send_message.call_args
        self.assertIsNotNone(kwargs["content"])
        self.assertIsNotNone(kwargs["embeds"])

    def test_should_ignore_unsupported_notif_types(self, mock_send_message):
        # given
        mock_send_message.return_value = True
        obj = Notification.objects.create(
            notification_id=666,
            owner=self.owner,
            sender=EveEntity.objects.get(id=2001),
            timestamp=now(),
            notif_type="XXXUnsupportedNotificationTypeXXX",
            last_updated=now(),
        )
        # when
        result = obj.send_to_webhook(self.webhook)
        # then
        self.assertFalse(result)

    def test_mark_notification_as_sent_when_successful(self, mock_send_message):
        mock_send_message.return_value = True

        obj = Notification.objects.get(notification_id=1000020601)
        obj.send_to_webhook(self.webhook)
        obj.refresh_from_db()
        self.assertTrue(obj.is_sent)

    def test_dont_mark_notification_as_sent_when_error(self, mock_send_message):
        mock_send_message.return_value = False

        obj = Notification.objects.get(notification_id=1000020601)
        obj.send_to_webhook(self.webhook)
        obj.refresh_from_db()
        self.assertFalse(obj.is_sent)

    def test_send_to_webhook_all_notification_types(self, mock_send_message):
        mock_send_message.return_value = True

        types_tested = set()
        for notif in Notification.objects.all():
            if notif.notif_type in NotificationType.values:
                self.assertFalse(notif.is_sent)
                self.assertTrue(notif.send_to_webhook(self.webhook))
                types_tested.add(notif.notif_type)

        # make sure we have tested all existing esi notification types
        self.assertSetEqual(NotificationType.esi_notifications, types_tested)

    def test_should_create_notification_for_structure_refueled(self, mock_send_message):
        # given
        mock_send_message.return_value = True
        structure = Structure.objects.get(id=1000000000001)
        notif = Notification.create_from_structure(
            structure, NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_webhook(self.webhook)
        # then
        self.assertTrue(result)

    def test_should_create_notification_for_tower_refueled(self, mock_send_message):
        # given
        mock_send_message.return_value = True
        structure = Structure.objects.get(id=1300000000001)
        notif = Notification.create_from_structure(
            structure, NotificationType.TOWER_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_webhook(self.webhook)
        # then
        self.assertTrue(result)

    @patch(MODULE_PATH + ".STRUCTURES_DEFAULT_LANGUAGE", "en")
    def test_send_notification_without_existing_structure(self, mock_send_message):
        mock_send_message.return_value = True

        Structure.objects.all().delete()
        obj = Notification.objects.get(notification_id=1000000505)
        obj.send_to_webhook(self.webhook)
        embed = mock_send_message.call_args[1]["embeds"][0]
        self.assertEqual(
            embed.description[:39], "The Astrahus **(unknown)** in [Amamake]"
        )

    @patch(MODULE_PATH + ".STRUCTURES_DEFAULT_LANGUAGE", "en")
    def test_notification_with_null_aggressor_alliance(self, mock_send_message):
        mock_send_message.return_value = True

        obj = Notification.objects.get(notification_id=1000020601)
        result = obj.send_to_webhook(self.webhook)
        self.assertTrue(result)

    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SET_AVATAR", True)
    def test_can_send_message_with_setting_avatar(self, mock_send_message):
        mock_send_message.return_value = True

        obj = Notification.objects.get(notification_id=1000020601)
        result = obj.send_to_webhook(self.webhook)
        self.assertTrue(result)
        _, kwargs = mock_send_message.call_args
        self.assertIsNotNone(kwargs["avatar_url"])
        self.assertIsNotNone(kwargs["username"])

    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SET_AVATAR", False)
    def test_can_send_message_without_setting_avatar(self, mock_send_message):
        mock_send_message.return_value = True

        obj = Notification.objects.get(notification_id=1000020601)
        result = obj.send_to_webhook(self.webhook)
        self.assertTrue(result)
        _, kwargs = mock_send_message.call_args
        self.assertIsNone(kwargs["avatar_url"])
        self.assertIsNone(kwargs["username"])


class TestNotificationPings(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def setUp(self):
        create_structures(dont_load_entities=True)
        _, self.owner = set_owner_character(character_id=1001)
        load_notification_entities(self.owner)

    @patch(MODULE_PATH + ".Webhook.send_message", spec=True)
    def test_can_ping(self, mock_send_message):
        args = {"status_code": 200, "status_ok": True, "content": None}
        mock_response = Mock(**args)
        mock_send_message.return_value = mock_response

        webhook_normal = Webhook.objects.create(
            name="Test", url="http://www.example.com/dummy/"
        )
        obj = Notification.objects.get(notification_id=1000000509)
        self.assertTrue(obj.send_to_webhook(webhook_normal))
        args, kwargs = mock_send_message.call_args
        self.assertTrue(kwargs["content"] and "@everyone" in kwargs["content"])

    @patch(MODULE_PATH + ".Webhook.send_message", spec=True)
    def test_can_disable_pinging_webhook(self, mock_send_message):
        args = {"status_code": 200, "status_ok": True, "content": None}
        mock_response = Mock(**args)
        mock_send_message.return_value = mock_response

        webhook_no_pings = Webhook.objects.create(
            name="Test2",
            url="http://www.example.com/x-2/",
            has_default_pings_enabled=False,
        )
        obj = Notification.objects.get(notification_id=1000000509)
        self.assertTrue(obj.send_to_webhook(webhook_no_pings))
        args, kwargs = mock_send_message.call_args
        self.assertFalse(kwargs["content"] and "@everyone" in kwargs["content"])

    @patch(MODULE_PATH + ".Webhook.send_message", spec=True)
    def test_can_disable_pinging_owner(self, mock_send_message):
        args = {"status_code": 200, "status_ok": True, "content": None}
        mock_response = Mock(**args)
        mock_send_message.return_value = mock_response

        webhook_normal = Webhook.objects.create(
            name="Test", url="http://www.example.com/dummy/"
        )
        self.owner.webhooks.add(webhook_normal)
        self.owner.has_default_pings_enabled = False
        self.owner.save()
        obj = Notification.objects.get(notification_id=1000000509)
        self.assertTrue(obj.send_to_webhook(webhook_normal))
        args, kwargs = mock_send_message.call_args
        self.assertFalse(kwargs["content"] and "@everyone" in kwargs["content"])


if "discord" in app_labels():

    @patch(MODULE_PATH + ".Notification._import_discord")
    class TestGroupPings(NoSocketsTestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            load_entities()
            cls.group_1 = Group.objects.create(name="Dummy Group 1")
            cls.group_2 = Group.objects.create(name="Dummy Group 2")
            create_structures(dont_load_entities=True)

        def setUp(self):
            _, self.owner = set_owner_character(character_id=1001)
            load_notification_entities(self.owner)

        @staticmethod
        def _my_group_to_role(group: Group) -> dict:
            if not isinstance(group, Group):
                raise TypeError("group must be of type Group")

            return {"id": group.pk, "name": group.name}

        @patch(MODULE_PATH + ".Webhook.send_message", spec=True)
        def test_can_ping_via_webhook(self, mock_send_message, mock_import_discord):
            args = {"status_code": 200, "status_ok": True, "content": None}
            mock_send_message.return_value = Mock(**args)
            mock_import_discord.return_value.objects.group_to_role.side_effect = (
                self._my_group_to_role
            )
            webhook = Webhook.objects.create(
                name="Test", url="http://www.example.com/dummy/"
            )
            webhook.ping_groups.add(self.group_1)

            obj = Notification.objects.get(notification_id=1000000509)
            self.assertTrue(obj.send_to_webhook(webhook))

            self.assertTrue(mock_import_discord.called)
            args, kwargs = mock_send_message.call_args
            self.assertIn(f"<@&{self.group_1.pk}>", kwargs["content"])

        @patch(MODULE_PATH + ".Webhook.send_message", spec=True)
        def test_can_ping_via_owner(self, mock_send_message, mock_import_discord):
            args = {"status_code": 200, "status_ok": True, "content": None}
            mock_send_message.return_value = Mock(**args)
            mock_import_discord.return_value.objects.group_to_role.side_effect = (
                self._my_group_to_role
            )
            webhook = Webhook.objects.create(
                name="Test", url="http://www.example.com/dummy/"
            )
            self.owner.ping_groups.add(self.group_2)

            obj = Notification.objects.get(notification_id=1000000509)
            self.assertTrue(obj.send_to_webhook(webhook))

            self.assertTrue(mock_import_discord.called)
            args, kwargs = mock_send_message.call_args
            self.assertIn(f"<@&{self.group_2.pk}>", kwargs["content"])

        @patch(MODULE_PATH + ".Webhook.send_message", spec=True)
        def test_can_ping_both(self, mock_send_message, mock_import_discord):
            args = {"status_code": 200, "status_ok": True, "content": None}
            mock_send_message.return_value = Mock(**args)
            mock_import_discord.return_value.objects.group_to_role.side_effect = (
                self._my_group_to_role
            )
            webhook = Webhook.objects.create(
                name="Test", url="http://www.example.com/dummy/"
            )
            webhook.ping_groups.add(self.group_1)
            self.owner.ping_groups.add(self.group_2)

            obj = Notification.objects.get(notification_id=1000000509)
            self.assertTrue(obj.send_to_webhook(webhook))

            self.assertTrue(mock_import_discord.called)
            args, kwargs = mock_send_message.call_args
            self.assertIn(f"<@&{self.group_1.pk}>", kwargs["content"])
            self.assertIn(f"<@&{self.group_2.pk}>", kwargs["content"])

        @patch(MODULE_PATH + ".Webhook.send_message", spec=True)
        def test_no_ping_if_not_set(self, mock_send_message, mock_import_discord):
            args = {"status_code": 200, "status_ok": True, "content": None}
            mock_send_message.return_value = Mock(**args)
            mock_import_discord.return_value.objects.group_to_role.side_effect = (
                self._my_group_to_role
            )
            webhook = Webhook.objects.create(
                name="Test", url="http://www.example.com/dummy/"
            )

            obj = Notification.objects.get(notification_id=1000000509)
            self.assertTrue(obj.send_to_webhook(webhook))

            self.assertFalse(mock_import_discord.called)
            args, kwargs = mock_send_message.call_args
            self.assertFalse(re.search(r"(<@&\d+>)", kwargs["content"]))

        @patch(MODULE_PATH + ".Webhook.send_message", spec=True)
        def test_can_handle_http_error(self, mock_send_message, mock_import_discord):
            args = {"status_code": 200, "status_ok": True, "content": None}
            mock_send_message.return_value = Mock(**args)
            mock_import_discord.return_value.objects.group_to_role.side_effect = (
                HTTPError
            )
            webhook = Webhook.objects.create(
                name="Test", url="http://www.example.com/dummy/"
            )
            webhook.ping_groups.add(self.group_1)

            obj = Notification.objects.get(notification_id=1000000509)
            self.assertTrue(obj.send_to_webhook(webhook))

            self.assertTrue(mock_import_discord.called)
            args, kwargs = mock_send_message.call_args
            self.assertFalse(re.search(r"(<@&\d+>)", kwargs["content"]))


if "timerboard" in app_labels():

    from allianceauth.timerboard.models import Timer as AuthTimer

    @patch(
        "structuretimers.models._task_calc_timer_distances_for_all_staging_systems",
        Mock(),
    )
    @patch("structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False)
    class TestNotificationAddToTimerboard(NoSocketsTestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            create_structures()
            load_eveuniverse()
            _, cls.owner = set_owner_character(character_id=1001)
            load_notification_entities(cls.owner)
            cls.webhook = Webhook.objects.create(
                name="Test", url="http://www.example.com/dummy/"
            )
            cls.owner.webhooks.add(cls.webhook)

        def setUp(self) -> None:
            AuthTimer.objects.all().delete()

        @patch(MODULE_PATH + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", False)
        @patch("allianceauth.timerboard.models.Timer", spec=True)
        def test_moon_timers_disabled(self, mock_Timer):
            x = Notification.objects.get(notification_id=1000000404)
            self.assertFalse(x.process_for_timerboard())
            self.assertFalse(mock_Timer.objects.create.called)

            x = Notification.objects.get(notification_id=1000000402)
            self.assertFalse(x.process_for_timerboard())
            self.assertFalse(mock_Timer.delete.called)

        @patch(MODULE_PATH + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", True)
        def test_normal(self):
            notification_without_timer_query = Notification.objects.filter(
                notification_id__in=[
                    1000000401,
                    1000000403,
                    1000000405,
                    1000000502,
                    1000000503,
                    1000000506,
                    1000000507,
                    1000000508,
                    1000000509,
                    1000000510,
                    1000000511,
                    1000000512,
                    1000000513,
                    1000000601,
                    1000010509,
                    1000010601,
                ]
            )
            for x in notification_without_timer_query:
                self.assertFalse(x.process_for_timerboard())

            self.assertEqual(AuthTimer.objects.count(), 0)

            x = Notification.objects.get(notification_id=1000000501)
            self.assertFalse(x.process_for_timerboard())

            x = Notification.objects.get(notification_id=1000000504)
            self.assertTrue(x.process_for_timerboard())

            x = Notification.objects.get(notification_id=1000000505)
            self.assertTrue(x.process_for_timerboard())

            x = Notification.objects.get(notification_id=1000000602)
            self.assertTrue(x.process_for_timerboard())

            ids_set_1 = {x.id for x in AuthTimer.objects.all()}
            x = Notification.objects.get(notification_id=1000000404)
            self.assertTrue(x.process_for_timerboard())

            self.assertEqual(AuthTimer.objects.count(), 4)

            # this should remove the right timer only
            x = Notification.objects.get(notification_id=1000000402)
            x.process_for_timerboard()
            self.assertEqual(AuthTimer.objects.count(), 3)
            ids_set_2 = {x.id for x in AuthTimer.objects.all()}
            self.assertSetEqual(ids_set_1, ids_set_2)

        @patch(MODULE_PATH + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", True)
        def test_run_all(self):
            for x in Notification.objects.all():
                x.process_for_timerboard()

        @patch(MODULE_PATH + ".STRUCTURES_TIMERS_ARE_CORP_RESTRICTED", False)
        def test_corp_restriction_1(self):
            # given
            notif = Notification.objects.get(notification_id=1000000504)
            # when
            result = notif.process_for_timerboard()
            # then
            self.assertTrue(result)
            timer = AuthTimer.objects.first()
            self.assertFalse(timer.corp_timer)

        @patch(MODULE_PATH + ".STRUCTURES_TIMERS_ARE_CORP_RESTRICTED", True)
        def test_corp_restriction_2(self):
            x = Notification.objects.get(notification_id=1000000504)
            self.assertTrue(x.process_for_timerboard())
            t = AuthTimer.objects.first()
            self.assertTrue(t.corp_timer)


if "structuretimers" in app_labels():

    from structuretimers.models import Timer

    from eveuniverse.models import EveSolarSystem as EveSolarSystem2
    from eveuniverse.models import EveType as EveType2

    @patch(
        "structuretimers.models._task_calc_timer_distances_for_all_staging_systems",
        Mock(),
    )
    @patch("structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False)
    @patch(MODULE_PATH + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", True)
    class TestNotificationAddToTimerboard2(NoSocketsTestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            create_structures()
            load_eveuniverse()

        def setUp(self) -> None:
            _, self.owner = set_owner_character(character_id=1001)
            load_notification_entities(self.owner)
            self.webhook = Webhook.objects.create(
                name="Test", url="http://www.example.com/dummy/"
            )
            self.owner.webhooks.add(self.webhook)
            Timer.objects.all().delete()

        def test_timer_structure_reinforcement(self):
            notification = Notification.objects.get(notification_id=1000000505)
            self.assertTrue(notification.process_for_timerboard())
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(
                timer.eve_solar_system, EveSolarSystem2.objects.get(id=30002537)
            )
            self.assertEqual(timer.structure_type, EveType2.objects.get(id=35832))
            self.assertEqual(timer.timer_type, Timer.TYPE_ARMOR)
            self.assertEqual(timer.objective, Timer.OBJECTIVE_FRIENDLY)
            self.assertAlmostEqual(
                timer.date, now() + dt.timedelta(hours=47), delta=dt.timedelta(hours=1)
            )
            self.assertEqual(
                timer.eve_corporation,
                EveCorporationInfo.objects.get(corporation_id=2001),
            )
            self.assertEqual(
                timer.eve_alliance, EveAllianceInfo.objects.get(alliance_id=3001)
            )
            self.assertEqual(timer.visibility, Timer.VISIBILITY_UNRESTRICTED)
            self.assertEqual(timer.structure_name, "Test Structure Alpha")
            self.assertEqual(timer.owner_name, "Wayne Technologies")
            self.assertTrue(timer.details_notes)

        def test_timer_sov_reinforcement(self):
            notification = Notification.objects.get(notification_id=1000000804)

            # do not process if owner is not set as main for alliance
            self.assertFalse(notification.process_for_timerboard())

            # process for alliance main
            self.owner.is_alliance_main = True
            self.owner.save()
            notification.owner.refresh_from_db()
            self.assertTrue(notification.process_for_timerboard())

            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(timer.timer_type, Timer.TYPE_FINAL)
            self.assertEqual(
                timer.eve_solar_system, EveSolarSystem2.objects.get(id=30000474)
            )
            self.assertEqual(timer.structure_type, EveType2.objects.get(id=32226))
            self.assertAlmostEqual(
                timer.date,
                pytz.utc.localize(dt.datetime(2018, 12, 20, 17, 3, 22)),
                delta=dt.timedelta(seconds=120),
            )
            self.assertEqual(
                timer.eve_corporation,
                EveCorporationInfo.objects.get(corporation_id=2001),
            )
            self.assertEqual(
                timer.eve_alliance, EveAllianceInfo.objects.get(alliance_id=3001)
            )
            self.assertEqual(timer.visibility, Timer.VISIBILITY_UNRESTRICTED)
            self.assertEqual(timer.owner_name, "Wayne Enterprises")
            self.assertTrue(timer.details_notes)

        def test_timer_orbital_reinforcements(self):
            notification = Notification.objects.get(notification_id=1000000602)
            self.assertTrue(notification.process_for_timerboard())
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(timer.timer_type, Timer.TYPE_FINAL)
            self.assertEqual(
                timer.eve_solar_system, EveSolarSystem2.objects.get(id=30002537)
            )
            self.assertEqual(timer.structure_type, EveType2.objects.get(id=2233))
            self.assertEqual(timer.location_details, "Amamake IV")
            self.assertAlmostEqual(
                timer.date,
                pytz.utc.localize(dt.datetime(2019, 10, 13, 20, 32, 27)),
                delta=dt.timedelta(seconds=120),
            )
            self.assertEqual(
                timer.eve_corporation,
                EveCorporationInfo.objects.get(corporation_id=2001),
            )
            self.assertEqual(
                timer.eve_alliance, EveAllianceInfo.objects.get(alliance_id=3001)
            )
            self.assertEqual(timer.visibility, Timer.VISIBILITY_UNRESTRICTED)
            self.assertEqual(timer.owner_name, "Wayne Technologies")
            self.assertTrue(timer.details_notes)

        def test_timer_moon_extraction(self):
            notification = Notification.objects.get(notification_id=1000000404)
            self.assertTrue(notification.process_for_timerboard())
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(timer.timer_type, Timer.TYPE_MOONMINING)
            self.assertEqual(
                timer.eve_solar_system, EveSolarSystem2.objects.get(id=30002537)
            )
            self.assertEqual(timer.structure_type, EveType2.objects.get(id=35835))
            self.assertEqual(
                timer.eve_corporation,
                EveCorporationInfo.objects.get(corporation_id=2001),
            )
            self.assertEqual(
                timer.eve_alliance, EveAllianceInfo.objects.get(alliance_id=3001)
            )
            self.assertEqual(timer.visibility, Timer.VISIBILITY_UNRESTRICTED)
            self.assertEqual(timer.location_details, "Amamake II - Moon 1")
            self.assertEqual(timer.owner_name, "Wayne Technologies")
            self.assertEqual(timer.structure_name, "Dummy")
            self.assertTrue(timer.details_notes)

        def test_anchoring_timer_not_created_for_null_sec(self):
            obj = Notification.objects.get(notification_id=1000010501)
            self.assertFalse(obj.process_for_timerboard())
            self.assertIsNone(Timer.objects.first())

        def test_can_delete_extraction_timer(self):
            # create timer
            obj = Notification.objects.get(notification_id=1000000404)
            self.assertTrue(obj.process_for_timerboard())
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)

            # delete timer
            obj = Notification.objects.get(notification_id=1000000402)
            self.assertFalse(obj.process_for_timerboard())
            self.assertFalse(Timer.objects.filter(pk=timer.pk).exists())


class TestNotificationType(NoSocketsTestCase):
    def test_should_return_enabled_values_only(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICIATIONS", False):
            values = NotificationType.values_enabled
        # then
        self.assertNotIn(NotificationType.STRUCTURE_REFUELED_EXTRA, values)
        self.assertNotIn(NotificationType.TOWER_REFUELED_EXTRA, values)

    def test_should_return_all_values(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICIATIONS", True):
            values = NotificationType.values_enabled
        # then
        self.assertIn(NotificationType.STRUCTURE_REFUELED_EXTRA, values)
        self.assertIn(NotificationType.TOWER_REFUELED_EXTRA, values)

    def test_should_return_enabled_choices_only(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICIATIONS", False):
            choices = NotificationType.choices_enabled
        # then
        types = {choice[0] for choice in choices}
        self.assertNotIn(NotificationType.STRUCTURE_REFUELED_EXTRA, types)
        self.assertNotIn(NotificationType.TOWER_REFUELED_EXTRA, types)

    def test_should_return_all_choices(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICIATIONS", True):
            choices = NotificationType.choices_enabled
        # then
        types = {choice[0] for choice in choices}
        self.assertIn(NotificationType.STRUCTURE_REFUELED_EXTRA, types)
        self.assertIn(NotificationType.TOWER_REFUELED_EXTRA, types)

    def test_has_correct_esi_values(self):
        # given
        esi_valid_notification_types = {
            "AcceptedAlly",
            "AcceptedSurrender",
            "AgentRetiredTrigravian",
            "AllAnchoringMsg",
            "AllMaintenanceBillMsg",
            "AllStrucInvulnerableMsg",
            "AllStructVulnerableMsg",
            "AllWarCorpJoinedAllianceMsg",
            "AllWarDeclaredMsg",
            "AllWarInvalidatedMsg",
            "AllWarRetractedMsg",
            "AllWarSurrenderMsg",
            "AllianceCapitalChanged",
            "AllianceWarDeclaredV2",
            "AllyContractCancelled",
            "AllyJoinedWarAggressorMsg",
            "AllyJoinedWarAllyMsg",
            "AllyJoinedWarDefenderMsg",
            "BattlePunishFriendlyFire",
            "BillOutOfMoneyMsg",
            "BillPaidCorpAllMsg",
            "BountyClaimMsg",
            "BountyESSShared",
            "BountyESSTaken",
            "BountyPlacedAlliance",
            "BountyPlacedChar",
            "BountyPlacedCorp",
            "BountyYourBountyClaimed",
            "BuddyConnectContactAdd",
            "CharAppAcceptMsg",
            "CharAppRejectMsg",
            "CharAppWithdrawMsg",
            "CharLeftCorpMsg",
            "CharMedalMsg",
            "CharTerminationMsg",
            "CloneActivationMsg",
            "CloneActivationMsg2",
            "CloneMovedMsg",
            "CloneRevokedMsg1",
            "CloneRevokedMsg2",
            "CombatOperationFinished",
            "ContactAdd",
            "ContactEdit",
            "ContainerPasswordMsg",
            "ContractRegionChangedToPochven",
            "CorpAllBillMsg",
            "CorpAppAcceptMsg",
            "CorpAppInvitedMsg",
            "CorpAppNewMsg",
            "CorpAppRejectCustomMsg",
            "CorpAppRejectMsg",
            "CorpBecameWarEligible",
            "CorpDividendMsg",
            "CorpFriendlyFireDisableTimerCompleted",
            "CorpFriendlyFireDisableTimerStarted",
            "CorpFriendlyFireEnableTimerCompleted",
            "CorpFriendlyFireEnableTimerStarted",
            "CorpKicked",
            "CorpLiquidationMsg",
            "CorpNewCEOMsg",
            "CorpNewsMsg",
            "CorpNoLongerWarEligible",
            "CorpOfficeExpirationMsg",
            "CorpStructLostMsg",
            "CorpTaxChangeMsg",
            "CorpVoteCEORevokedMsg",
            "CorpVoteMsg",
            "CorpWarDeclaredMsg",
            "CorpWarDeclaredV2",
            "CorpWarFightingLegalMsg",
            "CorpWarInvalidatedMsg",
            "CorpWarRetractedMsg",
            "CorpWarSurrenderMsg",
            "CustomsMsg",
            "DeclareWar",
            "DistrictAttacked",
            "DustAppAcceptedMsg",
            "ESSMainBankLink",
            "EntosisCaptureStarted",
            "ExpertSystemExpired",
            "ExpertSystemExpiryImminent",
            "FWAllianceKickMsg",
            "FWAllianceWarningMsg",
            "FWCharKickMsg",
            "FWCharRankGainMsg",
            "FWCharRankLossMsg",
            "FWCharWarningMsg",
            "FWCorpJoinMsg",
            "FWCorpKickMsg",
            "FWCorpLeaveMsg",
            "FWCorpWarningMsg",
            "FacWarCorpJoinRequestMsg",
            "FacWarCorpJoinWithdrawMsg",
            "FacWarCorpLeaveRequestMsg",
            "FacWarCorpLeaveWithdrawMsg",
            "FacWarLPDisqualifiedEvent",
            "FacWarLPDisqualifiedKill",
            "FacWarLPPayoutEvent",
            "FacWarLPPayoutKill",
            "GameTimeAdded",
            "GameTimeReceived",
            "GameTimeSent",
            "GiftReceived",
            "IHubDestroyedByBillFailure",
            "IncursionCompletedMsg",
            "IndustryOperationFinished",
            "IndustryTeamAuctionLost",
            "IndustryTeamAuctionWon",
            "InfrastructureHubBillAboutToExpire",
            "InsuranceExpirationMsg",
            "InsuranceFirstShipMsg",
            "InsuranceInvalidatedMsg",
            "InsuranceIssuedMsg",
            "InsurancePayoutMsg",
            "InvasionCompletedMsg",
            "InvasionSystemLogin",
            "InvasionSystemStart",
            "JumpCloneDeletedMsg1",
            "JumpCloneDeletedMsg2",
            "KillReportFinalBlow",
            "KillReportVictim",
            "KillRightAvailable",
            "KillRightAvailableOpen",
            "KillRightEarned",
            "KillRightUnavailable",
            "KillRightUnavailableOpen",
            "KillRightUsed",
            "LocateCharMsg",
            "MadeWarMutual",
            "MercOfferRetractedMsg",
            "MercOfferedNegotiationMsg",
            "MissionCanceledTriglavian",
            "MissionOfferExpirationMsg",
            "MissionTimeoutMsg",
            "MoonminingAutomaticFracture",
            "MoonminingExtractionCancelled",
            "MoonminingExtractionFinished",
            "MoonminingExtractionStarted",
            "MoonminingLaserFired",
            "MutualWarExpired",
            "MutualWarInviteAccepted",
            "MutualWarInviteRejected",
            "MutualWarInviteSent",
            "NPCStandingsGained",
            "NPCStandingsLost",
            "OfferToAllyRetracted",
            "OfferedSurrender",
            "OfferedToAlly",
            "OfficeLeaseCanceledInsufficientStandings",
            "OldLscMessages",
            "OperationFinished",
            "OrbitalAttacked",
            "OrbitalReinforced",
            "OwnershipTransferred",
            "RaffleCreated",
            "RaffleExpired",
            "RaffleFinished",
            "ReimbursementMsg",
            "ResearchMissionAvailableMsg",
            "RetractsWar",
            "SeasonalChallengeCompleted",
            "SovAllClaimAquiredMsg",
            "SovAllClaimLostMsg",
            "SovCommandNodeEventStarted",
            "SovCorpBillLateMsg",
            "SovCorpClaimFailMsg",
            "SovDisruptorMsg",
            "SovStationEnteredFreeport",
            "SovStructureDestroyed",
            "SovStructureReinforced",
            "SovStructureSelfDestructCancel",
            "SovStructureSelfDestructFinished",
            "SovStructureSelfDestructRequested",
            "SovereigntyIHDamageMsg",
            "SovereigntySBUDamageMsg",
            "SovereigntyTCUDamageMsg",
            "StationAggressionMsg1",
            "StationAggressionMsg2",
            "StationConquerMsg",
            "StationServiceDisabled",
            "StationServiceEnabled",
            "StationStateChangeMsg",
            "StoryLineMissionAvailableMsg",
            "StructureAnchoring",
            "StructureCourierContractChanged",
            "StructureDestroyed",
            "StructureFuelAlert",
            "StructureImpendingAbandonmentAssetsAtRisk",
            "StructureItemsDelivered",
            "StructureItemsMovedToSafety",
            "StructureLostArmor",
            "StructureLostShields",
            "StructureOnline",
            "StructureServicesOffline",
            "StructureUnanchoring",
            "StructureUnderAttack",
            "StructureWentHighPower",
            "StructureWentLowPower",
            "StructuresJobsCancelled",
            "StructuresJobsPaused",
            "StructuresReinforcementChanged",
            "TowerAlertMsg",
            "TowerResourceAlertMsg",
            "TransactionReversalMsg",
            "TutorialMsg",
            "WarAdopted",
            "WarAllyInherited",
            "WarAllyOfferDeclinedMsg",
            "WarConcordInvalidates",
            "WarDeclared",
            "WarEndedHqSecurityDrop",
            "WarHQRemovedFromSpace",
            "WarInherited",
            "WarInvalid",
            "WarRetracted",
            "WarRetractedByConcord",
            "WarSurrenderDeclinedMsg",
            "WarSurrenderOfferMsg",
        }
        # when
        for ntype in NotificationType.esi_notifications:
            with self.subTest(notification_type=ntype):
                self.assertIn(ntype, esi_valid_notification_types)


class TestWebhook(NoSocketsTestCase):
    pass
