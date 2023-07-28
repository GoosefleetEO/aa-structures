"""Helpers for generating embeds."""

import datetime as dt
from typing import Optional

from django.template import Context, Template
from django.utils.timezone import now
from django.utils.translation import gettext as __
from eveuniverse.models import EveEntity, EveSolarSystem

from allianceauth.eveonline.evelinks import dotlan, evewho
from app_utils.datetime import DATETIME_FORMAT

from structures.models import Structure, Webhook


def timeuntil(to_date: dt.datetime, from_date: Optional[dt.datetime] = None) -> str:
    """Render timeuntil template tag for given datetime to string."""
    if not from_date:
        from_date = now()
    template = Template("{{ to_date|timeuntil:from_date }}")
    context = Context({"to_date": to_date, "from_date": from_date})
    return template.render(context)


def target_datetime_formatted(target_datetime: dt.datetime) -> str:
    """Formatted Discord string for a target datetime."""
    return (
        f"{Webhook.text_bold(target_datetime.strftime(DATETIME_FORMAT))} "
        f"({timeuntil(target_datetime)})"
    )


def gen_solar_system_text(solar_system: EveSolarSystem) -> str:
    """Return generated text for a solar system."""
    solar_system_link = Webhook.create_link(
        solar_system.name, dotlan.solar_system_url(solar_system.name)
    )
    region_name = solar_system.eve_constellation.eve_region.name
    text = f"{solar_system_link} ({region_name})"
    return text


def gen_alliance_link(alliance_name: str) -> str:
    """Return generated text for an alliance link."""
    return Webhook.create_link(alliance_name, dotlan.alliance_url(alliance_name))


def gen_eve_entity_link(eve_entity: EveEntity) -> str:
    """Return a link for an alliance, corporation or character from an eve entity.

    Or return an empty string for any other category.
    """
    if eve_entity.category == EveEntity.CATEGORY_ALLIANCE:
        url = dotlan.alliance_url(eve_entity.name)

    elif eve_entity.category == EveEntity.CATEGORY_CORPORATION:
        url = dotlan.corporation_url(eve_entity.name)

    elif eve_entity.category == EveEntity.CATEGORY_CHARACTER:
        url = evewho.character_url(eve_entity.id)

    else:
        url = ""

    return Webhook.create_link(eve_entity.name, url)


def gen_eve_entity_link_from_id(id: int) -> str:
    """Return a link for an alliance, corporation or character from an ID."""
    if not id:
        return ""
    entity, _ = EveEntity.objects.get_or_create_esi(id=id)
    return gen_eve_entity_link(entity)


def gen_corporation_link(corporation_name: str) -> str:
    """Return a link for a corporation."""
    return Webhook.create_link(
        corporation_name, dotlan.corporation_url(corporation_name)
    )


def compile_damage_text(parsed_text: dict, field_postfix: str, factor: int = 1) -> str:
    """Compile damage text for Structures and POSes"""
    damage_labels = [
        ("shield", __("shield")),
        ("armor", __("armor")),
        ("hull", __("hull")),
    ]
    damage_parts = []
    for prop in damage_labels:
        field_name = f"{prop[0]}{field_postfix}"
        if field_name in parsed_text:
            label = prop[1]
            value = parsed_text[field_name] * factor
            damage_parts.append(f"{label}: {value:.1f}%")
    damage_text = " | ".join(damage_parts)
    return damage_text


def get_aggressor_link(parsed_text: dict) -> str:
    """Returns the aggressor link from a parsed_text for POS and POCOs only."""
    if parsed_text.get("aggressorAllianceID"):
        key = "aggressorAllianceID"
    elif parsed_text.get("aggressorCorpID"):
        key = "aggressorCorpID"
    elif parsed_text.get("aggressorID"):
        key = "aggressorID"
    else:
        return "(Unknown aggressor)"
    entity, _ = EveEntity.objects.get_or_create_esi(id=parsed_text[key])
    return Webhook.create_link(entity.name, entity.profile_url)


def fuel_expires_target_date(structure: Optional[Structure]) -> str:
    """Return calculated target date when fuel expires."""
    if structure and structure.fuel_expires_at:
        return target_datetime_formatted(structure.fuel_expires_at)
    return "?"
