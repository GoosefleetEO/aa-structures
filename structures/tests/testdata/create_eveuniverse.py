from django.test import TestCase
from eveuniverse.models import EveType as EveUniverseType
from eveuniverse.tools.testdata import ModelSpec, create_testdata

from ...constants import EveCategoryId, EveGroupId, EveTypeId
from . import test_data_filename


class CreateEveUniverseTestData(TestCase):
    def test_create_testdata(self):
        testdata_spec = [
            ModelSpec(
                "EveCategory",
                ids=[EveCategoryId.STRUCTURE],
                include_children=True,
                enabled_sections=[EveUniverseType.Section.DOGMAS],
            ),
            ModelSpec(
                "EveGroup",
                ids=[EveGroupId.CONTROL_TOWER],
                include_children=True,
                enabled_sections=[EveUniverseType.Section.DOGMAS],
            ),
            ModelSpec(
                "EveType",
                ids=[EveTypeId.TCU, EveTypeId.IHUB, EveTypeId.CUSTOMS_OFFICE],
                include_children=True,
                enabled_sections=[EveUniverseType.Section.DOGMAS],
            ),
            ModelSpec(
                "EveSolarSystem",
                ids=[30002537, 30000474],
                include_children=False,
            ),
            ModelSpec(
                "EveMoon",
                ids=[40161465, 40161466],
                include_children=False,
            ),
        ]
        create_testdata(testdata_spec, test_data_filename())
