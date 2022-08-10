import datetime as dt

from django.utils.timezone import now

from app_utils.testing import NoSocketsTestCase

from ...models import NotificationType, Structure, StructuresNotification
from ..testdata.factories_2 import (
    StarbaseFactory,
    StructureFactory,
    StructuresNotificationFactory,
)
from ..testdata.helpers import load_eveuniverse


class TestStructuresNotification(NoSocketsTestCase):
    def test_should_have_str(self):
        # given
        notif = StructuresNotificationFactory()
        # when/then
        self.assertTrue(str(notif))
        print(notif.owner.webhooks.first())


class TestStructuresNotificationManagerCreatePosReinforced(NoSocketsTestCase):
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
        obj, created = StructuresNotification.objects.get_or_create_pos_reinforced(
            starbase
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
        obj_old = StructuresNotificationFactory(
            owner=starbase.owner,
            notif_type=NotificationType.TOWER_REINFORCED_EXTRA,
            details={"reinforced_until": reinforced_until.isoformat()},
        )
        # when
        obj_new, created = StructuresNotification.objects.get_or_create_pos_reinforced(
            starbase
        )
        # then
        self.assertFalse(created)
        self.assertEqual(obj_old, obj_new)

    def test_should_raise_error_when_no_starbase(self):
        # given
        reinforced_until = now() + dt.timedelta(hours=24)
        starbase = StructureFactory(state_timer_end=reinforced_until)
        # when
        with self.assertRaises(ValueError):
            StructuresNotification.objects.get_or_create_pos_reinforced(starbase)

    def test_should_raise_error_when_not_reinforced(self):
        # given
        starbase = StarbaseFactory()
        # when
        with self.assertRaises(ValueError):
            StructuresNotification.objects.get_or_create_pos_reinforced(starbase)

    def test_should_raise_error_when_reinforcement_timer_missing(self):
        # given
        starbase = StarbaseFactory(state=Structure.State.POS_REINFORCED)
        # when
        with self.assertRaises(ValueError):
            StructuresNotification.objects.get_or_create_pos_reinforced(starbase)
