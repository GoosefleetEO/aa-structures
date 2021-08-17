import datetime as dt

from django.test import TestCase
from django.utils.timezone import now

from ..helpers.general import datetime_almost_equal


class TestDatetimeAlmostEqual(TestCase):
    def test_should_return_true(self):
        # given
        d1 = now() + dt.timedelta(hours=0, minutes=55)
        d2 = now() + dt.timedelta(hours=1, minutes=5)
        # when / then
        self.assertTrue(datetime_almost_equal(d1, d2, 3600))
        self.assertTrue(datetime_almost_equal(d2, d1, 3600))
        self.assertFalse(datetime_almost_equal(d2, d1, 60))
        self.assertFalse(datetime_almost_equal(d1, d2, 60))

    def test_should_return_false(self):
        # given
        d1 = now() + dt.timedelta(hours=0, minutes=55)
        d2 = now() + dt.timedelta(hours=1, minutes=5)
        # when / then
        self.assertFalse(datetime_almost_equal(d2, d1, 60))
        self.assertFalse(datetime_almost_equal(d1, d2, 60))

    def test_should_return_false_for_none_dates(self):
        # given
        d1 = now() + dt.timedelta(hours=0, minutes=55)
        # when / then
        self.assertFalse(datetime_almost_equal(d1, None, 3600))
        self.assertFalse(datetime_almost_equal(None, d1, 3600))
