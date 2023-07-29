from app_utils.testing import NoSocketsTestCase

from structures.constants import EveTypeId
from structures.core import sovereignty


class TestSovereignty(NoSocketsTestCase):
    def test_should_return_type_id_or_none(self):
        my_map = [(1, EveTypeId.TCU), (2, EveTypeId.IHUB), (3, None), (0, None)]
        for input, expected in my_map:
            with self.subTest(input=input):
                self.assertEqual(sovereignty.event_type_to_type_id(input), expected)

    def test_should_return_structure_type_names(self):
        my_map = [(1, "TCU"), (2, "I-HUB"), (3, "Other"), (0, "Other")]
        for input, expected in my_map:
            with self.subTest(input=input):
                self.assertEqual(
                    sovereignty.event_type_to_structure_type_name(input), expected
                )
