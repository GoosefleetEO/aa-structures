import logging
from pathlib import Path

from esi.clients import EsiClientProvider

from app_utils.logging import LoggerAddTag

from . import __title__, __version__

logger = LoggerAddTag(logging.getLogger(__name__), __title__)
swagger_path = Path(__file__).parent / "swagger.json"
esi = EsiClientProvider(
    app_info_text=f"aa-structures v{__version__}", spec_file=swagger_path
)
