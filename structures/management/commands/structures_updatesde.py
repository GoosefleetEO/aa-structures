from django.core.management.base import BaseCommand

from ...models import (
    EveCategory,
    EveConstellation,
    EveGroup,
    EveMoon,
    EveRegion,
    EveSolarSystem,
    EveType,
)


def get_input(text):
    """wrapped input to enable unit testing / patching"""
    return input(text)


class Command(BaseCommand):
    help = "Updates Eve Online SDE data"

    def _update_models(self):
        """updates all SDE models from ESI and provides progress output"""
        models = [
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveMoon,
        ]
        model_count = 0
        for EveModel in models:
            total_objects = EveModel.objects.count()
            model_count += 1
            self.stdout.write(
                "Updating %d objects of %s (%d/%d)..."
                % (total_objects, EveModel.__name__, model_count, len(models))
            )
            count_updated = EveModel.objects.update_all_esi()
            if count_updated < total_objects:
                self.stdout.write(
                    self.style.DANGER(
                        "Only %d objects updated due to an error." % count_updated
                    )
                )

    def handle(self, *args, **options):
        self.stdout.write(
            "This command will reload all local EVE Online SDE data from "
            "the server. This process can take a while to complete."
        )
        user_input = get_input("Are you sure you want to proceed? (y/N)?")
        if user_input.lower() == "y":
            self.stdout.write("Starting update. Please stand by.")
            self._update_models()
            self.stdout.write("Update completed!")
        else:
            self.stdout.write("Aborted")
