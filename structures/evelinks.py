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
CATEGORY_TYPE_RENDER = "render"

IMAGE_DEFAULT_SIZE = 64
IMAGESERVER_BASE_URL = 'https://images.evetech.net'
DOTLAN_BASE_URL = 'https://evemaps.dotlan.net'


def get_alliance_image_url(id: int, size: int = IMAGE_DEFAULT_SIZE) -> str:
    """returns the image URL for an alliance"""
    return get_image_url(ESI_CATEGORY_ALLIANCE, id, size)


def get_corporation_image_url(id: int, size: int = IMAGE_DEFAULT_SIZE) -> str:
    """returns the image URL for an corporation"""
    return get_image_url(ESI_CATEGORY_CORPORATION, id, size)


def get_character_image_url(id: int, size: int = IMAGE_DEFAULT_SIZE) -> str:
    """returns the image URL for a character"""
    return get_image_url(ESI_CATEGORY_CHARACTER, id, size)


def get_render_image_url(id: int, size: int = IMAGE_DEFAULT_SIZE) -> str:
    """returns the image URL for a render"""
    return get_image_url('render', id, size)


def get_type_image_url(id: int, size: int = IMAGE_DEFAULT_SIZE) -> str:
    """returns the image URL for a type"""
    return get_image_url(ESI_CATEGORY_INVENTORYTYPE, id, size)


def get_image_url(category: str, id: int, size: int = IMAGE_DEFAULT_SIZE) -> str:
    """returns the image URL for an eve entity of category"""
    
    VALID_CATEGORIES = {
        ESI_CATEGORY_ALLIANCE: 'alliances',      
        ESI_CATEGORY_CHARACTER: 'characters',
        ESI_CATEGORY_CORPORATION: 'corporations',
        ESI_CATEGORY_INVENTORYTYPE: 'types',        
        CATEGORY_TYPE_RENDER: 'renders'
    }    
    if category not in VALID_CATEGORIES.keys():
        raise ValueError("Undefined category: {}".format(category))
    
    if size < 32 or size > 1024 or (size % 2 != 0):
        raise ValueError("Invalid size: {}".format(size))
    
    url = '{}/{}/{}/icon'.format(
        IMAGESERVER_BASE_URL,
        VALID_CATEGORIES[category],
        int(id)
    )    
    if size:                
        args = {'size': size}
        url += '?{}'.format(urllib.parse.urlencode(args))
    return url    


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
