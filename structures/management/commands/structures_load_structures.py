from django.core.management import call_command
from django.core.management.base import BaseCommand

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from ... import __title__
from ...constants import EveCategoryId

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class Command(BaseCommand):
    help = "Preloads data required for this app from ESI"

    def handle(self, *args, **options):
        call_command(
            "eveuniverse_load_types",
            __title__,
            "--category_id_with_dogma",
            EveCategoryId.STRUCTURE.value,
        )
