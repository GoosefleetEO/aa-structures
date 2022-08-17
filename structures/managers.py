import datetime as dt
import itertools
from pydoc import locate
from typing import Tuple

from bravado.exception import HTTPError

from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Case, Count, Exists, OuterRef, Q, Value, When
from django.utils.timezone import now
from esi.models import Token

from allianceauth.eveonline.models import EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
from .constants import EveCategoryId, EveTypeId
from .helpers.esi_fetch import esi_fetch, esi_fetch_with_localization
from .providers import esi
from .webhooks.managers import WebhookBaseManager

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def make_log_prefix(model_manager, id):
    return f"{model_manager.model.__name__}(id={id})"


class EveUniverseManager(models.Manager):
    def get_or_create_esi(self, *, id: int) -> tuple:
        """gets or creates eve universe object fetched from ESI if needed.
        Will always get/create parent objects.

        id: Eve Online ID of object

        Returns: object, created
        """
        id = int(id)
        try:
            obj = self.get(id=id)
            created = False
        except self.model.DoesNotExist:
            obj, created = self.update_or_create_esi(id=id)

        return obj, created

    def update_or_create_esi(self, *, id: int) -> tuple:
        """updates or creates Eve Universe object with data fetched from ESI.
        Will always update/create children and get/create parent objects.

        id: Eve Online ID of object

        Returns: object, created
        """
        from .models import EsiNameLocalization

        id = int(id)
        esi_path = "Universe." + self.model.esi_method()
        args = {self.model.esi_pk(): id}
        if self.model.has_esi_localization():
            eve_data_objects = esi_fetch_with_localization(
                esi_path=esi_path,
                languages=EsiNameLocalization.ESI_LANGUAGES,
                args=args,
            )
        else:
            eve_data_objects = dict()
            eve_data_objects[EsiNameLocalization.ESI_DEFAULT_LANGUAGE] = esi_fetch(
                esi_path=esi_path, args=args
            )  # noqa E123
        defaults = self.model.map_esi_fields_to_model(eve_data_objects)
        obj, created = self.update_or_create(id=id, defaults=defaults)
        obj.set_generated_translations()
        obj.save()
        self._update_or_create_children(eve_data_objects)
        return obj, created

    def _update_or_create_children(self, eve_data_objects: dict) -> None:
        """updates or creates child objects if specified"""
        eve_data_obj = eve_data_objects[self.model.ESI_DEFAULT_LANGUAGE]
        for key, child_class in self.model.child_mappings().items():
            ChildClass = locate(__package__ + ".models." + child_class)
            for eve_data_obj_2 in eve_data_obj[key]:
                id = eve_data_obj_2[ChildClass.esi_pk()]
                ChildClass.objects.update_or_create_esi(id=id)

    def update_all_esi(self) -> int:
        """update all objects from ESI. Returns count of updated  objects"""
        logger.info(
            "%s: Updating %d objects from from ESI...",
            self.model.__name__,
            self.count(),
        )
        count_updated = 0
        for eve_obj in self.all().order_by("last_updated"):
            try:
                self.update_or_create_esi(id=eve_obj.id)
                count_updated += 1
            except HTTPError:
                logger.exception("Update interrupted by exception")

        return count_updated


class EveEntityManager(models.Manager):
    def get_or_create_esi(self, *, id: int) -> tuple:
        """gets or creates EveEntity obj with data fetched from ESI if needed

        Args:
            id: Eve Online ID of object

        Returns: object, created
        """
        id = int(id)
        try:
            obj = self.get(id=id)
            created = False
        except self.model.DoesNotExist:
            obj, created = self.update_or_create_esi(id=id)

        return obj, created

    def update_or_create_esi(self, *, id: int) -> tuple:
        """updates or creates EveEntity object with data fetched from ESI

        Args:
            id: Eve Online ID of object

        Returns: object, created
        """
        id = int(id)
        log_prefix = make_log_prefix(self, id)
        response = esi_fetch(
            esi_path="Universe.post_universe_names",
            args={"ids": [id]},
        )
        if len(response) > 0:
            first = response[0]
            category = self.model.Category.from_esi_name(first["category"])
            obj, created = self.update_or_create(
                id=id,
                defaults={"category": category, "name": first["name"]},
            )
        else:
            raise ValueError(f"{log_prefix}: Did not find a match")

        return obj, created


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
        self, eve_solar_system: models.Model, corporation: EveCorporationInfo
    ) -> bool:
        """returns true if given corporation has sov in this solar system
        else False
        """
        if not eve_solar_system.is_null_sec:
            return None
        else:
            alliance_id = (
                int(corporation.alliance.alliance_id) if corporation.alliance else None
            )
            return alliance_id and (
                self.solar_system_sov_alliance_id(eve_solar_system) == alliance_id
            )

    def solar_system_sov_alliance_id(self, eve_solar_system: models.Model) -> int:
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
    ) -> Tuple[models.Model, bool]:
        """Get or create an object from given structure."""
        from .models import NotificationType

        if notif_type not in {NotificationType.TOWER_REINFORCED_EXTRA}:
            raise ValueError(f"Unsupported notification type: {notif_type}")

        return self._get_or_create_tower_reinforced(structure)

    def _get_or_create_tower_reinforced(
        self, structure: models.Model
    ) -> Tuple[models.Model, bool]:
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

    def structures_last_updated(self):
        """Date/time when structures were last updated for any of the active owners."""
        active_owners = self.filter(is_active=True)
        return (
            (
                active_owners.order_by("-structures_last_update_at")
                .first()
                .structures_last_update_at
            )
            if active_owners
            else None
        )


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

    def ids(self) -> set():
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
    def visible_for_user(self, user: User, tags: list = None) -> models.QuerySet:
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
                    for character_ownership in user.character_ownerships.all()
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

    def update_or_create_from_dict(self, structure: dict, owner: object) -> tuple:
        """update or create structure from given dict"""
        from eveuniverse.models import EveType as EveUniverseType

        from .models import (
            EveMoon,
            EvePlanet,
            EveSolarSystem,
            EveType,
            StructureService,
        )
        from .models.eveuniverse import EveUniverse

        eve_type, _ = EveType.objects.get_or_create_esi(id=structure["type_id"])
        eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=structure["system_id"]
        )
        fuel_expires_at = (
            structure["fuel_expires"] if "fuel_expires" in structure else None
        )
        next_reinforce_hour = (
            structure["next_reinforce_hour"]
            if "next_reinforce_hour" in structure
            else None
        )
        next_reinforce_apply = (
            structure["next_reinforce_apply"]
            if "next_reinforce_apply" in structure
            else None
        )
        reinforce_hour = (
            structure["reinforce_hour"] if "reinforce_hour" in structure else None
        )
        state = (
            self.model.State.from_esi_name(structure["state"])
            if "state" in structure
            else self.model.State.UNKNOWN
        )
        state_timer_start = (
            structure["state_timer_start"] if "state_timer_start" in structure else None
        )
        state_timer_end = (
            structure["state_timer_end"] if "state_timer_end" in structure else None
        )
        unanchors_at = (
            structure["unanchors_at"] if "unanchors_at" in structure else None
        )
        position_x = structure["position"]["x"] if "position" in structure else None
        position_y = structure["position"]["y"] if "position" in structure else None
        position_z = structure["position"]["z"] if "position" in structure else None
        if "planet_id" in structure:
            eve_planet, _ = EvePlanet.objects.get_or_create_esi(
                id=structure["planet_id"]
            )
        else:
            eve_planet = None
        if "moon_id" in structure:
            eve_moon, _ = EveMoon.objects.get_or_create_esi(id=structure["moon_id"])
        else:
            eve_moon = None
        try:
            old_obj = self.get(id=structure["structure_id"])
        except self.model.DoesNotExist:
            old_obj = None
        obj, created = self.update_or_create(
            id=structure["structure_id"],
            defaults={
                "owner": owner,
                "eve_type": eve_type,
                "name": structure["name"],
                "eve_solar_system": eve_solar_system,
                "eve_planet": eve_planet,
                "eve_moon": eve_moon,
                "position_x": position_x,
                "position_y": position_y,
                "position_z": position_z,
                "fuel_expires_at": fuel_expires_at,
                "next_reinforce_hour": next_reinforce_hour,
                "next_reinforce_apply": next_reinforce_apply,
                "reinforce_hour": reinforce_hour,
                "state": state,
                "state_timer_start": state_timer_start,
                "state_timer_end": state_timer_end,
                "unanchors_at": unanchors_at,
                "last_updated_at": now(),
            },
        )
        if old_obj:
            obj.handle_fuel_notifications(old_obj)
        # Make sure we have dogmas loaded for this type for fittings
        EveUniverseType.objects.get_or_create_esi(
            id=structure["type_id"], enabled_sections=[EveUniverseType.Section.DOGMAS]
        )
        # save related structure services
        StructureService.objects.filter(structure=obj).delete()
        if "services" in structure and structure["services"]:
            for service in structure["services"]:
                state = StructureService.State.from_esi_name(service["state"])
                args = {"structure": obj, "name": service["name"], "state": state}
                for lang in EveUniverse.ESI_LANGUAGES:
                    if lang != EveUniverse.ESI_DEFAULT_LANGUAGE:
                        field_name = "name_%s" % lang
                        if field_name in service:
                            args[field_name] = service[field_name]

                StructureService.objects.create(**args)

        if obj.services.filter(state=StructureService.State.ONLINE).exists():
            obj.last_online_at = now()
            obj.save()

        return obj, created


StructureManager = StructureManagerBase.from_queryset(StructureQuerySet)


class StructureTagManager(models.Manager):
    def get_or_create_for_space_type(self, solar_system: models.Model) -> tuple:
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

    def update_or_create_for_space_type(self, solar_system: object) -> tuple:
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
    def enabled_notification_types(self) -> set:
        """Set of all currently enabled notification types."""
        notif_types_list = list(
            self.filter(is_active=True).values_list("notification_types", flat=True)
        )
        return set(itertools.chain(*notif_types_list))
