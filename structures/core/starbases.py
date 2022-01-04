from enum import IntEnum, auto

from ..constants import EveGroupId
from ..models.eveuniverse import EveType


class StarbaseSize(IntEnum):
    SMALL = auto()
    MEDIUM = auto()
    LARGE = auto()


def is_fuel_block(eve_type: EveType) -> bool:
    return eve_type.eve_group_id == EveGroupId.FUEL_BLOCK


def is_starbase(eve_type: EveType) -> bool:
    return eve_type.eve_group_id == EveGroupId.CONTROL_TOWER


def starbase_size(eve_type: EveType) -> StarbaseSize:
    """return the size of a starbase or None if this type is not a starbase"""
    if not is_starbase(eve_type):
        return None
    elif "medium" in eve_type.name.lower():
        return StarbaseSize.MEDIUM
    elif "small" in eve_type.name.lower():
        return StarbaseSize.SMALL
    return StarbaseSize.LARGE


def starbase_fuel_per_hour(eve_type: EveType):
    """returns the number of fuel blocks consumed per hour
    or None if not a starbase
    """
    size = starbase_size(eve_type)
    if size is StarbaseSize.LARGE:
        return 40
    elif size is StarbaseSize.MEDIUM:
        return 20
    elif size is StarbaseSize.SMALL:
        return 10
    return None
