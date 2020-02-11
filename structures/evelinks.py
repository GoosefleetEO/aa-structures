import urllib


# list of all eve entity categories as defined in ESI
ESI_CATEGORY_AGENT = "agent"
ESI_CATEGORY_ALLIANCE = "alliance"
ESI_CATEGORY_CHARACTER = "character"
ESI_CATEGORY_CONSTELLATION = "constellation"
ESI_CATEGORY_CORPORATION = "corporation"
ESI_CATEGORY_FACTION = "faction"
ESI_CATEGORY_INVENTORYTYPE = "inventory_type"
ESI_CATEGORY_REGION = "region"
ESI_CATEGORY_SOLARSYSTEM = "solar_system"
ESI_CATEGORY_STATION = "station"
ESI_CATEGORY_WORMHOLE = "wormhole"


DOTLAN_BASE_URL = 'http://evemaps.dotlan.net'


def get_entity_profile_url_by_name(category: str, name: str) -> str:
    """return url to profile page for an eve entity"""

    if category == ESI_CATEGORY_ALLIANCE:
        url = "{}/alliance/{}".format(
            DOTLAN_BASE_URL,
            urllib.parse.quote(name.replace(" ", "_"))
        )

    elif category == ESI_CATEGORY_CORPORATION:
        url = "{}/corp/{}".format(
            DOTLAN_BASE_URL,
            urllib.parse.quote(name.replace(" ", "_"))
        )

    elif category == ESI_CATEGORY_SOLARSYSTEM:
        url = "{}/system/{}".format(
            DOTLAN_BASE_URL,
            urllib.parse.quote(name)
        )

    else:
        raise NotImplementedError(
            "Not implemented yet for category:" + category
        )
    return url


def get_entity_profile_url_by_id(category: str, id: int) -> str:
    """return url to profile page for an eve entity"""
    raise NotImplementedError()
