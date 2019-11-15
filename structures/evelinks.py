# this package contains helper functions for creating EVE related links
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

IMAGE_URL_DEFAULT_SIZE = 64

def get_alliance_image_url(id: int, size:int = IMAGE_URL_DEFAULT_SIZE) -> str:
    """returns the image URL for an alliance"""
    return get_image_url(ESI_CATEGORY_ALLIANCE, id, size)


def get_corporation_image_url(id: int, size: int = IMAGE_URL_DEFAULT_SIZE) -> str:
    """returns the image URL for an corporation"""
    return get_image_url(ESI_CATEGORY_CORPORATION, id, size)


def get_character_image_url(id: int, size: int = IMAGE_URL_DEFAULT_SIZE) -> str:
    """returns the image URL for a character"""
    return get_image_url(ESI_CATEGORY_CHARACTER, id, size)


def get_render_image_url(id: int, size: int = IMAGE_URL_DEFAULT_SIZE) -> str:
    """returns the image URL for a render"""
    return get_image_url('render', id, size)


def get_type_image_url(id: int, size: int = IMAGE_URL_DEFAULT_SIZE) -> str:
    """returns the image URL for a type"""
    return get_image_url(ESI_CATEGORY_INVENTORYTYPE, id, size)


def get_image_url(category: str, id: int, size: int = IMAGE_URL_DEFAULT_SIZE) -> str:
    """returns the image URL for an eve entity of category"""
    
    # defines all valid categories with respective sizes and image extensions
    IMAGES_TYPE_DEF = {
        ESI_CATEGORY_ALLIANCE: {
            "tag": "alliance",
            "sizes": [32, 64, 128], 
            "ext": "png"
        }, 
        ESI_CATEGORY_CORPORATION: {
            "tag": "corporation",
            "sizes": [32, 64, 128, 256],
            "ext": "png"
        }, 
        ESI_CATEGORY_CHARACTER: {
            "tag": "character",
            "sizes": [32, 64, 128, 256, 512, 1024],
            "ext": "jpg"
        }, 
        "render": {
            "tag": "render",
            "sizes": [32, 64, 128, 256, 512],
            "ext": "png"
        },
        ESI_CATEGORY_INVENTORYTYPE: {
            "tag": "Type",
            "sizes": [32, 64],
            "ext": "png"
        }        
    }
    
    # make sure the category is valid
    if not category in IMAGES_TYPE_DEF.keys():
        raise ValueError("Undefined category: " + str(category))

    # make sure the size is valid
    if not size in IMAGES_TYPE_DEF[category]['sizes']:
        raise ValueError("Invalid size for category: " + str(category))
    
    return "https://imageserver.eveonline.com/{}/{}_{}.{}".format(
        IMAGES_TYPE_DEF[category]["tag"],
        int(id),
        size,
        IMAGES_TYPE_DEF[category]["ext"]
    )

def get_entity_profile_url_by_name(category: str, name: str) -> str:
    """return url to profile page for an eve entity"""
    
    if category == ESI_CATEGORY_ALLIANCE:        
        url = "https://evemaps.dotlan.net/alliance/{}".format(
            urllib.parse.quote(name.replace(" ", "_"))
        )

    elif category == ESI_CATEGORY_CORPORATION:        
        url = "https://evemaps.dotlan.net/corporation/{}".format(
            urllib.parse.quote(name.replace(" ", "_"))
        )

    elif category == ESI_CATEGORY_SOLARSYSTEM:
        url = "https://evemaps.dotlan.net/system/{}".format(
            urllib.parse.quote(name)
        )
    
    else:
        raise NotImplementedError(
            "Not implemented yet for category:" + category
        )
    return url

def get_entity_profile_url_by_id(category: str, id: int) -> str:
    """return url to profile page for an eve entity"""
    if category == ESI_CATEGORY_INVENTORYTYPE:
        return "https://www.kalkoken.org/apps/eveitems/?typeId={}".format(
            int(id)
        )

    else:
        raise NotImplementedError(
            "Not implemented yet for category:" + category
        )

