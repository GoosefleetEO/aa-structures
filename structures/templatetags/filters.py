from django.template.defaulttags import register


@register.filter(name="empty_slots")
def empty_slots(fittings: dict, slot_type: str):
    keys = fittings.keys()

    for key in keys:
        if slot_type in key:
            # This slot type is not empty
            return False
    # This slot type is completely empty
    return True
