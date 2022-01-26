from random import randint

from django.utils.text import slugify
from django.utils.timezone import now

from allianceauth.eveonline.models import EveCorporationInfo

from ...models import Notification, Owner, OwnerCharacter, Structure, Webhook


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


def create_owner_from_user(user, **kwargs) -> Owner:
    main_character = user.profile.main_character
    kwargs["corporation"] = EveCorporationInfo.objects.get(
        corporation_id=main_character.corporation_id
    )
    if "is_alliance_main" not in kwargs:
        kwargs["is_alliance_main"] = True
    owner = Owner.objects.create(**kwargs)
    webhook = create_webhook()
    owner.webhooks.add(webhook)
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
        params["owner_id"] = 2001
    if "eve_solar_system_id" not in kwargs and "eve_solar_system" not in kwargs:
        params["eve_solar_system_id"] = 30002537
    if "eve_type_id" not in kwargs and "eve_type" not in kwargs:
        params["eve_type_id"] = 35832
    params.update(kwargs)
    return Structure.objects.create(**params)


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
