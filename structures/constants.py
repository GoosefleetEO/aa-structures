"""Constants for Structures."""

from enum import IntEnum


# Eve enums
class EveAttributeId(IntEnum):
    """An EVE attribute ID."""

    SQUADRON_SIZE = 2215


class EveCategoryId(IntEnum):
    """An EVE category ID."""

    ORBITAL = 46
    STARBASE = 23
    STRUCTURE = 65


class EveGroupId(IntEnum):
    """An EVE group ID."""

    CITADEL = 1657
    CONTROL_TOWER = 365
    ENGINEERING_COMPLEX = 1404
    FUEL_BLOCK = 1136
    ICE_PRODUCT = 423
    REFINERY = 1406
    PLANET = 7
    STRUCTURE_CITADEL_SERVICE_MODULE = 1321
    UNCOMMON_MOON_ASTEROIDS = 1921
    QUANTUM_CORES = 4086


class EveTypeId(IntEnum):
    """An EVE type ID."""

    CALDARI_CONTROL_TOWER = 16213
    CUSTOMS_OFFICE = 2233
    IHUB = 32458
    JUMP_GATE = 35841
    LIQUID_OZONE = 16273
    NITROGEN_FUEL_BLOCK = 4051
    STRONTIUM = 16275
    TCU = 32226


class EveCorporationId(IntEnum):
    """An EVE corporation ID."""

    DED = 1000137
