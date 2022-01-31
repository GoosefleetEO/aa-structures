import logging

from esi.clients import EsiClientProvider

from app_utils.logging import LoggerAddTag

from . import __title__, __version__

logger = LoggerAddTag(logging.getLogger(__name__), __title__)
esi = EsiClientProvider(app_info_text=f"aa-structures v{__version__}")
