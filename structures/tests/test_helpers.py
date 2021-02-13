from datetime import datetime, timedelta

import pytz
from django.test import TestCase

from ..helpers import eveonline


class TestEveOnline(TestCase):
    def test_ldap_datetime_2_dt(self):
        self.assertEqual(
            eveonline.ldap_datetime_2_dt(131924601300000000),
            pytz.utc.localize(
                datetime(year=2019, month=1, day=20, hour=12, minute=15, second=30)
            ),
        )

    def test_ldap_timedelta_2_timedelta(self):
        expected = timedelta(minutes=15)
        self.assertEqual(eveonline.ldap_timedelta_2_timedelta(9000000000), expected)
