from django import template

register = template.Library()


@register.inclusion_tag("structures/templatetags/list_title.html")
def list_title(title: str):
    """Render HTML for list title."""
    return {"title": title}


@register.inclusion_tag("structures/templatetags/list_item.html")
def list_item(title: str, value="", eve_type=None, is_muted=False):
    """Render HTML for list item."""
    return {"title": title, "value": value, "eve_type": eve_type, "is_muted": is_muted}
