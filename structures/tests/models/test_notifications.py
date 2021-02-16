from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import re

from requests.exceptions import HTTPError
import pytz

from django.contrib.auth.models import Group
from django.utils.timezone import now

from allianceauth.eveonline.models import EveAllianceInfo, EveCorporationInfo

from ...models import (
    EveEntity,
    Notification,
    NotificationType,
    NotificationGroup,
    Webhook,
    Structure,
)
from ..testdata import (
    load_entities,
    load_notification_entities,
    create_structures,
    set_owner_character,
)
from app_utils.django import app_labels
from app_utils.testing import NoSocketsTestCase

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
            EveEntity.get_matching_entity_category("character"),
            EveEntity.CATEGORY_CHARACTER,
        )
        self.assertEqual(
            EveEntity.get_matching_entity_category("corporation"),
            EveEntity.CATEGORY_CORPORATION,
        )
        self.assertEqual(
            EveEntity.get_matching_entity_category("alliance"),
            EveEntity.CATEGORY_ALLIANCE,
        )
        self.assertEqual(
            EveEntity.get_matching_entity_category("faction"),
            EveEntity.CATEGORY_FACTION,
        )
        self.assertEqual(
            EveEntity.get_matching_entity_category("other"), EveEntity.CATEGORY_OTHER
        )
        self.assertEqual(
            EveEntity.get_matching_entity_category("does not exist"),
            EveEntity.CATEGORY_OTHER,
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

    def test_filter_alliance_level(self):
        # notification is not and owner is not alliance level
        self.owner.is_alliance_main = False
        self.owner.save()
        x1 = Notification.objects.get(notification_id=1000000509)
        self.assertFalse(x1.filter_for_alliance_level())

        # notification is, but owner is not
        self.owner.is_alliance_main = False
        self.owner.save()
        x1 = Notification.objects.get(notification_id=1000000803)
        self.assertTrue(x1.filter_for_alliance_level())

        # notification is and owner is
        self.owner.is_alliance_main = True
        self.owner.save()
        x1 = Notification.objects.get(notification_id=1000000803)
        self.assertFalse(x1.filter_for_alliance_level())

        # notification is not, but owner is
        self.owner.is_alliance_main = True
        self.owner.save()
        x1 = Notification.objects.get(notification_id=1000000509)
        self.assertFalse(x1.filter_for_alliance_level())


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
            if notif.notif_type in NotificationType.ids():
                self.assertFalse(notif.is_sent)
                self.assertTrue(notif.send_to_webhook(self.webhook))
                types_tested.add(notif.notif_type)

        # make sure we have tested all existing notification types
        self.assertSetEqual(set(NotificationType.ids()), types_tested)

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
    def test_anchoring_in_low_sec_has_timer(self, mock_send_message):
        mock_send_message.return_value = True

        obj = Notification.objects.get(notification_id=1000000501)
        obj.send_to_webhook(self.webhook)
        embed = mock_send_message.call_args[1]["embeds"][0]
        self.assertIn("The anchoring timer ends at", embed.description)

    @patch(MODULE_PATH + ".STRUCTURES_DEFAULT_LANGUAGE", "en")
    def test_anchoring_in_null_sec_no_timer(self, mock_send_message):
        mock_send_message.return_value = True

        obj = Notification.objects.get(notification_id=1000010501)
        obj.send_to_webhook(self.webhook)
        embed = mock_send_message.call_args[1]["embeds"][0]
        self.assertNotIn("The anchoring timer ends at", embed.description)

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
            self.assertTrue(x.process_for_timerboard())

            x = Notification.objects.get(notification_id=1000000504)
            self.assertTrue(x.process_for_timerboard())

            x = Notification.objects.get(notification_id=1000000505)
            self.assertTrue(x.process_for_timerboard())

            x = Notification.objects.get(notification_id=1000000602)
            self.assertTrue(x.process_for_timerboard())

            ids_set_1 = {x.id for x in AuthTimer.objects.all()}
            x = Notification.objects.get(notification_id=1000000404)
            self.assertTrue(x.process_for_timerboard())

            self.assertEqual(AuthTimer.objects.count(), 5)

            # this should remove the right timer only
            x = Notification.objects.get(notification_id=1000000402)
            x.process_for_timerboard()
            self.assertEqual(AuthTimer.objects.count(), 4)
            ids_set_2 = {x.id for x in AuthTimer.objects.all()}
            self.assertSetEqual(ids_set_1, ids_set_2)

        @patch(MODULE_PATH + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", True)
        def test_run_all(self):
            for x in Notification.objects.all():
                x.process_for_timerboard()

        @patch(MODULE_PATH + ".STRUCTURES_TIMERS_ARE_CORP_RESTRICTED", False)
        def test_corp_restriction_1(self):
            x = Notification.objects.get(notification_id=1000000504)
            self.assertTrue(x.process_for_timerboard())
            t = AuthTimer.objects.first()
            self.assertFalse(t.corp_timer)

        @patch(MODULE_PATH + ".STRUCTURES_TIMERS_ARE_CORP_RESTRICTED", True)
        def test_corp_restriction_2(self):
            x = Notification.objects.get(notification_id=1000000504)
            self.assertTrue(x.process_for_timerboard())
            t = AuthTimer.objects.first()
            self.assertTrue(t.corp_timer)

        def test_anchoring_timer_created_for_low_sec(self):
            obj = Notification.objects.get(notification_id=1000000501)
            self.assertTrue(obj.process_for_timerboard())
            timer = AuthTimer.objects.first()
            self.assertEqual(timer.eve_time, obj.timestamp + timedelta(hours=24))

        def test_anchoring_timer_not_created_for_null_sec(self):
            obj = Notification.objects.get(notification_id=1000010501)
            self.assertFalse(obj.process_for_timerboard())
            self.assertIsNone(AuthTimer.objects.first())


if "structuretimers" in app_labels():

    from structuretimers.models import Timer
    from eveuniverse.models import (
        EveSolarSystem as EveSolarSystem2,
        EveType as EveType2,
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
                timer.date, now() + timedelta(hours=47), delta=timedelta(hours=1)
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

        def test_timer_structure_anchoring(self):
            notification = Notification.objects.get(notification_id=1000000501)
            self.assertTrue(notification.process_for_timerboard())
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(timer.timer_type, Timer.TYPE_ANCHORING)
            self.assertEqual(
                timer.eve_solar_system, EveSolarSystem2.objects.get(id=30002537)
            )
            self.assertEqual(timer.structure_type, EveType2.objects.get(id=35832))
            self.assertAlmostEqual(
                timer.date, now() + timedelta(hours=22), delta=timedelta(hours=1)
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
                pytz.utc.localize(datetime(2018, 12, 20, 17, 3, 22)),
                delta=timedelta(seconds=120),
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
                pytz.utc.localize(datetime(2019, 10, 13, 20, 32, 27)),
                delta=timedelta(seconds=120),
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
    def test_should_compare_with_id_1(self):
        # given
        x = NotificationType.STRUCTURE_ANCHORING
        # when/then
        self.assertTrue(x == "StructureAnchoring")

    def test_should_compare_with_id_2(self):
        # given
        x = NotificationType.STRUCTURE_ANCHORING
        # when/then
        self.assertFalse(x == "xStructureAnchoring")

    def test_should_return_ids_for_group(self):
        # when
        result = NotificationType.ids_for_group(NotificationGroup.CUSTOMS_OFFICE)
        # then
        self.assertSetEqual(
            set(result),
            {
                NotificationType.ORBITAL_ATTACKED.id,
                NotificationType.ORBITAL_REINFORCED.id,
            },
        )


class TestWebhook(NoSocketsTestCase):
    def test_should_return_notification_type_ids_for_all_groups(self):
        # given
        webhook = Webhook.objects.create(
            name="Test", url="dummy-url", notification_groups=[40, 50]
        )
        # when
        result = webhook.notification_types
        # then
        self.assertSetEqual(
            set(result),
            {
                NotificationType.TOWER_ALERT_MSG.id,
                NotificationType.TOWER_RESOURCE_ALERT_MSG.id,
                NotificationType.ORBITAL_ATTACKED.id,
                NotificationType.ORBITAL_REINFORCED.id,
            },
        )
