import datetime as dt

from django.test import TestCase
from django.utils.timezone import now
from eveuniverse.models import EveType
from eveuniverse.tests.testdata.factories_2 import EveTypeFactory

from structures.helpers import (
    datetime_almost_equal,
    get_or_create_esi_obj,
    hours_until_deadline,
    is_absolute_url,
)


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


class TestHoursUntilDeadline(TestCase):
    def test_should_return_correct_value_for_two_datetimes(self):
        # given
        d1 = now()
        d2 = d1 - dt.timedelta(hours=3)
        # when / then
        self.assertEqual(hours_until_deadline(d1, d2), 3)

    def test_should_return_correct_value_for_one_datetimes(self):
        # given
        d1 = now() + dt.timedelta(hours=3)
        # when / then
        self.assertAlmostEqual(hours_until_deadline(d1), 3, delta=0.1)

    def test_should_raise_error_when_deadline_is_not_a_datetime(self):
        with self.assertRaises(TypeError):
            hours_until_deadline(None)


class TestIsAbsoluteUrl(TestCase):
    def test_should_detect_absolute_urls(self):
        cases = [
            ("https://www.google.com", True),
            ("http://www.google.com", True),
            ("www.google.com", False),
            ("", False),
            ("/abc/x", False),
            (None, False),
        ]
        for url, expected_result in cases:
            with self.subTest(url=url):
                self.assertIs(is_absolute_url(url), expected_result)


class TestGetOrCreateEsiObj(TestCase):
    def test_should_return_existing_obj(self):
        # given
        obj = EveTypeFactory()
        # when
        obj_2 = get_or_create_esi_obj(EveType, id=obj.id)
        # then
        self.assertEqual(obj, obj_2)
