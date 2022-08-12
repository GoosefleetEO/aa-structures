from enum import IntEnum


# Eve enums
class EveAttributeId(IntEnum):
    SQUADRON_SIZE = 2215


class EveCategoryId(IntEnum):
    ORBITAL = 46
    STARBASE = 23
    STRUCTURE = 65


class EveGroupId(IntEnum):
    CITADEL = 1657
    CONTROL_TOWER = 365
    ENGINEERING_COMPLEX = 1404
    FUEL_BLOCK = 1136
    REFINERY = 1406


class EveTypeId(IntEnum):
    CALDARI_CONTROL_TOWER = 16213
    CUSTOMS_OFFICE = 2233
    IHUB = 32458
    JUMP_GATE = 35841
    LIQUID_OZONE = 16273
    NITROGEN_FUEL_BLOCK = 4051
    STRONTIUM = 16275
    TCU = 32226


class EveCorporationId(IntEnum):
    DED = 1000137
