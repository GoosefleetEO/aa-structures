import datetime as dt
from random import randint
from typing import List

import yaml

from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils.timezone import now

from allianceauth.eveonline.models import EveCorporationInfo

from ...constants import EveTypeId
from ...models import (
    EveSovereigntyMap,
    Notification,
    Owner,
    OwnerCharacter,
    PocoDetails,
    StarbaseDetail,
    StarbaseDetailFuel,
    Structure,
    StructureItem,
    StructureService,
    Webhook,
)


def create_eve_sovereignty_map(**kwargs):
    if "alliance_id" not in kwargs:
        kwargs["alliance_id"] = 3001
    return EveSovereigntyMap.objects.create(**kwargs)


def create_notification(**kwargs):
    """Args(optional):
    - data: details of notification as Python dict
    """
    params = {
        "notification_id": _generate_unique_id(Notification, "notification_id"),
        "sender_id": 2901,
        "timestamp": now(),
        "notif_type": "CorpBecameWarEligible",
        "last_updated": now(),
        "text": "{}",
    }
    if "owner" not in kwargs and "owner_id" not in kwargs:
        params["owner_id"] = 2001
    if "data" in kwargs:
        data = kwargs.pop("data")
        params["text"] = yaml.dump(data)
    params.update(kwargs)
    return Notification.objects.create(**params)


def create_owner_from_user(
    user: User, webhooks: List[Webhook] = None, **kwargs
) -> Owner:
    main_character = user.profile.main_character
    kwargs["corporation"] = EveCorporationInfo.objects.get(
        corporation_id=main_character.corporation_id
    )
    if "is_alliance_main" not in kwargs:
        kwargs["is_alliance_main"] = True
    owner = Owner.objects.create(**kwargs)
    if not webhooks:
        owner.webhooks.add(create_webhook())
    else:
        owner.webhooks.add(*webhooks)
    owner.characters.add(
        create_owner_character(
            owner=owner, character_ownership=main_character.character_ownership
        )
    )
    return owner


def create_owner_character(**kwargs) -> OwnerCharacter:
    return OwnerCharacter.objects.create(**kwargs)


def _create_structure(**kwargs) -> Structure:
    structure_id = _generate_unique_id(Structure, "id")
    params = {"id": structure_id, "name": f"Generated Structure #{structure_id}"}
    if "owner" not in kwargs and "owner_id" not in kwargs:
        params["owner_id"] = 2001  # Wayne Technologies
    if "eve_solar_system_id" not in kwargs and "eve_solar_system" not in kwargs:
        params["eve_solar_system_id"] = 30002537  # Amamake
    if "eve_type_id" not in kwargs and "eve_type" not in kwargs:
        params["eve_type_id"] = 35832  # Astrahus
    params.update(kwargs)
    return Structure.objects.create(**params)


def create_structure_item(**kwargs):
    params = {
        "id": _generate_unique_id(StructureItem, "id"),
        "location_flag": StructureItem.LocationFlag.CARGO,
        "is_singleton": False,
        "quantity": 1,
    }
    if "eve_type_id" not in kwargs and "eve_type" not in kwargs:
        params["eve_type_id"] = EveTypeId.LIQUID_OZONE
    params.update(kwargs)
    return StructureItem.objects.create(**params)


def create_poco(poco_details=None, **kwargs) -> Structure:
    params = {"state": Structure.State.UNKNOWN, "eve_type_id": EveTypeId.CUSTOMS_OFFICE}
    if "eve_type" in kwargs:
        del kwargs["eve_type"]
    if "eve_planet_id" not in kwargs and "eve_planet" not in kwargs:
        kwargs["eve_planet_id"] = 40161472  # Amamake V
    params.update(kwargs)
    structure = _create_structure(**params)
    assert structure.is_poco
    poco_params = {
        "alliance_tax_rate": 0.05,
        "allow_access_with_standings": True,
        "allow_alliance_access": True,
        "bad_standing_tax_rate": 0.1,
        "corporation_tax_rate": 0.1,
        "excellent_standing_tax_rate": 0.05,
        "good_standing_tax_rate": 0.05,
        "neutral_standing_tax_rate": 0.1,
        "reinforce_exit_end": 20,
        "reinforce_exit_start": 18,
        "standing_level": PocoDetails.StandingLevel.TERRIBLE,
        "structure": structure,
        "terrible_standing_tax_rate": 0.1,
    }
    if poco_details:
        poco_params.update(poco_details)
    PocoDetails.objects.create(**poco_params)
    return structure


def create_starbase(detail=None, fuels=None, **kwargs):
    if "eve_moon_id" not in kwargs and "eve_moon" not in kwargs:
        kwargs["eve_moon_id"] = 40161465  # Amamake II - Moon 1
    if "eve_type_id" not in kwargs and "eve_type" not in kwargs:
        kwargs["eve_type_id"] = EveTypeId.CALDARI_CONTROL_TOWER.value
    params = {
        "state": Structure.State.POS_ONLINE,
        "fuel_expires_at": now() + dt.timedelta(days=3),
        "position_x": 0,
        "position_y": 0,
        "position_z": 0,
    }
    params.update(kwargs)
    structure = _create_structure(**params)
    assert structure.is_starbase
    detail_params = {
        "allow_alliance_members": True,
        "allow_corporation_members": True,
        "anchor_role": StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE,
        "attack_if_at_war": True,
        "attack_if_other_security_status_dropping": True,
        "fuel_bay_take_role": StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE,
        "fuel_bay_view_role": StarbaseDetail.Role.STARBASE_FUEL_TECHNICIAN_ROLE,
        "last_modified_at": now(),
        "offline_role": StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE,
        "online_role": StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE,
        "structure": structure,
        "unanchor_role": StarbaseDetail.Role.CONFIG_STARBASE_EQUIPMENT_ROLE,
        "use_alliance_standings": True,
    }
    if detail:
        detail_params.update(detail)
    detail_obj = StarbaseDetail.objects.create(**detail_params)
    if not fuels:
        fuels = [
            {"quantity": 960, "eve_type_id": EveTypeId.NITROGEN_FUEL_BLOCK},
            {"quantity": 12000, "eve_type_id": EveTypeId.STRONTIUM},
        ]
    for fuel in fuels:
        StarbaseDetailFuel.objects.create(
            detail=detail_obj,
            eve_type_id=fuel["eve_type_id"],
            quantity=fuel["quantity"],
        )
    return structure


def create_upwell_structure(**kwargs) -> Structure:
    params = {
        "state": Structure.State.SHIELD_VULNERABLE,
        "fuel_expires_at": now() + dt.timedelta(days=3),
    }
    if "eve_type_id" not in kwargs and "eve_type" not in kwargs:
        params["eve_type_id"] = 35832  # Astrahus
    params.update(kwargs)
    structure = _create_structure(**params)
    assert structure.is_upwell_structure
    return structure


def create_jump_gate(**kwargs) -> Structure:
    kwargs["eve_type_id"] = EveTypeId.JUMP_GATE
    if "eve_type" in kwargs:
        del kwargs["eve_type"]
    structure = create_upwell_structure(**kwargs)
    assert structure.is_jump_gate
    return structure


def create_structure_service(**kwargs) -> StructureService:
    if "name" not in kwargs:
        kwargs["name"] = "Clone Bay"
    if "state" not in kwargs:
        kwargs["state"] = StructureService.State.ONLINE
    return StructureService.objects.create(**kwargs)


def create_webhook(**kwargs) -> Webhook:
    while True:
        num = randint(1, 100_000)
        name = f"Test Webhook #{num}"
        if not Webhook.objects.filter(name=name).exists():
            break
    params = {
        "name": name,
        "url": f"https://www.example.com/webhooks/{slugify(name)}",
        "is_active": True,
    }
    params.update(kwargs)
    return Webhook.objects.create(**params)


def _generate_unique_id(Model: object, field_name: str):
    while True:
        id = randint(1, 100_000_000_000)
        params = {field_name: id}
        if not Model.objects.filter(**params).exists():
            return id
