from django.core.management import call_command
from django.core.management.base import BaseCommand

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from ... import __title__
from ...constants import EveCategoryId, EveGroupId, EveTypeId

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class Command(BaseCommand):
    help = "Preloads data required for this app from ESI"

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_true",
            help="Do NOT prompt the user for input of any kind.",
        )

    def handle(self, *args, **options):
        params = [
            "eveuniverse_load_types",
            __title__,
            "--category_id_with_dogma",
            EveCategoryId.STRUCTURE.value,
            "--group_id",
            EveGroupId.CONTROL_TOWER.value,
            "--group_id",
            EveGroupId.FUEL_BLOCK.value,
            "--type_id",
            EveTypeId.CUSTOMS_OFFICE.value,
            "--type_id",
            EveTypeId.IHUB.value,
            "--type_id",
            EveTypeId.LIQUID_OZONE.value,
            "--type_id",
            EveTypeId.STRONTIUM.value,
            "--type_id",
            EveTypeId.TCU.value,
        ]
        if options["noinput"]:
            params.append("--noinput")
        call_command(*params)
