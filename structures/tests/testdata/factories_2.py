import factory
import factory.faker

from django.utils.timezone import now

from app_utils.testdata_factories import (
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)

from ...models import (
    NotificationType,
    Owner,
    OwnerCharacter,
    StructuresNotification,
    Webhook,
)


class UserMainDefaultFactory(UserMainFactory):
    """Default user in Structures."""

    main_character__scopes = Owner.get_esi_scopes()
    permissions__ = [
        "structures.basic_access",
        "structures.view_corporation_structures",
    ]


class UserMainDefaultOwnerFactory(UserMainFactory):
    """Default user owning structures."""

    main_character__scopes = Owner.get_esi_scopes()
    permissions__ = [
        "structures.basic_access",
        "structures.add_structure_owner",
        "structures.view_corporation_structures",
    ]


class WebhookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Webhook
        django_get_or_create = ("name",)

    name = factory.Faker("city")
    url = factory.Faker("url")
    notes = factory.Faker("sentence")


class OwnerCharacterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OwnerCharacter

    structures_last_used_at = factory.LazyFunction(now)
    notifications_last_used_at = factory.LazyFunction(now)


class OwnerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Owner
        django_get_or_create = ("corporation",)

    assets_last_update_at = factory.LazyFunction(now)
    character_ownership = None
    forwarding_last_update_at = factory.LazyFunction(now)
    is_alliance_main = True
    is_up = True
    notifications_last_update_at = factory.LazyFunction(now)
    structures_last_update_at = factory.LazyFunction(now)
    corporation = factory.SubFactory(EveCorporationInfoFactory)

    @factory.post_generation
    def add_owner_character(obj, create, extracted, **kwargs):
        """Set this param to False to disable."""
        if not create or extracted is False:
            return
        character = EveCharacterFactory(corporation=obj.corporation)
        user = UserMainDefaultOwnerFactory(main_character__character=character)
        character_ownership = user.profile.main_character.character_ownership
        OwnerCharacterFactory(owner=obj, character_ownership=character_ownership)

    @factory.post_generation
    def add_webhook(obj, create, extracted, **kwargs):
        """Set this param to False to disable."""
        if not create or extracted is False:
            return
        obj.webhooks.add(WebhookFactory())


class StructuresNotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StructuresNotification

    notif_type = factory.LazyAttribute(
        lambda obj: NotificationType.TOWER_REINFORCED_EXTRA
    )
    owner = factory.SubFactory(OwnerFactory)
