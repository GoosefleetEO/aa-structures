from app_utils.django import app_labels

if "timerboard" in app_labels():
    from unittest.mock import Mock, patch

    from allianceauth.timerboard.models import Timer as AuthTimer
    from app_utils.testing import NoSocketsTestCase

    from structures.core import notification_timers
    from structures.models import Notification

    from ..testdata.factories import create_webhook
    from ..testdata.factories_2 import GeneratedNotificationFactory
    from ..testdata.helpers import (
        create_structures,
        load_notification_entities,
        set_owner_character,
    )
    from ..testdata.load_eveuniverse import load_eveuniverse

    MODULE_PATH = "structures.core.notification_timers"

    @patch(
        "structuretimers.models._task_calc_timer_distances_for_all_staging_systems",
        Mock(),
    )
    @patch("structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False)
    class TestNotificationAddToTimerboard(NoSocketsTestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            load_eveuniverse()
            create_structures()
            _, cls.owner = set_owner_character(character_id=1001)
            load_notification_entities(cls.owner)
            cls.owner.webhooks.add(create_webhook())

        @patch(MODULE_PATH + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", False)
        @patch("allianceauth.timerboard.models.Timer", spec=True)
        def test_moon_timers_disabled(self, mock_Timer):
            # given
            notif = Notification.objects.get(notification_id=1000000404)
            # when
            result = notification_timers.add_or_remove_timer(notif)
            # then
            self.assertFalse(result)
            self.assertFalse(mock_Timer.objects.create.called)
            notif.refresh_from_db()
            self.assertFalse(notif.add_or_remove_timer())
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
                self.assertFalse(x.add_or_remove_timer())

            self.assertEqual(AuthTimer.objects.count(), 0)

            x = Notification.objects.get(notification_id=1000000501)
            self.assertFalse(x.add_or_remove_timer())

            x = Notification.objects.get(notification_id=1000000504)
            self.assertTrue(x.add_or_remove_timer())

            x = Notification.objects.get(notification_id=1000000505)
            self.assertTrue(x.add_or_remove_timer())

            x = Notification.objects.get(notification_id=1000000602)
            self.assertTrue(x.add_or_remove_timer())

            ids_set_1 = {x.id for x in AuthTimer.objects.all()}
            x = Notification.objects.get(notification_id=1000000404)
            self.assertTrue(x.add_or_remove_timer())

            self.assertEqual(AuthTimer.objects.count(), 4)

            # this should remove the right timer only
            x = Notification.objects.get(notification_id=1000000402)
            x.add_or_remove_timer()
            self.assertEqual(AuthTimer.objects.count(), 3)
            ids_set_2 = {x.id for x in AuthTimer.objects.all()}
            self.assertSetEqual(ids_set_1, ids_set_2)

        @patch(
            MODULE_PATH + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED",
            True,
        )
        def test_run_all(self):
            for x in Notification.objects.all():
                x.add_or_remove_timer()

        @patch(MODULE_PATH + ".STRUCTURES_TIMERS_ARE_CORP_RESTRICTED", False)
        def test_corp_restriction_1(self):
            # given
            notif = Notification.objects.get(notification_id=1000000504)
            # when
            result = notif.add_or_remove_timer()
            # then
            self.assertTrue(result)
            timer = AuthTimer.objects.first()
            self.assertFalse(timer.corp_timer)

        @patch(MODULE_PATH + ".STRUCTURES_TIMERS_ARE_CORP_RESTRICTED", True)
        def test_corp_restriction_2(self):
            x = Notification.objects.get(notification_id=1000000504)
            self.assertTrue(x.add_or_remove_timer())
            t = AuthTimer.objects.first()
            self.assertTrue(t.corp_timer)

        def test_timer_starbase_reinforcement(self):
            # given
            notif = GeneratedNotificationFactory()
            structure = notif.structures.first()
            # when
            result = notif.add_or_remove_timer()
            # then
            self.assertTrue(result)
            obj = AuthTimer.objects.first()
            self.assertEqual(obj.system, structure.eve_solar_system.name)
            self.assertEqual(obj.planet_moon, structure.eve_moon.name)
            self.assertEqual(obj.eve_time, structure.state_timer_end)
