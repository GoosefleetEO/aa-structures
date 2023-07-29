import datetime as dt

from django.test import TestCase

from structures.core.notification_embeds import helpers


class TestTimeuntil(TestCase):
    def test_should_return_time(self):
        # given
        to_date = dt.datetime(2023, 7, 29, 12, 00, tzinfo=dt.timezone.utc)
        from_date = dt.datetime(2023, 7, 28, 11, 00, tzinfo=dt.timezone.utc)
        # when
        result = helpers.timeuntil(to_date=to_date, from_date=from_date)
        # then
        self.assertEqual("a day from now", result)
