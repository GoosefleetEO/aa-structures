import datetime as dt
import itertools
from typing import Optional, Set, Tuple, TypeVar

from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Case, Count, Exists, OuterRef, Q, Value, When
from django.utils.timezone import now
from esi.models import Token
from eveuniverse.models import EveMoon, EvePlanet, EveSolarSystem, EveType

from allianceauth.eveonline.models import EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
from .constants import EveCategoryId, EveTypeId
from .providers import esi
from .webhooks.managers import WebhookBaseManager

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

ModelType = TypeVar("ModelType", bound=models.Model)


class EveSovereigntyMapManager(models.Manager):
    def update_from_esi(self):
        sov_map = esi.client.Sovereignty.get_sovereignty_map().results()
        logger.info("Retrieved sovereignty map from ESI")
        last_updated = now()
        obj_list = list()
        for solar_system in sov_map:
            obj_def = {
                "solar_system_id": solar_system["system_id"],
                "last_updated": last_updated,
            }
            for key in ["alliance_id", "corporation_id", "faction_id"]:
                if key in solar_system and solar_system[key]:
                    obj_def[key] = solar_system[key]
                else:
                    obj_def[key] = None

            if (
                obj_def["alliance_id"]
                or obj_def["corporation_id"]
                or obj_def["faction_id"]
            ):
                obj_list.append(self.model(**obj_def))

        if obj_list:
            logger.info("Storing sovereignty map ...")
            with transaction.atomic():
                self.all().delete()
                self.bulk_create(obj_list, batch_size=1000)

    def corporation_has_sov(
        self, eve_solar_system, corporation: EveCorporationInfo
    ) -> bool:
        """returns true if given corporation has sov in this solar system
        else False
        """
        if not eve_solar_system.is_null_sec:
            return False
        else:
            alliance_id = (
                int(corporation.alliance.alliance_id) if corporation.alliance else None
            )
            return bool(alliance_id) and (
                self.solar_system_sov_alliance_id(eve_solar_system) == alliance_id
            )

    def solar_system_sov_alliance_id(self, eve_solar_system) -> Optional[int]:
        """returns ID of sov owning alliance for this system or None"""
        if not eve_solar_system.is_null_sec:
            return None
        try:
            sov_map = self.get(solar_system_id=eve_solar_system.id)
            return sov_map.alliance_id if sov_map.alliance_id else None
        except self.model.DoesNotExist:
            return None


class NotificationBaseQuerySet(models.QuerySet):
    def annotate_can_be_rendered(self) -> models.QuerySet:
        """annotates field indicating if a notification can be rendered"""
        from .models import NotificationType

        return self.annotate(
            can_be_rendered_2=Case(
                When(notif_type__in=NotificationType.values, then=True),
                default=Value(False),
                output_field=models.BooleanField(),
            )
        )


class NotificationBaseManagerBase(models.Manager):
    def add_or_remove_timers(self):
        """Add or remove timers from notifications."""
        from .models import NotificationType

        cutoff_dt_for_stale = now() - dt.timedelta(
            hours=STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
        )
        notifications = (
            self.filter(notif_type__in=NotificationType.relevant_for_timerboard)
            .exclude(is_timer_added=True)
            .filter(timestamp__gte=cutoff_dt_for_stale)
            .select_related("owner")
            .order_by("timestamp")
        )
        if notifications.exists():
            for notification in notifications:
                notification.add_or_remove_timer()


class NotificationQuerySet(NotificationBaseQuerySet):
    pass


class NotificationManagerBase(NotificationBaseManagerBase):
    pass


NotificationManager = NotificationManagerBase.from_queryset(NotificationQuerySet)


class GeneratedNotificationQuerySet(NotificationBaseQuerySet):
    pass


class GeneratedNotificationManagerBase(NotificationBaseManagerBase):
    def get_or_create_from_structure(
        self, structure: models.Model, notif_type: models.TextChoices
    ) -> Tuple[ModelType, bool]:
        """Get or create an object from given structure."""
        from .models import NotificationType

        if notif_type not in {NotificationType.TOWER_REINFORCED_EXTRA}:
            raise ValueError(f"Unsupported notification type: {notif_type}")

        return self._get_or_create_tower_reinforced(structure)

    def _get_or_create_tower_reinforced(self, structure) -> Tuple[ModelType, bool]:
        from .models import NotificationType

        if not structure.is_starbase:
            raise ValueError(f"Structure is not a starbase: {structure}")
        if not structure.is_reinforced:
            raise ValueError(f"Starbase is not reinforced: {structure}")
        if not structure.state_timer_end:
            raise ValueError(f"Starbase has no reinforce time: {structure}")
        reinforced_until = structure.state_timer_end.isoformat()
        with transaction.atomic():
            try:
                obj = self.get(
                    structures=structure,
                    notif_type=NotificationType.TOWER_REINFORCED_EXTRA,
                    details__reinforced_until=reinforced_until,
                )
                created = False
            except self.model.DoesNotExist:
                obj = self.create(
                    owner=structure.owner,
                    notif_type=NotificationType.TOWER_REINFORCED_EXTRA,
                    details={"reinforced_until": reinforced_until},
                )
                obj.structures.add(structure)
                created = True
        return obj, created


GeneratedNotificationManager = GeneratedNotificationManagerBase.from_queryset(
    GeneratedNotificationQuerySet
)


class OwnerQuerySet(models.QuerySet):
    def annotate_characters_count(self) -> models.QuerySet:
        return self.annotate(
            x_characters_count=Count(
                "characters",
                filter=Q(characters__character_ownership__isnull=False),
                distinct=True,
            )
        )

    def structures_last_updated(self) -> Optional[dt.datetime]:
        """Date/time when structures were last updated for any of the active owners."""
        obj = self.filter(is_active=True).order_by("-structures_last_update_at").first()
        if not obj:
            return None
        return obj.structures_last_update_at


class OwnerManagerBase(models.Manager):
    pass


OwnerManager = OwnerManagerBase.from_queryset(OwnerQuerySet)


class StructureQuerySet(models.QuerySet):
    def filter_upwell_structures(self) -> models.QuerySet:
        return self.filter(eve_type__eve_group__eve_category=EveCategoryId.STRUCTURE)

    def filter_customs_offices(self) -> models.QuerySet:
        return self.filter(eve_type=EveTypeId.CUSTOMS_OFFICE)

    def filter_starbases(self) -> models.QuerySet:
        return self.filter(eve_type__eve_group__eve_category=EveCategoryId.STARBASE)

    def ids(self) -> Set[int]:
        """Return ids as set."""
        return set(self.values_list("id", flat=True))

    def select_related_defaults(self) -> models.QuerySet:
        """returns a QuerySet with the default select_related"""
        return self.select_related(
            "owner",
            "owner__corporation",
            "owner__corporation__alliance",
            "eve_type",
            "eve_solar_system",
            "eve_solar_system__eve_constellation__eve_region",
            "eve_planet",
            "eve_moon",
            "eve_type__eve_group",
            "eve_type__eve_group__eve_category",
        )

    # TODO: Add specific tests
    def visible_for_user(
        self, user: User, tags: Optional[list] = None
    ) -> models.QuerySet:
        if user.has_perm("structures.view_all_structures"):
            structures_query = self.select_related_defaults()
            if tags:
                structures_query = structures_query.filter(
                    tags__name__in=tags
                ).distinct()

        else:
            if user.has_perm("structures.view_corporation_structures") or user.has_perm(
                "structures.view_alliance_structures"
            ):
                corporation_ids = {
                    character_ownership.character.corporation_id
                    for character_ownership in user.character_ownerships.all()  # type: ignore
                }
                corporations = list(
                    EveCorporationInfo.objects.select_related("alliance").filter(
                        corporation_id__in=corporation_ids
                    )
                )
            else:
                corporations = []

            if user.has_perm("structures.view_alliance_structures"):
                alliances = {
                    corporation.alliance
                    for corporation in corporations
                    if corporation.alliance
                }
                for alliance in alliances:
                    corporations += alliance.evecorporationinfo_set.all()

                corporations = list(set(corporations))

            structures_query = self.select_related_defaults().filter(
                owner__corporation__in=corporations
            )
        return structures_query

    def annotate_has_poco_details(self) -> models.QuerySet:
        from .models import PocoDetails

        return self.annotate(
            has_poco_details=Exists(
                PocoDetails.objects.filter(structure_id=OuterRef("id"))
            )
        )

    def annotate_has_starbase_detail(self) -> models.QuerySet:
        from .models import StarbaseDetail

        return self.annotate(
            has_starbase_detail=Exists(
                StarbaseDetail.objects.filter(structure_id=OuterRef("id"))
            )
        )


class StructureManagerBase(models.Manager):
    def get_or_create_esi(self, *, id: int, token: Token) -> tuple:
        """get or create a structure with data from ESI if needed.

        Args:
            id: Structure ID of object in Eve Online
            token: ``esi.models.Token`` object with scope:
                ``esi-universe.read_structures.v1``

        Returns:
            object, created
        """
        id = int(id)
        try:
            obj = self.get(id=id)
            return obj, False
        except self.model.DoesNotExist:
            return self.update_or_create_esi(id=id, token=token)

    def update_or_create_esi(self, *, id: int, token: Token) -> tuple:
        """update or create a structure from ESI for given structure ID
        This will only fetch basic info about a structure

        Args:
            id: Structure ID of object in Eve Online
            token: ``esi.models.Token`` object with scope: ``esi-universe.read_structures.v1``

        Returns:
            object, created
        """
        from .models import Owner

        id = int(id)
        logger.info("Trying to fetch structure from ESI with ID %s", id)
        if token is None:
            raise ValueError("Can not fetch structure without token")

        structure_info = esi.client.Universe.get_universe_structures_structure_id(
            structure_id=id, token=token.valid_access_token()
        ).results()
        structure = {
            "structure_id": id,
            "name": self.model.extract_name_from_esi_response(structure_info["name"]),
            "position": structure_info["position"],
            "type_id": structure_info["type_id"],
            "system_id": structure_info["solar_system_id"],
        }
        owner = Owner.objects.get(
            corporation__corporation_id=structure_info["corporation_id"]
        )
        obj, created = self.update_or_create_from_dict(structure=structure, owner=owner)
        return obj, created

    def update_or_create_from_dict(self, structure: dict, owner) -> tuple:
        """update or create structure from given dict"""

        from .models import StructureService

        eve_type, _ = EveType.objects.get_or_create_esi(id=structure["type_id"])
        eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=structure["system_id"]
        )
        if position := structure.get("position"):
            position_x = position.get("x")
            position_y = position.get("y")
            position_z = position.get("z")
        else:
            position_x = position_y = position_z = None
        if planet_id := structure.get("planet_id"):
            eve_planet, _ = EvePlanet.objects.get_or_create_esi(id=planet_id)
        else:
            eve_planet = None
        if moon_id := structure.get("moon_id"):
            eve_moon, _ = EveMoon.objects.get_or_create_esi(id=moon_id)
        else:
            eve_moon = None

        structure_id = structure["structure_id"]
        try:
            old_obj = self.get(id=structure_id)
        except self.model.DoesNotExist:
            old_obj = None

        obj, created = self.update_or_create(
            id=structure_id,
            defaults={
                "owner": owner,
                "eve_type": eve_type,
                "name": structure.get("name", ""),
                "eve_solar_system": eve_solar_system,
                "eve_planet": eve_planet,
                "eve_moon": eve_moon,
                "position_x": position_x,
                "position_y": position_y,
                "position_z": position_z,
                "fuel_expires_at": structure.get("fuel_expires"),
                "next_reinforce_hour": structure.get("next_reinforce_hour"),
                "next_reinforce_apply": structure.get("next_reinforce_apply"),
                "reinforce_hour": structure.get("reinforce_hour"),
                "state": self.model.State.from_esi_name(structure.get("state", "")),
                "state_timer_start": structure.get("state_timer_start"),
                "state_timer_end": structure.get("state_timer_end"),
                "unanchors_at": structure.get("unanchors_at"),
                "last_updated_at": now(),
            },
        )

        if old_obj:
            obj.handle_fuel_notifications(old_obj)

        # Make sure we have dogmas loaded for this type for fittings
        EveType.objects.get_or_create_esi(
            id=structure["type_id"], enabled_sections=[EveType.Section.DOGMAS]
        )

        # save related structure services
        StructureService.objects.filter(structure=obj).delete()
        if "services" in structure and structure["services"]:
            for service in structure["services"]:
                service_state = StructureService.State.from_esi_name(service["state"])
                args = {
                    "structure": obj,
                    "name": service["name"],
                    "state": service_state,
                }
                StructureService.objects.create(**args)

        if obj.services.filter(state=StructureService.State.ONLINE).exists():
            obj.last_online_at = now()
            obj.save()

        return obj, created


StructureManager = StructureManagerBase.from_queryset(StructureQuerySet)


class StructureTagManager(models.Manager):
    def get_or_create_for_space_type(self, solar_system) -> tuple:
        from .models import EveSpaceType

        space_type = EveSpaceType.from_solar_system(solar_system)
        params = self.model.SPACE_TYPE_MAP.get(space_type)
        if params:
            try:
                obj = self.get(name=params["name"])
                return obj, False
            except self.model.DoesNotExist:
                return self.update_or_create_for_space_type(solar_system)
        return None, None

    def update_or_create_for_space_type(self, solar_system) -> tuple:
        from .models import EveSpaceType

        space_type = EveSpaceType.from_solar_system(solar_system)
        params = self.model.SPACE_TYPE_MAP.get(space_type)
        if params:
            return self.update_or_create(
                name=params["name"],
                defaults={
                    "style": params["style"],
                    "description": (
                        "this tag represents a space type. system generated."
                    ),
                    "order": 50,
                    "is_user_managed": False,
                    "is_default": False,
                },
            )
        return None, None

    def get_or_create_for_sov(self) -> tuple:
        try:
            obj = self.get(name=self.model.NAME_SOV_TAG)
            return obj, False
        except self.model.DoesNotExist:
            return self.update_or_create_for_sov()

    def update_or_create_for_sov(self) -> tuple:
        return self.update_or_create(
            name=self.model.NAME_SOV_TAG,
            defaults={
                "style": self.model.Style.DARK_BLUE,
                "description": (
                    "Owner of this structure has sovereignty. system generated."
                ),
                "order": 20,
                "is_user_managed": False,
                "is_default": False,
            },
        )


class WebhookManager(WebhookBaseManager):
    def enabled_notification_types(self) -> Set[str]:
        """Set of all currently enabled notification types."""
        notif_types_list = list(
            self.filter(is_active=True).values_list("notification_types", flat=True)
        )
        return set(itertools.chain(*notif_types_list))
