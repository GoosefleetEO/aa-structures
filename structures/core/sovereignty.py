"""Eve sovereignty related core logic."""

from typing import Optional

from ..constants import EveTypeId

_MAP_CAMPAIGN_EVENT_2_TYPE_ID = {
    1: EveTypeId.TCU,
    2: EveTypeId.IHUB,
}
_MAP_TYPE_ID_2_TIMER_STRUCTURE_NAME = {
    EveTypeId.CUSTOMS_OFFICE: "POCO",
    EveTypeId.TCU: "TCU",
    EveTypeId.IHUB: "I-HUB",
}


def type_id_from_event_type(event_type: int) -> Optional[int]:
    return _MAP_CAMPAIGN_EVENT_2_TYPE_ID.get(event_type)


def structure_type_name_from_event_type(event_type: int) -> str:
    return _MAP_TYPE_ID_2_TIMER_STRUCTURE_NAME.get(
        type_id_from_event_type(event_type), "Other"
    )
