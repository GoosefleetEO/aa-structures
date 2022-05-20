import math
from enum import IntEnum, auto
from typing import Optional

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


def fuel_per_hour(eve_type: EveType) -> Optional[int]:
    """Calculate the number of fuel blocks consumed per hour.

    Returns None if not a starbase.
    """
    size = starbase_size(eve_type)
    if size is StarbaseSize.LARGE:
        return 40
    elif size is StarbaseSize.MEDIUM:
        return 20
    elif size is StarbaseSize.SMALL:
        return 10
    return None


def fuel_duration(
    starbase_type: EveType,
    fuel_quantity: int,
    has_sov: bool = False,
) -> float:
    """Calculate how long the fuel lasts in seconds."""
    sov_discount = 0.25 if has_sov else 0
    amount_per_hour = fuel_per_hour(starbase_type)
    if amount_per_hour is None:
        raise ValueError(
            f"{starbase_type}: Can only calculate fuel durations for starbases"
        )
    seconds = math.floor(3600 * fuel_quantity / (amount_per_hour * (1 - sov_discount)))
    return seconds
