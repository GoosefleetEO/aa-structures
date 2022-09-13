"""Creating or removing timers from notifications."""

import datetime as dt

from django.utils.translation import gettext
from eveuniverse.models import EveMoon, EvePlanet, EveSolarSystem, EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.datetime import (
    DATETIME_FORMAT,
    ldap_time_2_datetime,
    ldap_timedelta_2_timedelta,
)
from app_utils.django import app_labels
from app_utils.logging import LoggerAddTag

from .. import __title__
from ..app_settings import (
    STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED,
    STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
)
from ..constants import EveTypeId
from ..models import Notification, NotificationType, Structure
from . import sovereignty, starbases

if "timerboard" in app_labels():
    from allianceauth.timerboard.models import Timer as AuthTimer

    has_auth_timers = True
else:
    has_auth_timers = False

if "structuretimers" in app_labels():
    from structuretimers.models import Timer

    has_structure_timers = True
else:
    has_structure_timers = False

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def add_or_remove_timer(notif: Notification) -> bool:
    """Add/remove a timer related to this notification for some types.

    Returns True when timers where added or removed, else False
    """
    parsed_text = notif.parsed_text()
    if notif.notif_type in [
        NotificationType.STRUCTURE_LOST_ARMOR,
        NotificationType.STRUCTURE_LOST_SHIELD,
    ]:
        timer_processed = _gen_timer_structure_reinforcement(notif, parsed_text)
    elif notif.notif_type == NotificationType.SOV_STRUCTURE_REINFORCED:
        timer_processed = _gen_timer_sov_reinforcements(notif, parsed_text)
    elif notif.notif_type == NotificationType.ORBITAL_REINFORCED:
        timer_processed = _gen_timer_orbital_reinforcements(notif, parsed_text)
    elif notif.notif_type in [
        NotificationType.MOONMINING_EXTRACTION_STARTED,
        NotificationType.MOONMINING_EXTRACTION_CANCELLED,
    ]:
        if not STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED:
            timer_processed = None
        else:
            timer_processed = _gen_timer_moon_extraction(notif, parsed_text)
    elif notif.notif_type == NotificationType.TOWER_REINFORCED_EXTRA:
        timer_processed = _gen_timer_tower_reinforcements(notif, parsed_text)
    else:
        raise NotImplementedError(
            f"Unsupported notification type for timers: {notif.notif_type}"
        )
    if timer_processed:
        logger.info("%s: Created timer for notification", notif.notification_id)
        notif.is_timer_added = True
        notif.save()
    return timer_processed


def _gen_timer_structure_reinforcement(notif: Notification, parsed_text: str) -> bool:
    """Generate timer for structure reinforcements"""
    token = notif.owner.fetch_token()
    structure_obj, _ = Structure.objects.get_or_create_esi(
        id=parsed_text["structureID"], token=token
    )
    eve_time = notif.timestamp + ldap_timedelta_2_timedelta(parsed_text["timeLeft"])
    timer_processed = False
    if has_auth_timers:
        details_map = {
            NotificationType.STRUCTURE_LOST_SHIELD: gettext("Armor timer"),
            NotificationType.STRUCTURE_LOST_ARMOR: gettext("Final timer"),
        }
        AuthTimer.objects.create(
            details=details_map.get(notif.notif_type, ""),
            system=structure_obj.eve_solar_system.name,
            planet_moon="",
            structure=structure_obj.eve_type.name,
            objective="Friendly",
            eve_time=eve_time,
            eve_corp=notif.owner.corporation,
            corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
        )
        timer_processed = True

    if has_structure_timers:
        timer_map = {
            NotificationType.STRUCTURE_LOST_SHIELD: Timer.Type.ARMOR,
            NotificationType.STRUCTURE_LOST_ARMOR: Timer.Type.HULL,
        }
        visibility = (
            Timer.Visibility.CORPORATION
            if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
            else Timer.Visibility.UNRESTRICTED
        )
        Timer.objects.create(
            eve_solar_system=structure_obj.eve_solar_system,
            structure_type=structure_obj.eve_type,
            timer_type=timer_map.get(notif.notif_type),
            objective=Timer.Objective.FRIENDLY,
            date=eve_time,
            eve_corporation=notif.owner.corporation,
            eve_alliance=notif.owner.corporation.alliance,
            visibility=visibility,
            structure_name=structure_obj.name,
            owner_name=notif.owner.corporation.corporation_name,
            details_notes=_timer_details_notes(notif),
        )
        timer_processed = True

    return timer_processed


def _gen_timer_sov_reinforcements(notif: Notification, parsed_text: str) -> bool:
    """Generate timer for sov reinforcements."""
    if not notif.owner.is_alliance_main:
        return False

    solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
        id=parsed_text["solarSystemID"]
    )
    structure_type_name = sovereignty.structure_type_name_from_event_type(
        parsed_text["campaignEventType"]
    )
    eve_time = ldap_time_2_datetime(parsed_text["decloakTime"])
    timer_processed = False
    if has_auth_timers:
        AuthTimer.objects.create(
            details=gettext("Sov timer"),
            system=solar_system.name,
            planet_moon="",
            structure=structure_type_name,
            objective="Friendly",
            eve_time=eve_time,
            eve_corp=notif.owner.corporation,
            corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
        )
        timer_processed = True

    if has_structure_timers:
        eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=parsed_text["solarSystemID"]
        )
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=sovereignty.type_id_from_event_type(parsed_text["campaignEventType"])
        )
        visibility = (
            Timer.Visibility.CORPORATION
            if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
            else Timer.Visibility.UNRESTRICTED
        )
        Timer.objects.create(
            eve_solar_system=eve_solar_system,
            structure_type=structure_type,
            timer_type=Timer.Type.FINAL,
            objective=Timer.Objective.FRIENDLY,
            date=eve_time,
            eve_corporation=notif.owner.corporation,
            eve_alliance=notif.owner.corporation.alliance,
            visibility=visibility,
            owner_name=notif.sender.name,
            details_notes=_timer_details_notes(notif),
        )
        timer_processed = True

    return timer_processed


def _gen_timer_orbital_reinforcements(notif: Notification, parsed_text: str) -> bool:
    """Generate timer for orbital reinforcements."""
    solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
        id=parsed_text["solarSystemID"]
    )
    planet, _ = EvePlanet.objects.get_or_create_esi(id=parsed_text["planetID"])
    eve_time = ldap_time_2_datetime(parsed_text["reinforceExitTime"])
    timer_processed = False
    if has_auth_timers:
        AuthTimer.objects.create(
            details=gettext("Final timer"),
            system=solar_system.name,
            planet_moon=planet.name,
            structure="POCO",
            objective="Friendly",
            eve_time=eve_time,
            eve_corp=notif.owner.corporation,
            corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
        )
        timer_processed = True

    if has_structure_timers:
        eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=parsed_text["solarSystemID"]
        )
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=EveTypeId.CUSTOMS_OFFICE
        )
        visibility = (
            Timer.Visibility.CORPORATION
            if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
            else Timer.Visibility.UNRESTRICTED
        )
        Timer.objects.create(
            eve_solar_system=eve_solar_system,
            structure_type=structure_type,
            timer_type=Timer.Type.FINAL,
            objective=Timer.Objective.FRIENDLY,
            date=eve_time,
            location_details=planet.name,
            eve_corporation=notif.owner.corporation,
            eve_alliance=notif.owner.corporation.alliance,
            visibility=visibility,
            structure_name="Customs Office",
            owner_name=notif.owner.corporation.corporation_name,
            details_notes=_timer_details_notes(notif),
        )
        timer_processed = True

    return timer_processed


def _gen_timer_moon_extraction(notif: Notification, parsed_text: str) -> bool:
    """Generate timer for moon mining extractions."""
    solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
        id=parsed_text["solarSystemID"]
    )
    moon, _ = EveMoon.objects.get_or_create_esi(id=parsed_text["moonID"])
    if "readyTime" in parsed_text:
        eve_time = ldap_time_2_datetime(parsed_text["readyTime"])
    else:
        eve_time = None
    details = gettext("Extraction ready")
    system = solar_system.name
    planet_moon = moon.name
    structure_type_name = "Moon Mining Cycle"
    objective = "Friendly"
    timer_processed = False

    if has_structure_timers:
        eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=parsed_text["solarSystemID"]
        )
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=parsed_text["structureTypeID"]
        )
        visibility = (
            Timer.Visibility.CORPORATION
            if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
            else Timer.Visibility.UNRESTRICTED
        )
    else:
        eve_solar_system = None
        structure_type = None
        visibility = None

    if notif.notif_type == NotificationType.MOONMINING_EXTRACTION_STARTED:
        if has_auth_timers:
            AuthTimer.objects.create(
                details=details,
                system=system,
                planet_moon=planet_moon,
                structure=structure_type_name,
                objective=objective,
                eve_time=eve_time,
                eve_corp=notif.owner.corporation,
                corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
            )
            timer_processed = True

        if has_structure_timers:
            eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                id=parsed_text["solarSystemID"]
            )
            structure_type, _ = EveType.objects.get_or_create_esi(
                id=parsed_text["structureTypeID"]
            )
            visibility = (
                Timer.Visibility.CORPORATION
                if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
                else Timer.Visibility.UNRESTRICTED
            )
            Timer.objects.create(
                eve_solar_system=eve_solar_system,
                structure_type=structure_type,
                timer_type=Timer.Type.MOONMINING,
                objective=Timer.Objective.FRIENDLY,
                date=eve_time,
                location_details=moon.name,
                eve_corporation=notif.owner.corporation,
                eve_alliance=notif.owner.corporation.alliance,
                visibility=visibility,
                structure_name=parsed_text["structureName"],
                owner_name=notif.owner.corporation.corporation_name,
                details_notes=_timer_details_notes(notif),
            )
            timer_processed = True

    elif notif.notif_type == NotificationType.MOONMINING_EXTRACTION_CANCELLED:
        timer_processed = True
        notifications_qs = Notification.objects.filter(
            notif_type=NotificationType.MOONMINING_EXTRACTION_STARTED,
            owner=notif.owner,
            is_timer_added=True,
            timestamp__lte=notif.timestamp,
        ).order_by("-timestamp")
        for notification in notifications_qs:
            parsed_text_2 = notification.parsed_text()
            my_structure_type_id = parsed_text_2["structureTypeID"]
            if my_structure_type_id == parsed_text["structureTypeID"]:
                eve_time = ldap_time_2_datetime(parsed_text_2["readyTime"])
                if has_auth_timers:
                    timer_query = AuthTimer.objects.filter(
                        system=system,
                        planet_moon=planet_moon,
                        structure=structure_type_name,
                        objective=objective,
                        eve_time=eve_time,
                    )
                    deleted_count, _ = timer_query.delete()
                    logger.info(
                        f"{notif.notification_id}: removed {deleted_count} "
                        "obsolete Auth timers related to notification"
                    )

                if has_structure_timers:
                    timer_query = Timer.objects.filter(
                        eve_solar_system=eve_solar_system,
                        structure_type=structure_type,
                        timer_type=Timer.Type.MOONMINING,
                        location_details=moon.name,
                        date=eve_time,
                        objective=Timer.Objective.FRIENDLY,
                        eve_corporation=notif.owner.corporation,
                        eve_alliance=notif.owner.corporation.alliance,
                        visibility=visibility,
                        structure_name=parsed_text["structureName"],
                        owner_name=notif.owner.corporation.corporation_name,
                    )
                    deleted_count, _ = timer_query.delete()
                    logger.info(
                        f"{notif.notification_id}: removed {deleted_count} "
                        "obsolete structure timers related to notification"
                    )

    return timer_processed


def _gen_timer_tower_reinforcements(notif: Notification, parsed_text: str) -> bool:
    """Generate timer for tower reinforcements."""
    structure = notif.structures.first()
    eve_time = dt.datetime.fromisoformat(notif.details["reinforced_until"])
    timer_processed = False
    if has_auth_timers:
        structure_type_map = {
            starbases.StarbaseSize.SMALL: "POS[S]",
            starbases.StarbaseSize.MEDIUM: "POS[M]",
            starbases.StarbaseSize.LARGE: "POS[L]",
        }
        structure_str = structure_type_map.get(
            starbases.starbase_size(structure.eve_type), "POS[M]"
        )
        AuthTimer.objects.create(
            details=gettext("Final timer"),
            system=structure.eve_solar_system.name,
            planet_moon=structure.eve_moon.name,
            structure=structure_str,
            objective="Friendly",
            eve_time=eve_time,
            eve_corp=notif.owner.corporation,
            corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
        )
        timer_processed = True

    if has_structure_timers:
        eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=structure.eve_solar_system.id
        )
        structure_type, _ = EveType.objects.get_or_create_esi(id=structure.eve_type.id)
        visibility = (
            Timer.Visibility.CORPORATION
            if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
            else Timer.Visibility.UNRESTRICTED
        )
        Timer.objects.create(
            eve_solar_system=eve_solar_system,
            structure_type=structure_type,
            timer_type=Timer.Type.FINAL,
            objective=Timer.Objective.FRIENDLY,
            date=eve_time,
            location_details=structure.eve_moon.name,
            eve_corporation=notif.owner.corporation,
            eve_alliance=notif.owner.corporation.alliance,
            visibility=visibility,
            structure_name=structure.name,
            owner_name=notif.owner.corporation.corporation_name,
            details_notes=_timer_details_notes(notif),
        )
        timer_processed = True

    return timer_processed


def _timer_details_notes(notif: Notification) -> str:
    """Return generated details notes string for Timers."""
    return (
        "Automatically created from structure notification for "
        f"{notif.owner.corporation} at {notif.timestamp.strftime(DATETIME_FORMAT)}"
    )
