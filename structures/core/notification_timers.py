"""Creating or removing timers from notifications."""

# pylint: disable = ungrouped-imports

import datetime as dt

from django.utils.translation import gettext
from eveuniverse.models import EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.datetime import (
    DATETIME_FORMAT,
    ldap_time_2_datetime,
    ldap_timedelta_2_timedelta,
)
from app_utils.django import app_labels
from app_utils.logging import LoggerAddTag

from structures import __title__
from structures.app_settings import (
    STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED,
    STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
)
from structures.constants import EveTypeId
from structures.models import Notification, Structure

from . import sovereignty, starbases
from .notification_types import NotificationType

if "timerboard" in app_labels():
    from allianceauth.timerboard.models import Timer as AuthTimer
else:
    AuthTimer = None  # pylint: disable = invalid-name

if "structuretimers" in app_labels():
    from structuretimers.models import Timer
else:
    Timer = None  # pylint: disable = invalid-name

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def add_or_remove_timer(notif: Notification) -> bool:
    """Add/remove a timer related to this notification for some types.

    Returns True when timers where added or removed, else False
    """
    if notif.notif_type in [
        NotificationType.STRUCTURE_LOST_ARMOR,
        NotificationType.STRUCTURE_LOST_SHIELD,
    ]:
        timer_processed = _gen_timer_structure_reinforcement(notif)
    elif notif.notif_type == NotificationType.SOV_STRUCTURE_REINFORCED:
        timer_processed = _gen_timer_sov_reinforcements(notif)
    elif notif.notif_type == NotificationType.ORBITAL_REINFORCED:
        timer_processed = _gen_timer_orbital_reinforcements(notif)
    elif notif.notif_type in [
        NotificationType.MOONMINING_EXTRACTION_STARTED,
        NotificationType.MOONMINING_EXTRACTION_CANCELLED,
    ]:
        if not STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED:
            timer_processed = None
        else:
            timer_processed = _gen_timer_moon_extraction(notif)
    elif notif.notif_type == NotificationType.TOWER_REINFORCED_EXTRA:
        timer_processed = _gen_timer_tower_reinforcements(notif)
    else:
        raise NotImplementedError(
            f"Unsupported notification type for timers: {notif.notif_type}"
        )
    if timer_processed:
        logger.info("%s: Created timer for notification", notif.notification_id)
        notif.is_timer_added = True
        notif.save()
    return timer_processed


def _gen_timer_structure_reinforcement(notif: Notification) -> bool:
    """Generate timer for structure reinforcements"""
    token = notif.owner.fetch_token()
    parsed_text = notif.parsed_text()
    structure_obj, _ = Structure.objects.get_or_create_esi(
        id=parsed_text["structureID"], token=token
    )
    eve_time = notif.timestamp + ldap_timedelta_2_timedelta(parsed_text["timeLeft"])
    timer_processed = False
    if AuthTimer:
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

    if Timer:
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


def _gen_timer_sov_reinforcements(notif: Notification) -> bool:
    """Generate timer for sov reinforcements."""
    if not notif.owner.is_alliance_main:
        return False

    parsed_text = notif.parsed_text()
    solar_system = notif.eve_solar_system()
    structure_type_name = sovereignty.event_type_to_structure_type_name(
        parsed_text["campaignEventType"]
    )
    eve_time = ldap_time_2_datetime(parsed_text["decloakTime"])
    timer_processed = False

    if AuthTimer:
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

    if Timer:
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=sovereignty.event_type_to_type_id(parsed_text["campaignEventType"])
        )
        visibility = (
            Timer.Visibility.CORPORATION
            if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
            else Timer.Visibility.UNRESTRICTED
        )
        Timer.objects.create(
            eve_solar_system=solar_system,
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


def _gen_timer_orbital_reinforcements(notif: Notification) -> bool:
    """Generate timer for orbital reinforcements."""

    solar_system = notif.eve_solar_system()
    planet = notif.eve_planet()
    parsed_text = notif.parsed_text()
    eve_time = ldap_time_2_datetime(parsed_text["reinforceExitTime"])
    timer_processed = False

    if AuthTimer:
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

    if Timer:
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=EveTypeId.CUSTOMS_OFFICE
        )
        visibility = (
            Timer.Visibility.CORPORATION
            if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
            else Timer.Visibility.UNRESTRICTED
        )
        Timer.objects.create(
            eve_solar_system=solar_system,
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


def _gen_timer_moon_extraction(notif: Notification) -> bool:
    """Generate timer for moon mining extractions."""
    solar_system = notif.eve_solar_system()
    moon = notif.eve_moon()
    parsed_text = notif.parsed_text()
    eve_time = _extract_eve_time(parsed_text)

    structure_type_name = "Moon Mining Cycle"
    objective = "Friendly"
    timer_processed = False
    structure_type = notif.eve_structure_type()

    if notif.notif_type == NotificationType.MOONMINING_EXTRACTION_STARTED:
        if AuthTimer:
            AuthTimer.objects.create(
                details=gettext("Extraction ready"),
                system=solar_system.name,
                planet_moon=moon.name,
                structure=structure_type_name,
                objective=objective,
                eve_time=eve_time,
                eve_corp=notif.owner.corporation,
                corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
            )
            timer_processed = True

        if Timer:
            Timer.objects.create(
                eve_solar_system=solar_system,
                structure_type=structure_type,
                timer_type=Timer.Type.MOONMINING,
                objective=Timer.Objective.FRIENDLY,
                date=eve_time,
                location_details=moon.name,
                eve_corporation=notif.owner.corporation,
                eve_alliance=notif.owner.corporation.alliance,
                visibility=_calc_visibility(),
                structure_name=parsed_text["structureName"],
                owner_name=notif.owner.corporation.corporation_name,
                details_notes=_timer_details_notes(notif),
            )
            timer_processed = True

    elif notif.notif_type == NotificationType.MOONMINING_EXTRACTION_CANCELLED:
        timer_processed = True

        for notification in Notification.objects.filter(
            notif_type=NotificationType.MOONMINING_EXTRACTION_STARTED,
            owner=notif.owner,
            is_timer_added=True,
            timestamp__lte=notif.timestamp,
        ).order_by("-timestamp"):
            notification: Notification
            parsed_text_2 = notification.parsed_text()
            my_structure_type_id = parsed_text_2["structureTypeID"]
            if my_structure_type_id == parsed_text["structureTypeID"]:
                eve_time_2 = _extract_eve_time(parsed_text_2)

                if AuthTimer:
                    timer_query = AuthTimer.objects.filter(
                        system=solar_system.name,
                        planet_moon=moon.name,
                        structure=structure_type_name,
                        objective=objective,
                        eve_time=eve_time_2,
                    )
                    deleted_count, _ = timer_query.delete()
                    logger.info(
                        "%s: removed %d obsolete Auth timers related to notification",
                        notif.notification_id,
                        deleted_count,
                    )

                if Timer:
                    timer_query = Timer.objects.filter(
                        eve_solar_system=solar_system,
                        structure_type=structure_type,
                        timer_type=Timer.Type.MOONMINING,
                        location_details=moon.name,
                        date=eve_time_2,
                        objective=Timer.Objective.FRIENDLY,
                        eve_corporation=notif.owner.corporation,
                        eve_alliance=notif.owner.corporation.alliance,
                        visibility=_calc_visibility(),
                        structure_name=parsed_text["structureName"],
                        owner_name=notif.owner.corporation.corporation_name,
                    )
                    deleted_count, _ = timer_query.delete()
                    logger.info(
                        "%s: removed %d obsolete structure timers "
                        "related to notification",
                        notif.notification_id,
                        deleted_count,
                    )

    return timer_processed


def _calc_visibility():
    if Timer:
        return (
            Timer.Visibility.CORPORATION
            if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
            else Timer.Visibility.UNRESTRICTED
        )
    return None


def _extract_eve_time(parsed_text):
    if "readyTime" in parsed_text:
        return ldap_time_2_datetime(parsed_text["readyTime"])
    return None


def _gen_timer_tower_reinforcements(notif: Notification) -> bool:
    """Generate timer for tower reinforcements."""
    structure = notif.structures.select_related(
        "eve_solar_system", "eve_type", "eve_moon"
    ).first()
    eve_time = dt.datetime.fromisoformat(notif.details["reinforced_until"])
    timer_processed = False

    if AuthTimer:
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

    if Timer:
        visibility = (
            Timer.Visibility.CORPORATION
            if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
            else Timer.Visibility.UNRESTRICTED
        )
        Timer.objects.create(
            eve_solar_system=structure.eve_solar_system,
            structure_type=structure.eve_type,
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
