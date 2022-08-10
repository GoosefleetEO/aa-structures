import datetime as dt

import factory
import factory.fuzzy

from django.db.models import Max
from django.utils.timezone import now

from app_utils.testdata_factories import (
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)

from ...models import (
    EveMoon,
    EveSolarSystem,
    EveType,
    GeneratedNotification,
    NotificationType,
    Owner,
    OwnerCharacter,
    Structure,
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


class StructureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Structure
        django_get_or_create = ("id",)

    fuel_expires_at = factory.LazyAttribute(lambda obj: now() + dt.timedelta(days=3))
    has_fitting = False
    has_core = False
    last_updated_at = factory.LazyFunction(now)
    name = factory.Faker("last_name")
    owner = factory.SubFactory(OwnerFactory)
    position_x = factory.fuzzy.FuzzyFloat(-10_000_000_000_000, 10_000_000_000_000)
    position_y = factory.fuzzy.FuzzyFloat(-10_000_000_000_000, 10_000_000_000_000)
    position_z = factory.fuzzy.FuzzyFloat(-10_000_000_000_000, 10_000_000_000_000)
    state = Structure.State.SHIELD_VULNERABLE

    @factory.lazy_attribute
    def eve_type(self):
        return EveType.objects.get(name="Astrahus")

    @factory.lazy_attribute
    def eve_solar_system(self):
        return EveSolarSystem.objects.order_by("?").first()

    @factory.lazy_attribute
    def id(self):
        last_id = Structure.objects.aggregate(Max("id"))["id__max"] or 1_500_000_000_000
        return last_id + 1


class StarbaseFactory(StructureFactory):
    has_fitting = None
    has_core = None
    state = Structure.State.POS_ONLINE

    @factory.lazy_attribute
    def eve_moon(self):
        return EveMoon.objects.order_by("?").first()

    @factory.lazy_attribute
    def eve_solar_system(self):
        return self.eve_moon.eve_solar_system

    @factory.lazy_attribute
    def eve_type(self):
        return EveType.objects.get(name="Caldari Control Tower")


class GeneratedNotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GeneratedNotification
        exclude = ("reinforced_until",)

    notif_type = factory.LazyAttribute(
        lambda obj: NotificationType.TOWER_REINFORCED_EXTRA
    )

    @factory.lazy_attribute
    def reinforced_until(self):
        return factory.fuzzy.FuzzyDateTime(
            start_dt=now() + dt.timedelta(hours=3),
            end_dt=now() + dt.timedelta(hours=48),
        ).fuzz()

    @factory.lazy_attribute
    def structure(self):
        return StarbaseFactory(
            state=Structure.State.POS_REINFORCED, state_timer_end=self.reinforced_until
        )

    @factory.lazy_attribute
    def details(self):
        return {"reinforced_until": self.reinforced_until.isoformat()}
