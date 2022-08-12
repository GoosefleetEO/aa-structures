from app_utils.django import app_labels

if "structuretimers" in app_labels():
    import datetime as dt
    from unittest.mock import Mock, patch

    import pytz
    from structuretimers.models import Timer

    from django.utils.timezone import now
    from eveuniverse.models import EveSolarSystem as EveSolarSystem2
    from eveuniverse.models import EveType as EveType2

    from allianceauth.eveonline.models import EveAllianceInfo, EveCorporationInfo
    from app_utils.testing import NoSocketsTestCase

    from ...models import Notification
    from ..testdata.factories import create_webhook
    from ..testdata.factories_2 import GeneratedNotificationFactory
    from ..testdata.helpers import (
        create_structures,
        load_notification_entities,
        set_owner_character,
    )
    from ..testdata.load_eveuniverse import load_eveuniverse

    MODULE_PATH = "structures.models.notifications"

    @patch(
        "structuretimers.models._task_calc_timer_distances_for_all_staging_systems",
        Mock(),
    )
    @patch("structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False)
    @patch(MODULE_PATH + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", True)
    class TestNotificationAddToStructureTimers(NoSocketsTestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            create_structures()
            load_eveuniverse()

        def setUp(self) -> None:
            _, self.owner = set_owner_character(character_id=1001)
            load_notification_entities(self.owner)
            self.owner.webhooks.add(create_webhook())
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
            self.assertEqual(timer.timer_type, Timer.Type.FINAL)
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
            self.assertEqual(timer.visibility, Timer.Visibility.UNRESTRICTED)
            self.assertEqual(timer.owner_name, "Wayne Enterprises")
            self.assertTrue(timer.details_notes)

        def test_timer_orbital_reinforcements(self):
            notification = Notification.objects.get(notification_id=1000000602)
            self.assertTrue(notification.process_for_timerboard())
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(timer.timer_type, Timer.Type.FINAL)
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
            self.assertEqual(timer.visibility, Timer.Visibility.UNRESTRICTED)
            self.assertEqual(timer.owner_name, "Wayne Technologies")
            self.assertTrue(timer.details_notes)

        def test_timer_moon_extraction(self):
            notification = Notification.objects.get(notification_id=1000000404)
            self.assertTrue(notification.process_for_timerboard())
            timer = Timer.objects.first()
            self.assertIsInstance(timer, Timer)
            self.assertEqual(timer.timer_type, Timer.Type.MOONMINING)
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
            self.assertEqual(timer.visibility, Timer.Visibility.UNRESTRICTED)
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

        def test_timer_starbase_reinforcement(self):
            # given
            notif = GeneratedNotificationFactory()
            structure = notif.structures.first()
            # when
            result = notif.process_for_timerboard()
            # then
            self.assertTrue(result)
            obj = Timer.objects.first()
            self.assertEqual(
                obj.eve_solar_system,
                EveSolarSystem2.objects.get(id=structure.eve_solar_system.id),
            )
            self.assertEqual(
                obj.structure_type, EveType2.objects.get(id=structure.eve_type.id)
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
