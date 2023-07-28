"""Helpers for generating embeds."""

import datetime as dt
from typing import Optional

from django.template import Context, Template
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveSolarSystem

from allianceauth.eveonline.evelinks import dotlan, evewho
from app_utils.datetime import DATETIME_FORMAT

from structures.models import Webhook


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
    solar_system_link = Webhook.create_link(
        solar_system.name, dotlan.solar_system_url(solar_system.name)
    )
    region_name = solar_system.eve_constellation.eve_region.name
    text = f"{solar_system_link} ({region_name})"
    return text


def gen_alliance_link(alliance_name: str) -> str:
    return Webhook.create_link(alliance_name, dotlan.alliance_url(alliance_name))


def gen_eve_entity_external_url(eve_entity: EveEntity) -> str:
    if eve_entity.category == EveEntity.CATEGORY_ALLIANCE:
        return dotlan.alliance_url(eve_entity.name)

    if eve_entity.category == EveEntity.CATEGORY_CORPORATION:
        return dotlan.corporation_url(eve_entity.name)

    if eve_entity.category == EveEntity.CATEGORY_CHARACTER:
        return evewho.character_url(eve_entity.id)

    return ""


def gen_eve_entity_link(eve_entity: EveEntity) -> str:
    return Webhook.create_link(eve_entity.name, gen_eve_entity_external_url(eve_entity))


def gen_eve_entity_link_from_id(id: int) -> str:
    if not id:
        return ""
    entity, _ = EveEntity.objects.get_or_create_esi(id=id)
    return gen_eve_entity_link(entity)


def gen_corporation_link(corporation_name: str) -> str:
    return Webhook.create_link(
        corporation_name, dotlan.corporation_url(corporation_name)
    )
