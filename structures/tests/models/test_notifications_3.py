import datetime as dt
from unittest import mock

from django.utils.timezone import now

from app_utils.testing import NoSocketsTestCase

from structures.models import GeneratedNotification, NotificationType, Structure

from ..testdata.factories_2 import (
    GeneratedNotificationFactory,
    NotificationFactory,
    OwnerFactory,
    StarbaseFactory,
    StructureFactory,
)
from ..testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "structures.models.notifications"


class TestGeneratedNotification(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_have_str(self):
        # given
        notif = GeneratedNotificationFactory()
        # when/then
        self.assertTrue(str(notif))

    def test_should_have_repr(self):
        # given
        notif = GeneratedNotificationFactory()
        # when/then
        self.assertTrue(repr(notif))

    def test_should_send_to_configured_webhooks(self):
        # given
        notif = GeneratedNotificationFactory()
        webhook = notif.owner.webhooks.first()
        webhook.notification_types = [NotificationType.TOWER_REINFORCED_EXTRA]
        webhook.save()
        # when
        result = notif.send_to_configured_webhooks()
        # then
        self.assertTrue(result)


class TestGeneratedNotificationManagerCreatePosReinforced(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_create_new_notif(self):
        # given
        reinforced_until = now() + dt.timedelta(hours=24)
        starbase = StarbaseFactory(
            state=Structure.State.POS_REINFORCED, state_timer_end=reinforced_until
        )
        # when
        obj, created = GeneratedNotification.objects.get_or_create_from_structure(
            structure=starbase, notif_type=NotificationType.TOWER_REINFORCED_EXTRA
        )
        # then
        self.assertTrue(created)
        self.assertEqual(
            dt.datetime.fromisoformat(obj.details["reinforced_until"]), reinforced_until
        )

    def test_should_return_existing_notif(self):
        # given
        reinforced_until = now() + dt.timedelta(hours=24)
        starbase = StarbaseFactory(
            state=Structure.State.POS_REINFORCED, state_timer_end=reinforced_until
        )
        obj_old = GeneratedNotificationFactory(
            owner=starbase.owner,
            notif_type=NotificationType.TOWER_REINFORCED_EXTRA,
            details={"reinforced_until": reinforced_until.isoformat()},
            create_structure=False,
        )
        obj_old.structures.add(starbase)
        # when
        (
            obj_new,
            created,
        ) = GeneratedNotification.objects._get_or_create_tower_reinforced(starbase)
        # then
        self.assertFalse(created)
        self.assertEqual(obj_old, obj_new)

    def test_should_raise_error_when_no_starbase(self):
        # given
        reinforced_until = now() + dt.timedelta(hours=24)
        starbase = StructureFactory(state_timer_end=reinforced_until)
        # when
        with self.assertRaises(ValueError):
            GeneratedNotification.objects._get_or_create_tower_reinforced(starbase)

    def test_should_raise_error_when_not_reinforced(self):
        # given
        starbase = StarbaseFactory()
        # when
        with self.assertRaises(ValueError):
            GeneratedNotification.objects._get_or_create_tower_reinforced(starbase)

    def test_should_raise_error_when_reinforcement_timer_missing(self):
        # given
        starbase = StarbaseFactory(state=Structure.State.POS_REINFORCED)
        # when
        with self.assertRaises(ValueError):
            GeneratedNotification.objects._get_or_create_tower_reinforced(starbase)


@mock.patch("structures.core.notification_timers.add_or_remove_timer")
class TestProcessTimers(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = OwnerFactory()

    @mock.patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", True)
    def test_should_process_timers_for_all_supported_notification_types(
        self, mock_add_or_remove_timer
    ):
        mock_add_or_remove_timer.return_value = True
        for notif_type in [
            NotificationType.STRUCTURE_LOST_SHIELD,
            NotificationType.STRUCTURE_LOST_ARMOR,
            NotificationType.ORBITAL_REINFORCED,
            NotificationType.MOONMINING_EXTRACTION_STARTED,
            NotificationType.MOONMINING_EXTRACTION_CANCELLED,
            NotificationType.SOV_STRUCTURE_REINFORCED,
            NotificationType.TOWER_REINFORCED_EXTRA,
        ]:
            with self.subTest(notif_type=notif_type):
                notif = NotificationFactory(owner=self.owner, notif_type=notif_type)
                self.assertTrue(notif.add_or_remove_timer())

    @mock.patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", True)
    def test_should_not_process_timers_for_non_supported_notification_types(
        self, mock_add_or_remove_timer
    ):
        mock_add_or_remove_timer.return_value = True
        unsupported_notif_types = {
            obj for obj in NotificationType
        } - NotificationType.relevant_for_timerboard
        for notif_type in unsupported_notif_types:
            with self.subTest(notif_type=notif_type):
                notif = NotificationFactory(owner=self.owner, notif_type=notif_type)
                self.assertFalse(notif.add_or_remove_timer())

    def test_should_not_process_timers_when_disabled(self, mock_add_or_remove_timer):
        # given
        mock_add_or_remove_timer.side_effect = RuntimeError
        notif = NotificationFactory(
            owner=self.owner, notif_type=NotificationType.CHAR_APP_ACCEPT_MSG
        )
        # when
        with mock.patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", False):
            result = notif.add_or_remove_timer()
        # then
        self.assertFalse(result)
