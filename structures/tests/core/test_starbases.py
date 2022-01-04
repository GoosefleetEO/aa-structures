from app_utils.testing import NoSocketsTestCase

from ...core import starbases
from ...models import EveCategory, EveGroup, EveType
from ..testdata import load_entities


class TestStarbases(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([EveCategory, EveGroup, EveType])
        cls.type_astrahus = EveType.objects.get(id=35832)
        cls.type_poco = EveType.objects.get(id=2233)
        cls.type_starbase = EveType.objects.get(id=16213)

    def test_is_starbase(self):
        self.assertFalse(starbases.is_starbase(self.type_astrahus))
        self.assertFalse(starbases.is_starbase(self.type_poco))
        self.assertTrue(starbases.is_starbase(self.type_starbase))

    def test_starbase_fuel_consumption_per_hour(self):
        # large
        obj = EveType.objects.get(id=16213)
        self.assertEqual(starbases.starbase_fuel_per_hour(obj), 40)

        # medium
        obj = EveType.objects.get(id=20061)
        self.assertEqual(starbases.starbase_fuel_per_hour(obj), 20)

        # small
        obj = EveType.objects.get(id=20062)
        self.assertEqual(starbases.starbase_fuel_per_hour(obj), 10)

        # none
        obj = EveType.objects.get(id=35832)
        self.assertIsNone(starbases.starbase_fuel_per_hour(obj))

    def test_returns_large_for_large_control_tower(self):
        obj = EveType.objects.get(id=16213)
        expected = starbases.StarbaseSize.LARGE
        self.assertEqual(starbases.starbase_size(obj), expected)

    def test_returns_medium_for_medium_control_tower(self):
        obj = EveType.objects.get(id=20061)
        expected = starbases.StarbaseSize.MEDIUM
        self.assertEqual(starbases.starbase_size(obj), expected)

    def test_returns_small_for_small_control_tower(self):
        obj = EveType.objects.get(id=20062)
        expected = starbases.StarbaseSize.SMALL
        self.assertEqual(starbases.starbase_size(obj), expected)

    def test_returns_none_for_non_control_towers(self):
        obj = EveType.objects.get(id=35832)
        self.assertIsNone(starbases.starbase_size(obj))

    def test_is_fuel_block(self):
        obj = EveType.objects.get(id=16213)
        self.assertFalse(starbases.is_fuel_block(obj))

        obj = EveType.objects.get(id=4051)
        self.assertTrue(starbases.is_fuel_block(obj))
