import datetime as dt
from typing import List, Optional

import factory
import factory.fuzzy
import pytz
import yaml

from django.db.models import Max
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveMoon, EvePlanet, EveSolarSystem, EveType

from allianceauth.authentication.models import CharacterOwnership
from app_utils.testdata_factories import (
    EveAllianceInfoFactory,
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)

from ...models import (
    FuelAlertConfig,
    GeneratedNotification,
    JumpFuelAlertConfig,
    Notification,
    NotificationType,
    Owner,
    OwnerCharacter,
    Structure,
    StructureTag,
    Webhook,
)

# eve universe (within structures)


def datetime_to_esi(my_dt: dt.datetime) -> str:
    """Convert datetime to ESI datetime string."""
    utc_dt = my_dt.astimezone(pytz.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class EveEntityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EveEntity
        django_get_or_create = ("id", "name")

    category = EveEntity.CATEGORY_CHARACTER

    @factory.lazy_attribute
    def id(self):
        if self.category == EveEntity.CATEGORY_CHARACTER:
            obj = EveCharacterFactory()
            return obj.character_id
        if self.category == EveEntity.CATEGORY_CORPORATION:
            obj = EveCorporationInfoFactory()
            return obj.corporation_id
        if self.category == EveEntity.CATEGORY_ALLIANCE:
            obj = EveAllianceInfoFactory()
            return obj.alliance_id
        raise NotImplementedError(f"Unknown category: {self.category}")


class EveEntityCharacterFactory(EveEntityFactory):
    name = factory.Sequence(lambda n: f"character_name_{n}")
    category = EveEntity.CATEGORY_CHARACTER


class EveEntityCorporationFactory(EveEntityFactory):
    name = factory.Sequence(lambda n: f"corporation_name_{n}")
    category = EveEntity.CATEGORY_CORPORATION


class EveEntityAllianceFactory(EveEntityFactory):
    name = factory.Sequence(lambda n: f"alliance_name_{n}")
    category = EveEntity.CATEGORY_ALLIANCE


# Structures objects


class FuelAlertConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FuelAlertConfig

    start = 48
    end = 0
    repeat = 12


class JumpFuelAlertConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = JumpFuelAlertConfig

    threshold = 100


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

    name = factory.Sequence(lambda n: f"name_{n}")
    url = factory.Sequence(lambda n: f"url_{n}")
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
    character_ownership = None  # no longer used
    forwarding_last_update_at = factory.LazyFunction(now)
    is_alliance_main = False
    is_up = True
    notifications_last_update_at = factory.LazyFunction(now)
    structures_last_update_at = factory.LazyFunction(now)
    corporation = factory.SubFactory(EveCorporationInfoFactory)

    @factory.post_generation
    def characters(
        obj, create: bool, extracted: Optional[List[CharacterOwnership]], **kwargs
    ):
        if not create:
            return
        if extracted:
            for character_ownership in extracted:
                OwnerCharacterFactory(
                    owner=obj, character_ownership=character_ownership
                )
            return
        character = EveCharacterFactory(corporation=obj.corporation)
        user = UserMainDefaultOwnerFactory(main_character__character=character)
        character_ownership = user.profile.main_character.character_ownership
        OwnerCharacterFactory(owner=obj, character_ownership=character_ownership)

    @factory.post_generation
    def webhooks(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for webhook in extracted:
                obj.webhooks.add(webhook)
        else:
            obj.webhooks.add(WebhookFactory())


class StructureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Structure
        django_get_or_create = ("id",)

    fuel_expires_at = factory.LazyAttribute(lambda obj: now() + dt.timedelta(days=3))
    has_fitting = False
    has_core = False
    last_updated_at = factory.LazyFunction(now)
    name = factory.Sequence(lambda n: f"name_{n}")
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

    @factory.post_generation
    def webhooks(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for webhook in extracted:
                obj.webhooks.add(webhook)


class StarbaseFactory(StructureFactory):
    has_fitting = None
    has_core = None
    state = Structure.State.POS_ONLINE

    @factory.lazy_attribute
    def eve_moon(self):
        return EveMoon.objects.order_by("?").first()

    @factory.lazy_attribute
    def eve_solar_system(self):
        return self.eve_moon.eve_planet.eve_solar_system

    @factory.lazy_attribute
    def eve_type(self):
        return EveType.objects.get(name="Caldari Control Tower")


class PocoFactory(StructureFactory):
    has_fitting = None
    has_core = None
    state = Structure.State.NA

    @factory.lazy_attribute
    def eve_planet(self):
        return EvePlanet.objects.order_by("?").first()

    @factory.lazy_attribute
    def eve_solar_system(self):
        return self.eve_planet.eve_solar_system

    @factory.lazy_attribute
    def eve_type(self):
        return EveType.objects.get(name="Customs Office")


class JumpGateFactory(StructureFactory):
    @factory.lazy_attribute
    def eve_type(self):
        return EveType.objects.get(name="Ansiblex Jump Gate")


class StructureTagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StructureTag
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"name_{n}")
    description = factory.Faker("sentence")


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification
        exclude = ("text_from_dict",)

    text_from_dict = None

    created = factory.LazyFunction(now)
    is_read = False
    last_updated = factory.LazyAttribute(lambda o: o.created)
    notif_type = NotificationType.WAR_CORPORATION_BECAME_ELIGIBLE.value
    owner = factory.SubFactory(OwnerFactory)
    sender = factory.SubFactory(EveEntityCorporationFactory, id=1000137, name="DED")
    timestamp = factory.LazyAttribute(lambda o: o.created)

    @factory.lazy_attribute
    def notification_id(self):
        last_id = (
            Notification.objects.aggregate(Max("notification_id"))[
                "notification_id__max"
            ]
            or 1_500_000_000
        )
        return last_id + 1

    @factory.lazy_attribute
    def text(self):
        if not self.text_from_dict:
            return ""
        return yaml.dump(self.text_from_dict)

    @classmethod
    def _adjust_kwargs(cls, **kwargs):
        if isinstance(kwargs["notif_type"], NotificationType):
            kwargs["notif_type"] = kwargs["notif_type"].value
        return kwargs


class GeneratedNotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GeneratedNotification

    notif_type = NotificationType.TOWER_REINFORCED_EXTRA.value
    owner = factory.SubFactory(OwnerFactory)

    @factory.lazy_attribute
    def details(self):
        reinforced_until = factory.fuzzy.FuzzyDateTime(
            start_dt=now() + dt.timedelta(hours=3),
            end_dt=now() + dt.timedelta(hours=48),
        ).fuzz()
        return {"reinforced_until": reinforced_until.isoformat()}

    @factory.post_generation
    def create_structure(obj, create, extracted, **kwargs):
        """Set this param to False to disable."""
        if not create or extracted is False:
            return
        reinforced_until = dt.datetime.fromisoformat(obj.details["reinforced_until"])
        starbase = StarbaseFactory(
            owner=obj.owner,
            state=Structure.State.POS_REINFORCED,
            state_timer_end=reinforced_until,
        )
        obj.structures.add(starbase)


class RawNotificationFactory(factory.DictFactory):
    """Create a raw notification as received from ESI."""

    class Meta:
        exclude = ("data", "timestamp_dt", "sender")

    # excluded
    data = None
    timestamp_dt = None
    sender = factory.SubFactory(EveEntityCorporationFactory, id=2902, name="CONCORD")

    # included
    notification_id = factory.Sequence(lambda o: 1999000000 + o)
    type = "CorpBecameWarEligible"
    sender_id = factory.LazyAttribute(lambda o: o.sender.id)
    sender_type = factory.LazyAttribute(lambda o: o.sender.category)
    is_read = True

    @factory.lazy_attribute
    def timestamp(self):
        if not self.timestamp_dt:
            timestamp_dt = now()
        else:
            timestamp_dt = self.timestamp_dt
        return datetime_to_esi(timestamp_dt)

    @factory.lazy_attribute
    def text(self):
        if not self.data:
            return ""
        return yaml.dump(self.data)
