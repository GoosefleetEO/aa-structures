import datetime as dt

from django.utils.timezone import now

from app_utils.testing import NoSocketsTestCase

from ...models import GeneratedNotification, NotificationType, Structure
from ..testdata.factories_2 import (
    GeneratedNotificationFactory,
    StarbaseFactory,
    StructureFactory,
)
from ..testdata.helpers import load_eveuniverse


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
            structure=starbase,
            notif_type=NotificationType.TOWER_REINFORCED_EXTRA,
            details={"reinforced_until": reinforced_until.isoformat()},
        )
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
