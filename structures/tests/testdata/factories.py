from random import randint

from django.utils.text import slugify
from django.utils.timezone import now

from allianceauth.eveonline.models import EveCorporationInfo

from ...models import Notification, Owner, OwnerCharacter, Webhook


def create_notification(**kwargs):
    while True:
        notification_id = randint(1, 100_000_000_000)
        if not Notification.objects.filter(notification_id=notification_id).exists():
            break
    params = {
        "notification_id": notification_id,
        "sender_id": 2901,
        "timestamp": now(),
        "notif_type": "CorpBecameWarEligible",
    }
    params.update(kwargs)
    return Notification.objects.create(**params)


def create_owner_from_user(user, **kwargs) -> Owner:
    main_character = user.profile.main_character
    kwargs["corporation"] = EveCorporationInfo.objects.get(
        corporation_id=main_character.corporation_id
    )
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
