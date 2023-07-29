"""Eve sovereignty related core logic."""

from typing import Optional

from structures.constants import EveTypeId

_MAP_CAMPAIGN_EVENT_2_TYPE_ID = {
    1: EveTypeId.TCU,
    2: EveTypeId.IHUB,
}
_MAP_TYPE_ID_2_TIMER_STRUCTURE_NAME = {
    EveTypeId.CUSTOMS_OFFICE: "POCO",
    EveTypeId.TCU: "TCU",
    EveTypeId.IHUB: "I-HUB",
}


def event_type_to_type_id(event_type: int) -> Optional[int]:
    """Convert an event type to a type ID."""
    return _MAP_CAMPAIGN_EVENT_2_TYPE_ID.get(event_type)


def event_type_to_structure_type_name(event_type: int) -> str:
    """Convert an event type to a structure type name."""
    return _MAP_TYPE_ID_2_TIMER_STRUCTURE_NAME.get(
        event_type_to_type_id(event_type), "Other"
    )
