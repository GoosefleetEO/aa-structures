from app_utils.django import app_labels

if "structuretimers" in app_labels():
    import datetime as dt
    from unittest.mock import Mock, patch

    import pytz
    from structuretimers.models import Timer

    from django.utils.timezone import now
    from eveuniverse.models import EveSolarSystem, EveType

    from allianceauth.eveonline.models import EveAllianceInfo, EveCorporationInfo
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
    @patch(MODULE_PATH + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", True)
    class TestTimersForStructureTimers(NoSocketsTestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            load_eveuniverse()
            create_structures()

        def setUp(self) -> None:
            _, self.owner = set_owner_character(character_id=1001)
            load_notification_entities(self.owner)
            self.owner.webhooks.add(create_webhook())

        def test_should_create_timer_for_reinforced_structure(self):
            # given
            notif = Notification.objects.get(notification_id=1000000505)
            # when
            result = notification_timers.add_or_remove_timer(notif)
            # then
            self.assertTrue(result)
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(
                timer.eve_solar_system, EveSolarSystem.objects.get(id=30002537)
            )
            self.assertEqual(timer.structure_type, EveType.objects.get(id=35832))
            self.assertEqual(timer.timer_type, Timer.Type.ARMOR)
            self.assertEqual(timer.objective, Timer.Objective.FRIENDLY)
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
            self.assertEqual(timer.visibility, Timer.Visibility.UNRESTRICTED)
            self.assertEqual(timer.structure_name, "Test Structure Alpha")
            self.assertEqual(timer.owner_name, "Wayne Technologies")
            self.assertTrue(timer.details_notes)
            notif.refresh_from_db()
            self.assertTrue(notif.is_timer_added)

        def test_should_create_timer_for_sov_reinforcement(self):
            # given
            notif = Notification.objects.get(notification_id=1000000804)
            self.owner.is_alliance_main = True
            self.owner.save()
            notif.owner.refresh_from_db()
            # when
            result = notification_timers.add_or_remove_timer(notif)
            # then
            self.assertTrue(result)
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(timer.timer_type, Timer.Type.FINAL)
            self.assertEqual(
                timer.eve_solar_system, EveSolarSystem.objects.get(id=30000474)
            )
            self.assertEqual(timer.structure_type, EveType.objects.get(id=32226))
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
            self.assertEqual(timer.visibility, Timer.Visibility.UNRESTRICTED)
            self.assertEqual(timer.owner_name, "Wayne Enterprises")
            self.assertTrue(timer.details_notes)
            notif.refresh_from_db()
            self.assertTrue(notif.is_timer_added)

        def test_should_create_timer_for_sov_reinforcement_2(self):
            # given
            notif = Notification.objects.get(notification_id=1000000804)
            self.owner.is_alliance_main = False
            self.owner.save()
            notif.owner.refresh_from_db()
            # when
            result = notification_timers.add_or_remove_timer(notif)
            # then
            self.assertFalse(result)
            self.assertFalse(Timer.objects.exists())
            notif.refresh_from_db()
            self.assertFalse(notif.is_timer_added)

        def test_should_create_timer_for_orbital_reinforcements(self):
            # given
            notif = Notification.objects.get(notification_id=1000000602)
            # when
            result = notification_timers.add_or_remove_timer(notif)
            # then
            self.assertTrue(result)
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(timer.timer_type, Timer.Type.FINAL)
            self.assertEqual(
                timer.eve_solar_system, EveSolarSystem.objects.get(id=30002537)
            )
            self.assertEqual(timer.structure_type, EveType.objects.get(id=2233))
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
            self.assertEqual(timer.visibility, Timer.Visibility.UNRESTRICTED)
            self.assertEqual(timer.owner_name, "Wayne Technologies")
            self.assertTrue(timer.details_notes)
            notif.refresh_from_db()
            self.assertTrue(notif.is_timer_added)

        def test_should_create_timer_for_moon_extraction(self):
            # given
            notif = Notification.objects.get(notification_id=1000000404)
            # when
            result = notification_timers.add_or_remove_timer(notif)
            # then
            self.assertTrue(result)
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(timer.timer_type, Timer.Type.MOONMINING)
            self.assertEqual(
                timer.eve_solar_system, EveSolarSystem.objects.get(id=30002537)
            )
            self.assertEqual(timer.structure_type, EveType.objects.get(id=35835))
            self.assertEqual(
                timer.eve_corporation,
                EveCorporationInfo.objects.get(corporation_id=2001),
            )
            self.assertEqual(
                timer.eve_alliance, EveAllianceInfo.objects.get(alliance_id=3001)
            )
            self.assertEqual(timer.visibility, Timer.Visibility.UNRESTRICTED)
            self.assertEqual(timer.location_details, "Amamake II - Moon 1")
            self.assertEqual(timer.owner_name, "Wayne Technologies")
            self.assertEqual(timer.structure_name, "Dummy")
            self.assertTrue(timer.details_notes)
            notif.refresh_from_db()
            self.assertTrue(notif.is_timer_added)

        def test_raise_error_for_unsupported_types(self):
            notif = Notification.objects.get(notification_id=1000010501)
            # when
            with self.assertRaises(NotImplementedError):
                notification_timers.add_or_remove_timer(notif)

        def test_can_delete_extraction_timer(self):
            # create timer
            notif = Notification.objects.get(notification_id=1000000404)
            self.assertTrue(notification_timers.add_or_remove_timer(notif))
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            notif.refresh_from_db()
            self.assertTrue(notif.is_timer_added)

            # delete timer
            notif = Notification.objects.get(notification_id=1000000402)
            self.assertTrue(notification_timers.add_or_remove_timer(notif))
            self.assertFalse(Timer.objects.filter(pk=timer.pk).exists())
            notif.refresh_from_db()
            self.assertTrue(notif.is_timer_added)

        def test_should_create_timer_for_starbase_reinforcement(self):
            # given
            notif = GeneratedNotificationFactory()
            structure = notif.structures.first()
            # when
            result = notification_timers.add_or_remove_timer(notif)
            # then
            self.assertTrue(result)
            obj = Timer.objects.first()
            self.assertEqual(
                obj.eve_solar_system,
                EveSolarSystem.objects.get(id=structure.eve_solar_system.id),
            )
            self.assertEqual(
                obj.structure_type, EveType.objects.get(id=structure.eve_type.id)
            )
            self.assertEqual(obj.timer_type, Timer.Type.FINAL)
            self.assertEqual(obj.objective, Timer.Objective.FRIENDLY)
            self.assertAlmostEqual(obj.date, structure.state_timer_end)
            self.assertEqual(obj.eve_corporation, structure.owner.corporation)
            self.assertEqual(obj.visibility, Timer.Visibility.UNRESTRICTED)
            self.assertEqual(obj.structure_name, structure.name)
            self.assertEqual(
                obj.owner_name, structure.owner.corporation.corporation_name
            )
            self.assertTrue(obj.details_notes)
            notif.refresh_from_db()
            self.assertTrue(notif.is_timer_added)
