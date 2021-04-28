from django.test import TestCase
from eveuniverse.models import EveType as EveUniverseType
from eveuniverse.tools.testdata import ModelSpec, create_testdata

from ...models.eveuniverse import EveCategory, EveGroup, EveType
from . import test_data_filename


class CreateEveUniverseTestData(TestCase):
    def test_create_testdata(self):
        testdata_spec = [
            ModelSpec(
                "EveCategory",
                ids=[EveCategory.EVE_CATEGORY_ID_STRUCTURE],
                include_children=True,
                enabled_sections=[EveUniverseType.Section.DOGMAS],
            ),
            ModelSpec(
                "EveGroup",
                ids=[EveGroup.EVE_GROUP_ID_CONTROL_TOWER],
                include_children=True,
                enabled_sections=[EveUniverseType.Section.DOGMAS],
            ),
            ModelSpec(
                "EveType",
                ids=[
                    EveType.EVE_TYPE_ID_TCU,
                    EveType.EVE_TYPE_ID_IHUB,
                    EveType.EVE_TYPE_ID_POCO,
                ],
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
                ids=[40161465],
                include_children=False,
            ),
        ]
        create_testdata(testdata_spec, test_data_filename())
