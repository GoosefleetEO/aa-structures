from enum import Enum, auto

from django.core.management.base import BaseCommand, CommandError
from eveuniverse.models import EveCategory as EveCategory2
from eveuniverse.models import EveConstellation as EveConstellation2
from eveuniverse.models import EveEntity as EveEntity2
from eveuniverse.models import EveGroup as EveGroup2
from eveuniverse.models import EveMoon as EveMoon2
from eveuniverse.models import EvePlanet as EvePlanet2
from eveuniverse.models import EveRegion as EveRegion2
from eveuniverse.models import EveSolarSystem as EveSolarSystem2
from eveuniverse.models import EveType as EveType2

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from ... import __title__
from ...models import (
    EveCategory,
    EveConstellation,
    EveEntity,
    EveGroup,
    EveMoon,
    EvePlanet,
    EveRegion,
    EveSolarSystem,
    EveType,
)

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def get_input(text):
    """wrapped input to enable unit testing / patching"""
    return input(text)


class ProcessMode(Enum):
    COPY = auto()
    CHECK = auto()


class Command(BaseCommand):
    help = "Preload missing eveuniverse objects in preparation for migrating to eveuniverse with release 2."

    def process(self, mode: ProcessMode):
        models_map = {
            EveEntity: EveEntity2,
            EveCategory: EveCategory2,
            EveGroup: EveGroup2,
            EveType: EveType2,
            EveRegion: EveRegion2,
            EveConstellation: EveConstellation2,
            EveSolarSystem: EveSolarSystem2,
            EvePlanet: EvePlanet2,
            EveMoon: EveMoon2,
        }
        for OldModel, NewModel in models_map.items():
            qs_old = OldModel.objects.all()
            if OldModel is EveEntity:
                qs_old = (
                    qs_old.exclude(category=EveEntity.Category.OTHER)
                    .exclude(id=1)
                    .exclude(name__isnull=True)
                )
            ids_target = set(qs_old.values_list("id", flat=True))
            ids_current = set(NewModel.objects.values_list("id", flat=True))
            ids_missing = ids_target.difference(ids_current)
            if mode is ProcessMode.COPY:
                if ids_missing:
                    self.stdout.write(
                        f"{OldModel.__name__}: Need to fetch {len(ids_missing)} "
                        "missing object(s) from ESI."
                    )
                else:
                    self.stdout.write(f"{OldModel.__name__}: No outstanding objects.")
                NewModel.objects.bulk_get_or_create_esi(ids=ids_target)
            elif mode is ProcessMode.CHECK:
                if ids_missing:
                    raise CommandError(f"Missing objects for {OldModel}. Please retry.")
            else:
                raise NotImplementedError(f"Invalid mode: {mode}")

    def handle(self, *args, **options):
        self.process(ProcessMode.COPY)
        self.process(ProcessMode.CHECK)
        self.stdout.write(self.style.SUCCESS("DONE"))
