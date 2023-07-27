from django.apps import AppConfig

from . import __version__


class StructuresConfig(AppConfig):
    name = "structures"
    label = "structures"
    verbose_name = f"Structures v{__version__}"
