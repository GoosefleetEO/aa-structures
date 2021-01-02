from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import (
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
)


def get_input(text):
    """wrapped input to enable unit testing / patching"""
    return input(text)


class Command(BaseCommand):
    help = (
        "Removes all app-related data from the database. "
        "Run this command before zero migrations, "
        "which would otherwise fail due to FK constraints."
    )

    def _purge_all_data(self):
        """updates all SDE models from ESI and provides progress output"""
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
        with transaction.atomic():
            for MyModel in models:
                self.stdout.write("Deleting all {} objects".format(MyModel.__name__))
                MyModel.objects.all().delete()

    def handle(self, *args, **options):
        self.stdout.write(
            "This command will delete all app related data in the database. "
            "This can not be undone. Use with caution."
        )
        user_input = get_input("Are you sure you want to proceed? (y/N)?")
        if user_input.lower() == "y":
            self.stdout.write("Starting data purge. Please stand by.")
            self._purge_all_data()
            self.stdout.write("Purge complete!")
        else:
            self.stdout.write("Aborted")
