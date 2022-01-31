from random import randint
from typing import List

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


def create_structure(**kwargs) -> Structure:
    structure_id = _generate_unique_id(Structure, "id")
    params = {
        "id": structure_id,
        "name": f"Generated Structure #{structure_id}",
        "state": Structure.State.SHIELD_VULNERABLE,
    }
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
    kwargs["eve_type_id"] = EveTypeId.CUSTOMS_OFFICE
    if "eve_type" in kwargs:
        del kwargs["eve_type"]
    if "eve_planet_id" not in kwargs and "eve_planet" not in kwargs:
        kwargs["eve_planet_id"] = 40161472  # Amamake V
    structure = create_structure(**kwargs)
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


def create_starbase(**kwargs):
    if "eve_moon_id" not in kwargs and "eve_moon" not in kwargs:
        kwargs["eve_moon_id"] = 40161465  # Amamake II - Moon 1
    if "eve_type_id" not in kwargs and "eve_type" not in kwargs:
        kwargs["eve_type_id"] = 16213  # Caldari Control Tower
    structure = create_structure(**kwargs)
    assert structure.is_starbase
    return structure


def create_upwell_structure(**kwargs) -> Structure:
    structure = create_structure(**kwargs)
    assert structure.is_upwell_structure
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
