from django.apps import AppConfig

from . import __version__


class StructuresConfig(AppConfig):
    name = "structures"
    label = "structures"
    verbose_name = "Structures v{}".format(__version__)

    def ready(self):
        from . import signals  # noqa: F401
