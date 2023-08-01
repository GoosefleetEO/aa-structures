import datetime as dt

from django.test import TestCase
from eveuniverse.models import EveEntity

from structures.core.notification_embeds import helpers
from structures.tests.testdata.factories_2 import EveEntityCharacterFactory


class TestTimeuntil(TestCase):
    def test_should_return_time(self):
        # given
        to_date = dt.datetime(2023, 7, 29, 12, 00, tzinfo=dt.timezone.utc)
        from_date = dt.datetime(2023, 7, 28, 11, 00, tzinfo=dt.timezone.utc)
        # when
        result = helpers.timeuntil(to_date=to_date, from_date=from_date)
        # then
        self.assertEqual("a day from now", result)


class TestGenEveEntityLinkFromId(TestCase):
    def test_should_return_eve_entity(self):
        # given
        obj = EveEntityCharacterFactory()
        # when
        result = helpers.gen_eve_entity_link_from_id(obj.id)
        # then
        self.assertIn(str(obj.id), result)

    def test_should_return_empty_string(self):
        self.assertEqual(helpers.gen_eve_entity_link_from_id(None), "")


class TestGenEveEntityLink(TestCase):
    def test_should_return_eve_entity(self):
        # given
        obj = EveEntityCharacterFactory()
        # when
        result = helpers.gen_eve_entity_link(obj)
        # then
        self.assertIn(str(obj.id), result)

    def test_should_return_empty_string_when_obj_not_valid(self):
        # when
        result = helpers.gen_eve_entity_link(None)
        # then
        self.assertEqual(result, "")

    def test_should_return_empty_string_when_eve_entity_not_supported(self):
        # given
        obj = EveEntity(id=99, name="special", category=EveEntity.CATEGORY_SOLAR_SYSTEM)
        # when
        result = helpers.gen_eve_entity_link(obj)
        # then
        self.assertEqual(result, "")
