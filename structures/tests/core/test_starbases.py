from eveuniverse.models import EveType

from app_utils.testing import NoSocketsTestCase

from ...core import starbases
from ..testdata.load_eveuniverse import load_eveuniverse


class TestStarbases(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
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
        self.assertEqual(starbases.fuel_per_hour(obj), 40)

        # medium
        obj = EveType.objects.get(id=20061)
        self.assertEqual(starbases.fuel_per_hour(obj), 20)

        # small
        obj = EveType.objects.get(id=20062)
        self.assertEqual(starbases.fuel_per_hour(obj), 10)

        # none
        obj = EveType.objects.get(id=35832)
        self.assertIsNone(starbases.fuel_per_hour(obj))

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


class TestStarbasesFuelDuration(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_can_calculate_for_large_tower(self):
        # given
        large_tower_type = EveType.objects.get(name="Caldari Control Tower")
        # when
        result = starbases.fuel_duration(
            starbase_type=large_tower_type, fuel_quantity=80
        )
        # then
        self.assertEqual(result, 7200)

    def test_can_calculate_for_large_tower_with_sov(self):
        # given
        large_tower_type = EveType.objects.get(name="Caldari Control Tower")
        # when
        result = starbases.fuel_duration(
            starbase_type=large_tower_type, fuel_quantity=80, has_sov=True
        )
        # then
        self.assertEqual(result, 9600)

    def test_can_raise_error_when_not_starbase_type(self):
        # given
        astrahus_type = EveType.objects.get(name="Astrahus")
        # when
        with self.assertRaises(ValueError):
            starbases.fuel_duration(starbase_type=astrahus_type, fuel_quantity=80)
