from django.test import TestCase
from eveuniverse.models import EveType
from eveuniverse.tools.testdata import ModelSpec, create_testdata

from ...constants import EveCategoryId, EveGroupId, EveTypeId
from .helpers import test_data_filename


class CreateEveUniverseTestData(TestCase):
    def test_create_testdata(self):
        testdata_spec = [
            ModelSpec(
                "EveCategory",
                ids=[EveCategoryId.STRUCTURE],
                include_children=True,
                enabled_sections=[EveType.Section.DOGMAS],
            ),
            ModelSpec(
                "EveGroup",
                ids=[EveGroupId.CONTROL_TOWER],
                include_children=True,
                enabled_sections=[EveType.Section.DOGMAS],
            ),
            ModelSpec(
                "EveType",
                ids=[EveTypeId.TCU, EveTypeId.IHUB, EveTypeId.CUSTOMS_OFFICE],
                include_children=True,
                enabled_sections=[EveType.Section.DOGMAS],
            ),
            ModelSpec(
                "EveGroup",
                ids=[
                    EveGroupId.PLANET,
                    EveGroupId.FUEL_BLOCK,
                    EveGroupId.ICE_PRODUCT,
                    EveGroupId.QUANTUM_CORES,
                    EveGroupId.STRUCTURE_CITADEL_SERVICE_MODULE,
                    EveGroupId.UNCOMMON_MOON_ASTEROIDS,
                ],
                include_children=True,
            ),
            ModelSpec("EveType", ids=[], include_children=False),
            ModelSpec(
                "EveSolarSystem",
                ids=[30002506, 31000005, 30002537, 30000474, 30000476],
                include_children=False,
            ),
            ModelSpec(
                "EvePlanet",
                ids=[
                    40161463,
                    40161464,
                    40161467,
                    40161469,
                    40161472,
                    40161476,
                    40029526,
                    40029528,
                    40029529,
                    40029531,
                    40029533,
                    40029537,
                    40029538,
                    40029553,
                    40029572,
                    40029610,
                    40029616,
                ],
                include_children=False,
            ),
            ModelSpec(
                "EveMoon",
                ids=[40161465, 40161466, 40161471, 40029527],
                include_children=False,
            ),
        ]
        create_testdata(testdata_spec, test_data_filename())
