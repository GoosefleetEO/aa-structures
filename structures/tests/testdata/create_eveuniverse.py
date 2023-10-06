from django.test import TestCase
from eveuniverse.models import EvePlanet, EveSolarSystem, EveType
from eveuniverse.tools.testdata import ModelSpec, create_testdata

from structures.constants import EveCategoryId, EveGroupId, EveTypeId

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
                include_children=True,
                enabled_sections=[
                    EveSolarSystem.Section.PLANETS,
                    EvePlanet.Section.MOONS,
                ],
            ),
            ModelSpec(
                "EveMoon",
                ids=[40161465, 40161466, 40161471, 40029527],
                include_children=False,
            ),
        ]
        create_testdata(testdata_spec, test_data_filename())
