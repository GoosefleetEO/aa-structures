"""Command to update planets for all known POCOs."""

from django.core.management.base import BaseCommand
from eveuniverse.models import EveSolarSystem

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from structures import __title__
from structures.constants import EveTypeId
from structures.models import Structure

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class Command(BaseCommand):
    help = "Update planets for all known POCOs."

    def handle(self, *args, **options):
        solar_system_ids = set(
            Structure.objects.filter(eve_type_id=EveTypeId.CUSTOMS_OFFICE).values_list(
                "eve_solar_system_id", flat=True
            )
        )
        self.stdout.write(
            f"Updating planets for {len(solar_system_ids)} solar systems", ending=""
        )
        for solar_system_id in solar_system_ids:
            EveSolarSystem.objects.update_or_create_esi(
                id=solar_system_id,
                include_children=True,
                wait_for_children=True,
                enabled_sections=[EveSolarSystem.Section.PLANETS],
            )
            self.stdout.write(".", ending="")

        self.stdout.write()
        self.stdout.write(self.style.SUCCESS("DONE"))
