from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

from ..models import (
    EveCategory,
    EveConstellation,
    EveEntity,
    EveGroup,
    EveMoon,
    EvePlanet,
    EveRegion,
    EveSolarSystem,
    EveType,
    Notification,
    Owner,
    Structure,
    StructureService,
    StructureTag,
    Webhook,
)
from .testdata import (
    create_structures,
    esi_mock_client,
    load_entities,
    load_notification_entities,
    set_owner_character,
)

PACKAGE_PATH = "structures.management.commands"


class TestUpdateSde(NoSocketsTestCase):
    @patch(PACKAGE_PATH + ".structures_updatesde.get_input")
    @patch("structures.helpers.esi_fetch._esi_client")
    def test_can_update_all_models(self, mock_esi_client, mock_get_input):
        mock_esi_client.side_effect = esi_mock_client
        mock_get_input.return_value = "Y"
        load_entities()

        eve_category = EveCategory.objects.get(id=65)
        eve_category.name = "Superheros"
        eve_category.save()

        eve_group = EveGroup.objects.get(id=1657)
        eve_group.name = "Fantastic Four"
        eve_group.save()

        eve_type = EveType.objects.get(id=35832)
        eve_type.name = "Batcave"
        eve_type.save()

        eve_region = EveRegion.objects.get(id=10000005)
        eve_region.name = "Toscana"
        eve_region.save()

        eve_constellation = EveConstellation.objects.get(id=20000069)
        eve_constellation.name = "Dark"
        eve_constellation.save()

        eve_moon = EveMoon.objects.get(id=40161465)
        eve_moon.name = "Alpha II - Moon 1"
        eve_moon.save()

        eve_planet = EvePlanet.objects.get(id=40029526)
        eve_planet.name = "Alpha I"
        eve_planet.save()

        eve_solar_system = EveSolarSystem.objects.get(id=30000474)
        eve_solar_system.name = "Alpha"
        eve_solar_system.save()

        out = StringIO()
        call_command("structures_updatesde", stdout=out)

        eve_category.refresh_from_db()
        self.assertEqual(eve_category.name, "Structure")

        eve_group.refresh_from_db()
        self.assertEqual(eve_group.name, "Citadel")

        eve_type.refresh_from_db()
        self.assertEqual(eve_type.name, "Astrahus")

        eve_region.refresh_from_db()
        self.assertEqual(eve_region.name, "Detorid")

        eve_constellation.refresh_from_db()
        self.assertEqual(eve_constellation.name, "1RG-GU")

        eve_moon.refresh_from_db()
        self.assertEqual(eve_moon.name, "Amamake II - Moon 1")

        eve_planet.refresh_from_db()
        self.assertEqual(eve_planet.name, "1-PGSG I")

        eve_solar_system.refresh_from_db()
        self.assertEqual(eve_solar_system.name, "1-PGSG")


class TestPurgeAll(NoSocketsTestCase):
    @patch(PACKAGE_PATH + ".structures_purgeall.get_input")
    def test_can_purge_all_data(self, mock_get_input):
        mock_get_input.return_value = "Y"
        create_structures()
        self.user, self.owner = set_owner_character(character_id=1001)
        self.owner.is_alliance_main = True
        self.owner.save()
        load_notification_entities(self.owner)
        models = [
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveMoon,
            EvePlanet,
            StructureTag,
            StructureService,
            Webhook,
            EveEntity,
            Owner,
            Notification,
            Structure,
        ]
        for MyModel in models:
            self.assertGreater(MyModel.objects.count(), 0)

        out = StringIO()
        call_command("structures_purgeall", stdout=out)

        for MyModel in models:
            self.assertEqual(MyModel.objects.count(), 0)
