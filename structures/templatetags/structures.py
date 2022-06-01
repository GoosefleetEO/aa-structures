from django import template
from eveuniverse.core import eveimageserver

from ..models import EveType

register = template.Library()


@register.inclusion_tag("structures/templatetags/detail_title.html")
def detail_title(structure):
    """Render HTML for detail box title."""
    image_url = eveimageserver.type_render_url(type_id=structure.eve_type_id, size=256)
    return {"image_url": image_url}


@register.inclusion_tag("structures/templatetags/list_title.html")
def list_title(title: str):
    """Render HTML for list title."""
    return {"title": title}


@register.inclusion_tag("structures/templatetags/list_item.html")
def list_item(title: str, value="", eve_type=None, is_muted=False):
    """Render HTML for list item."""
    return {"title": title, "value": value, "eve_type": eve_type, "is_muted": is_muted}


@register.inclusion_tag("structures/templatetags/list_asset.html")
def list_asset(eve_type: EveType, quantity=None):
    """Render HTML for an asset with optional quantity."""
    try:
        name = eve_type.name
        icon_url = eve_type.icon_url()
        profile_url = eve_type.profile_url
    except AttributeError:
        name = icon_url = profile_url = ""
    return {
        "name": name,
        "icon_url": icon_url,
        "profile_url": profile_url,
        "quantity": quantity,
    }
