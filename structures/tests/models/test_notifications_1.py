import datetime as dt
from unittest.mock import patch

from django.utils.timezone import now
from eveuniverse.models import EveEntity

from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from ...models import Notification, NotificationType, Structure, Webhook
from ..testdata.factories import (
    create_notification,
    create_owner_from_user,
    create_upwell_structure,
    create_webhook,
)
from ..testdata.helpers import (
    create_structures,
    load_entities,
    load_notification_entities,
    set_owner_character,
)
from ..testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "structures.models.notifications"


class TestNotification(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)
        cls.owner.webhooks.add(create_webhook())

    def test_str(self):
        obj = Notification.objects.get(notification_id=1000000403)
        self.assertEqual(str(obj), "1000000403:MoonminingExtractionFinished")

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
        parsed_text = obj.parsed_text()
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
        load_eveuniverse()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)

    def test_should_not_filter_non_alliance_notifications_1(self):
        # given
        self.owner.is_alliance_main = False
        self.owner.save()
        notifs = self.owner.notification_set.exclude(
            notif_type__in=NotificationType.relevant_for_alliance_level
        )
        # when/then
        for notif in notifs:
            with self.subTest(notif=str(notif)):
                self.assertFalse(notif.filter_for_alliance_level())

    def test_should_not_filter_non_alliance_notifications_2(self):
        # given
        self.owner.is_alliance_main = True
        self.owner.save()
        notifs = self.owner.notification_set.exclude(
            notif_type__in=NotificationType.relevant_for_alliance_level
        )
        # when/then
        for notif in notifs:
            with self.subTest(notif=str(notif)):
                self.assertFalse(notif.filter_for_alliance_level())

    def test_should_filter_alliance_notifications(self):
        # given
        self.owner.is_alliance_main = False
        self.owner.save()
        notifs = self.owner.notification_set.filter(
            notif_type__in=NotificationType.relevant_for_alliance_level
        )
        # when/then
        for notif in notifs:
            with self.subTest(notif=str(notif)):
                self.assertTrue(notif.filter_for_alliance_level())

    def test_should_not_filter_alliance_notifications_1(self):
        # given
        self.owner.is_alliance_main = True
        self.owner.save()
        notifs = self.owner.notification_set.filter(
            notif_type__in=NotificationType.relevant_for_alliance_level
        )
        # when/then
        for notif in notifs:
            with self.subTest(notif=str(notif)):
                self.assertFalse(notif.filter_for_alliance_level())

    def test_should_not_filter_alliance_notifications_2(self):
        # given
        self.owner.is_alliance_main = True
        self.owner.save()
        notifs = self.owner.notification_set.filter(
            notif_type__in=NotificationType.relevant_for_alliance_level
        )
        # when/then
        for notif in notifs:
            with self.subTest(notif=str(notif)):
                self.assertFalse(notif.filter_for_alliance_level())

    def test_should_not_filter_alliance_notifications_3(self):
        # given
        _, owner = set_owner_character(character_id=1102)  # corp with no alliance
        load_notification_entities(owner)
        notifs = self.owner.notification_set.filter(
            notif_type__in=NotificationType.relevant_for_alliance_level
        )
        # when/then
        for notif in notifs:
            with self.subTest(notif=str(notif)):
                self.assertFalse(notif.filter_for_alliance_level())


class TestNotificationCreateFromStructure(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
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
        self.assertTrue(notif.is_temporary)
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
        self.assertTrue(notif.is_temporary)
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


class TestNotificationRelevantWebhooks(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        user, _ = create_user_from_evecharacter(
            1001, permissions=["structures.add_structure_owner"]
        )
        cls.owner = create_owner_from_user(user=user)
        Webhook.objects.all().delete()

    def test_should_return_owner_webhooks_for_non_structure_notif(self):
        # given
        webhook = create_webhook(
            notification_types=[NotificationType.CHAR_APP_ACCEPT_MSG]
        )
        self.owner.webhooks.add(webhook)
        notif = create_notification(
            owner=self.owner, notif_type=NotificationType.CHAR_APP_ACCEPT_MSG
        )
        # when
        result_qs = notif.relevant_webhooks()
        # then
        self.assertQuerysetEqual(result_qs, Webhook.objects.filter(pk=webhook.pk))

    def test_should_return_no_webhooks(self):
        # given
        notif = create_notification(
            owner=self.owner, notif_type=NotificationType.CHAR_APP_ACCEPT_MSG
        )
        # when
        result_qs = notif.relevant_webhooks()
        # then
        self.assertQuerysetEqual(result_qs, Webhook.objects.none())

    def test_should_return_owner_webhooks_for_structure_notif(self):
        # given
        webhook_owner = create_webhook(
            notification_types=[NotificationType.STRUCTURE_UNDER_ATTACK]
        )
        self.owner.webhooks.add(webhook_owner)
        structure = create_upwell_structure(owner=self.owner)
        notif = create_notification(
            owner=self.owner,
            notif_type=NotificationType.STRUCTURE_UNDER_ATTACK,
            text=f"allianceID: 3011\nallianceLinkData:\n- showinfo\n- 16159\n- 3011\nallianceName: Big Bad Alliance\narmorPercentage: 98.65129050962584\ncharID: 1011\ncorpLinkData:\n- showinfo\n- 2\n- 2011\ncorpName: Bad Company\nhullPercentage: 100.0\nshieldPercentage: 4.704536686417284e-14\nsolarsystemID: {structure.eve_solar_system_id}\nstructureID: &id001 {structure.id}\nstructureShowInfoData:\n- showinfo\n- {structure.eve_type_id}\n- *id001\nstructureTypeID: {structure.eve_type_id}\n",
        )
        # when
        result_qs = notif.relevant_webhooks()
        # then
        self.assertQuerysetEqual(result_qs, Webhook.objects.filter(pk=webhook_owner.pk))

    def test_should_return_structure_webhooks_for_structure_notif(self):
        # given
        webhook_owner = create_webhook(
            notification_types=[NotificationType.STRUCTURE_UNDER_ATTACK]
        )
        self.owner.webhooks.add(webhook_owner)
        structure = create_upwell_structure(owner=self.owner)
        webhook_structure = create_webhook(
            notification_types=[NotificationType.STRUCTURE_UNDER_ATTACK]
        )
        structure.webhooks.add(webhook_structure)
        notif = create_notification(
            owner=self.owner,
            notif_type=NotificationType.STRUCTURE_UNDER_ATTACK,
            text=f"allianceID: 3011\nallianceLinkData:\n- showinfo\n- 16159\n- 3011\nallianceName: Big Bad Alliance\narmorPercentage: 98.65129050962584\ncharID: 1011\ncorpLinkData:\n- showinfo\n- 2\n- 2011\ncorpName: Bad Company\nhullPercentage: 100.0\nshieldPercentage: 4.704536686417284e-14\nsolarsystemID: {structure.eve_solar_system_id}\nstructureID: &id001 {structure.id}\nstructureShowInfoData:\n- showinfo\n- {structure.eve_type_id}\n- *id001\nstructureTypeID: {structure.eve_type_id}\n",
        )
        # when
        result_qs = notif.relevant_webhooks()
        # then
        self.assertQuerysetEqual(
            result_qs, Webhook.objects.filter(pk=webhook_structure.pk)
        )

    def test_should_return_owner_webhooks_when_notif_has_multiple_structures(self):
        # given
        webhook_owner = create_webhook(
            notification_types=[NotificationType.STRUCTURE_UNDER_ATTACK]
        )
        self.owner.webhooks.add(webhook_owner)
        structure_1 = create_upwell_structure(owner=self.owner)
        webhook_structure = create_webhook(
            notification_types=[NotificationType.STRUCTURE_UNDER_ATTACK]
        )
        structure_1.webhooks.add(webhook_structure)
        structure_2 = create_upwell_structure(owner=self.owner)
        webhook_structure = create_webhook(
            notification_types=[NotificationType.STRUCTURE_UNDER_ATTACK]
        )
        structure_2.webhooks.add(webhook_structure)
        notif = create_notification(
            owner=self.owner,
            notif_type=NotificationType.STRUCTURE_UNDER_ATTACK,
            text=f"allStructureInfo:\n- - {structure_1.id}\n  - {structure_1}\n  - 35825\n- - {structure_2.id}\n  - {structure_2}\n  - 35825\nhour: 19\nnumStructures: 1\ntimestamp: 132141703753688216\nweekday: 255\n",
        )
        # when
        result_qs = notif.relevant_webhooks()
        # then
        self.assertQuerysetEqual(result_qs, Webhook.objects.filter(pk=webhook_owner.pk))


class TestNotificationSendToConfiguredWebhooks(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        user, _ = create_user_from_evecharacter(
            1001, permissions=["structures.add_structure_owner"]
        )
        cls.owner = create_owner_from_user(user=user)
        Webhook.objects.all().delete()

    @patch(MODULE_PATH + ".Notification.send_to_webhook")
    def test_should_send_to_webhook(self, mock_send_to_webhook):
        # given
        webhook = create_webhook(
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA]
        )
        self.owner.webhooks.add(webhook)
        notif = create_notification(
            owner=self.owner, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertTrue(result)
        self.assertTrue(mock_send_to_webhook.called)

    @patch(MODULE_PATH + ".Notification.send_to_webhook")
    def test_should_send_to_multiple_webhooks(self, mock_send_to_webhook):
        # given
        webhook_1 = create_webhook(
            notification_types=[
                NotificationType.STRUCTURE_REFUELED_EXTRA,
                NotificationType.STRUCTURE_ANCHORING,
            ]
        )
        webhook_2 = create_webhook(
            notification_types=[
                NotificationType.STRUCTURE_REFUELED_EXTRA,
                NotificationType.STRUCTURE_DESTROYED,
            ]
        )
        self.owner.webhooks.add(webhook_1, webhook_2)
        notif = create_notification(
            owner=self.owner, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertTrue(result)
        self.assertEqual(mock_send_to_webhook.call_count, 2)
        webhook_pks = {call[0][0].pk for call in mock_send_to_webhook.call_args_list}
        self.assertSetEqual(webhook_pks, {webhook_1.pk, webhook_2.pk})

    @patch(MODULE_PATH + ".Notification.send_to_webhook")
    def test_should_not_send_when_webhooks_are_inactive(self, mock_send_to_webhook):
        # given
        webhook = create_webhook(
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA],
            is_active=False,
        )
        self.owner.webhooks.add(webhook)
        notif = create_notification(
            owner=self.owner, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertIsNone(result)
        self.assertFalse(mock_send_to_webhook.called)

    @patch(MODULE_PATH + ".Notification.send_to_webhook")
    def test_should_not_send_when_notif_types_dont_match(self, mock_send_to_webhook):
        # given
        webhook = create_webhook(
            notification_types=[NotificationType.STRUCTURE_UNDER_ATTACK]
        )
        self.owner.webhooks.add(webhook)
        notif = create_notification(
            owner=self.owner, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertIsNone(result)
        self.assertFalse(mock_send_to_webhook.called)

    @patch(MODULE_PATH + ".Notification.send_to_webhook")
    def test_should_return_false_when_sending_failed(self, mock_send_to_webhook):
        # given
        mock_send_to_webhook.return_value = False
        webhook = create_webhook(
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA]
        )
        self.owner.webhooks.add(webhook)
        notif = create_notification(
            owner=self.owner, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertFalse(result)
        self.assertTrue(mock_send_to_webhook.called)

    @patch(MODULE_PATH + ".Notification.send_to_webhook")
    def test_should_send_to_structure_webhook(self, mock_send_to_webhook):
        # given
        webhook_owner = create_webhook(notification_types=[])
        self.owner.webhooks.add(webhook_owner)
        structure = create_upwell_structure(owner=self.owner)
        webhook_structure = create_webhook(
            notification_types=[NotificationType.STRUCTURE_UNDER_ATTACK]
        )
        structure.webhooks.add(webhook_structure)
        notif = create_notification(
            owner=self.owner,
            notif_type=NotificationType.STRUCTURE_UNDER_ATTACK,
            text=f"allianceID: 3011\nallianceLinkData:\n- showinfo\n- 16159\n- 3011\nallianceName: Big Bad Alliance\narmorPercentage: 98.65129050962584\ncharID: 1011\ncorpLinkData:\n- showinfo\n- 2\n- 2011\ncorpName: Bad Company\nhullPercentage: 100.0\nshieldPercentage: 4.704536686417284e-14\nsolarsystemID: {structure.eve_solar_system_id}\nstructureID: &id001 {structure.id}\nstructureShowInfoData:\n- showinfo\n- {structure.eve_type_id}\n- *id001\nstructureTypeID: {structure.eve_type_id}\n",
        )
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertTrue(result)
        self.assertTrue(mock_send_to_webhook.called)


@patch(MODULE_PATH + ".Webhook.send_message")
class TestNotificationSendToWebhook(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        cls.structure = Structure.objects.get(id=1000000000001)
        _, cls.owner = set_owner_character(character_id=1001)
        Webhook.objects.all().delete()

    def test_should_override_ping_type(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        webhook = create_webhook(
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA]
        )
        self.owner.webhooks.add(webhook)
        notif = Notification.create_from_structure(
            self.structure, notif_type=NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        # when
        notif.send_to_configured_webhooks(ping_type_override=Webhook.PingType.HERE)
        # then
        self.assertTrue(mock_send_message.called)
        _, kwargs = mock_send_message.call_args
        self.assertIn("@here", kwargs["content"])

    def test_should_override_color(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        webhook = create_webhook(
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA]
        )
        self.owner.webhooks.add(webhook)
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


@patch(MODULE_PATH + ".Webhook.send_message", spec=True)
class TestNotificationSendMessage(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)
        cls.webhook = create_webhook()
        cls.owner.webhooks.add(cls.webhook)

    def test_can_send_message_normal(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        obj = Notification.objects.get(notification_id=1000020601)
        # when
        result = obj.send_to_webhook(self.webhook)
        # then
        self.assertTrue(result)
        _, kwargs = mock_send_message.call_args
        self.assertIsNotNone(kwargs["content"])
        self.assertIsNotNone(kwargs["embeds"])

    def test_should_ignore_unsupported_notif_types(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
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
        # given
        mock_send_message.return_value = 0
        obj = Notification.objects.get(notification_id=1000020601)
        # when
        obj.send_to_webhook(self.webhook)
        # then
        obj.refresh_from_db()
        self.assertFalse(obj.is_sent)

    def test_send_to_webhook_all_notification_types(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        types_tested = set()
        # when /then
        for notif in Notification.objects.all():
            with self.subTest(notif_type=notif.notif_type):
                if notif.notif_type in NotificationType.values:
                    self.assertFalse(notif.is_sent)
                    self.assertTrue(notif.send_to_webhook(self.webhook))
                    types_tested.add(notif.notif_type)

        # make sure we have tested all existing esi notification types
        self.assertSetEqual(NotificationType.esi_notifications, types_tested)

    def test_should_create_notification_for_structure_refueled(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
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
        mock_send_message.return_value = 1
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
        # given
        mock_send_message.return_value = 1
        Structure.objects.all().delete()
        obj = Notification.objects.get(notification_id=1000000505)
        # when
        obj.send_to_webhook(self.webhook)
        # then
        embed = mock_send_message.call_args[1]["embeds"][0]
        self.assertEqual(
            embed.description[:39], "The Astrahus **(unknown)** in [Amamake]"
        )

    @patch(MODULE_PATH + ".STRUCTURES_DEFAULT_LANGUAGE", "en")
    def test_notification_with_null_aggressor_alliance(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        obj = Notification.objects.get(notification_id=1000020601)
        # when
        result = obj.send_to_webhook(self.webhook)
        # then
        self.assertTrue(result)

    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SET_AVATAR", True)
    def test_can_send_message_with_setting_avatar(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        obj = Notification.objects.get(notification_id=1000020601)
        # when
        result = obj.send_to_webhook(self.webhook)
        # then
        self.assertTrue(result)
        _, kwargs = mock_send_message.call_args
        self.assertIsNotNone(kwargs["avatar_url"])
        self.assertIsNotNone(kwargs["username"])

    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SET_AVATAR", False)
    def test_can_send_message_without_setting_avatar(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        obj = Notification.objects.get(notification_id=1000020601)
        # when
        result = obj.send_to_webhook(self.webhook)
        # then
        self.assertTrue(result)
        _, kwargs = mock_send_message.call_args
        self.assertIsNone(kwargs["avatar_url"])
        self.assertIsNone(kwargs["username"])


@patch(MODULE_PATH + ".Webhook.send_message", spec=True)
class TestNotificationPings(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()

    def setUp(self):
        create_structures(dont_load_entities=True)
        _, self.owner = set_owner_character(character_id=1001)
        load_notification_entities(self.owner)

    def test_can_ping(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        webhook_normal = create_webhook()
        obj = Notification.objects.get(notification_id=1000000509)
        # when
        result = obj.send_to_webhook(webhook_normal)
        # then
        self.assertTrue(result)
        _, kwargs = mock_send_message.call_args
        self.assertIn("@everyone", kwargs["content"])

    def test_can_disable_pinging_webhook(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        webhook_no_pings = create_webhook(has_default_pings_enabled=False)
        obj = Notification.objects.get(notification_id=1000000509)
        # when
        result = obj.send_to_webhook(webhook_no_pings)
        self.assertTrue(result)
        _, kwargs = mock_send_message.call_args
        self.assertNotIn("@everyone", kwargs["content"])

    def test_can_disable_pinging_owner(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        webhook_normal = create_webhook()
        self.owner.webhooks.add(webhook_normal)
        self.owner.has_default_pings_enabled = False
        self.owner.save()
        obj = Notification.objects.get(notification_id=1000000509)
        # when
        result = obj.send_to_webhook(webhook_normal)
        # then
        self.assertTrue(result)
        _, kwargs = mock_send_message.call_args
        self.assertNotIn("@everyone", kwargs["content"])


class TestNotificationType(NoSocketsTestCase):
    def test_should_return_enabled_values_only(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", False):
            values = NotificationType.values_enabled
        # then
        self.assertNotIn(NotificationType.STRUCTURE_REFUELED_EXTRA, values)
        self.assertNotIn(NotificationType.TOWER_REFUELED_EXTRA, values)

    def test_should_return_all_values(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", True):
            values = NotificationType.values_enabled
        # then
        self.assertIn(NotificationType.STRUCTURE_REFUELED_EXTRA, values)
        self.assertIn(NotificationType.TOWER_REFUELED_EXTRA, values)

    def test_should_return_enabled_choices_only(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", False):
            choices = NotificationType.choices_enabled
        # then
        types = {choice[0] for choice in choices}
        self.assertNotIn(NotificationType.STRUCTURE_REFUELED_EXTRA, types)
        self.assertNotIn(NotificationType.TOWER_REFUELED_EXTRA, types)

    def test_should_return_all_choices(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", True):
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
