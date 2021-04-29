from django.test import TestCase
from eveuniverse.models import EveType as EveUniverseType
from eveuniverse.tools.testdata import ModelSpec, create_testdata

from ... import constants
from . import test_data_filename


class CreateEveUniverseTestData(TestCase):
    def test_create_testdata(self):
        testdata_spec = [
            ModelSpec(
                "EveCategory",
                ids=[constants.EVE_CATEGORY_ID_STRUCTURE],
                include_children=True,
                enabled_sections=[EveUniverseType.Section.DOGMAS],
            ),
            ModelSpec(
                "EveGroup",
                ids=[constants.EVE_GROUP_ID_CONTROL_TOWER],
                include_children=True,
                enabled_sections=[EveUniverseType.Section.DOGMAS],
            ),
            ModelSpec(
                "EveType",
                ids=[
                    constants.EVE_TYPE_ID_TCU,
                    constants.EVE_TYPE_ID_IHUB,
                    constants.EVE_TYPE_ID_POCO,
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
