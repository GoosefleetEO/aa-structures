from eveuniverse.models import EveSolarSystem

from app_utils.testing import NoSocketsTestCase

from structures.models import EveSovereigntyMap, EveSpaceType
from structures.tests.testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "structures.models.eveuniverse"


class TestEveSovereigntyMap(NoSocketsTestCase):
    def test_str(self):
        obj = EveSovereigntyMap(solar_system_id=99)
        expected = "99"
        self.assertEqual(str(obj), expected)

    def test_repr(self):
        obj = EveSovereigntyMap(solar_system_id=99)
        expected = "EveSovereigntyMap(solar_system_id='99')"
        self.assertEqual(repr(obj), expected)


class TestEveSpaceType(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_space_type_highsec(self):
        obj = EveSolarSystem.objects.get(id=30002506)
        expected = EveSpaceType.HIGHSEC
        self.assertEqual(EveSpaceType.from_solar_system(obj), expected)

    def test_space_type_lowsec(self):
        obj = EveSolarSystem.objects.get(id=30002537)
        expected = EveSpaceType.LOWSEC
        self.assertEqual(EveSpaceType.from_solar_system(obj), expected)

    def test_space_type_nullsec(self):
        obj = EveSolarSystem.objects.get(id=30000474)
        expected = EveSpaceType.NULLSEC
        self.assertEqual(EveSpaceType.from_solar_system(obj), expected)

    def test_space_type_wh_space(self):
        obj = EveSolarSystem.objects.get(id=31000005)
        expected = EveSpaceType.W_SPACE
        self.assertEqual(EveSpaceType.from_solar_system(obj), expected)
