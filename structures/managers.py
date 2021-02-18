from pydoc import locate

from bravado.exception import HTTPError

from django.db import models, transaction
from django.db.models import Case, When, Value
from django.utils.timezone import now

from allianceauth.services.hooks import get_extension_logger

from esi.models import Token

from . import __title__
from .helpers.esi_fetch import esi_fetch_with_localization, esi_fetch
from app_utils.logging import LoggerAddTag, make_logger_prefix


logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class EveUniverseManager(models.Manager):
    def get_or_create_esi(self, eve_id: int) -> tuple:
        """gets or creates eve universe object fetched from ESI if needed.
        Will always get/create parent objects.

        eve_id: Eve Online ID of object

        Returns: object, created
        """
        eve_id = int(eve_id)
        try:
            obj = self.get(id=eve_id)
            created = False
        except self.model.DoesNotExist:
            obj, created = self.update_or_create_esi(eve_id)

        return obj, created

    def update_or_create_esi(self, eve_id: int) -> tuple:
        """updates or creates Eve Universe object with data fetched from ESI.
        Will always update/create children and get/create parent objects.

        eve_id: Eve Online ID of object

        Returns: object, created
        """
        from .models import EsiNameLocalization

        eve_id = int(eve_id)
        add_prefix = make_logger_prefix("%s(id=%d)" % (self.model.__name__, eve_id))
        try:
            esi_path = "Universe." + self.model.esi_method()
            args = {self.model.esi_pk(): eve_id}
            if self.model.has_esi_localization():
                eve_data_objects = esi_fetch_with_localization(
                    esi_path=esi_path,
                    languages=EsiNameLocalization.ESI_LANGUAGES,
                    args=args,
                    logger_tag=add_prefix(),
                )
            else:
                eve_data_objects = dict()
                eve_data_objects[EsiNameLocalization.ESI_DEFAULT_LANGUAGE] = esi_fetch(
                    esi_path=esi_path, args=args, logger_tag=add_prefix()
                )  # noqa E123
            defaults = self.model.map_esi_fields_to_model(eve_data_objects)
            obj, created = self.update_or_create(id=eve_id, defaults=defaults)
            obj.set_generated_translations()
            obj.save()
            self._update_or_create_children(eve_data_objects)

        except Exception as ex:
            logger.warn(add_prefix("Failed to update or create: %s" % ex))
            raise ex

        return obj, created

    def _update_or_create_children(self, eve_data_objects: dict) -> None:
        """updates or creates child objects if specified"""
        eve_data_obj = eve_data_objects[self.model.ESI_DEFAULT_LANGUAGE]
        for key, child_class in self.model.child_mappings().items():
            ChildClass = locate(__package__ + ".models." + child_class)
            for eve_data_obj_2 in eve_data_obj[key]:
                eve_id = eve_data_obj_2[ChildClass.esi_pk()]
                ChildClass.objects.update_or_create_esi(eve_id)

    def update_all_esi(self) -> int:
        """update all objects from ESI. Returns count of updated  objects"""
        logger.info(
            "%s: Updating %d objects from from ESI..."
            % (self.model.__name__, self.count())
        )
        count_updated = 0
        for eve_obj in self.all().order_by("last_updated"):
            try:
                self.update_or_create_esi(eve_obj.id)
                count_updated += 1
            except HTTPError as ex:
                logger.exception("Update interrupted by exception: %s" % ex)

        return count_updated


class EveSovereigntyMapManager(models.Manager):
    def update_from_esi(self):
        logger.info("Fetching sovereignty map from ESI...")
        sov_map = esi_fetch("Sovereignty.get_sovereignty_map", args={})
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


class EveEntityManager(models.Manager):
    def get_or_create_esi(self, eve_entity_id: int) -> tuple:
        """gets or creates EveEntity obj with data fetched from ESI if needed

        eve_id: Eve Online ID of object

        Returns: object, created
        """
        eve_entity_id = int(eve_entity_id)
        try:
            obj = self.get(id=eve_entity_id)
            created = False
        except self.model.DoesNotExist:
            obj, created = self.update_or_create_esi(eve_entity_id)

        return obj, created

    def update_or_create_esi(self, eve_entity_id: int) -> tuple:
        """updates or creates EveEntity object with data fetched from ESI

        eve_id: Eve Online ID of object

        Returns: object, created
        """
        eve_entity_id = int(eve_entity_id)
        add_prefix = make_logger_prefix(
            "%s(id=%s)" % (self.model.__name__, eve_entity_id)
        )
        try:
            response = esi_fetch(
                esi_path="Universe.post_universe_names",
                args={"ids": [eve_entity_id]},
                logger_tag=add_prefix(),
            )
            if len(response) > 0:
                first = response[0]
                category = self.model.get_matching_entity_category(first["category"])
                obj, created = self.update_or_create(
                    id=eve_entity_id,
                    defaults={"category": category, "name": first["name"]},
                )
            else:
                raise ValueError(add_prefix("Did not find a match"))

        except Exception as ex:
            logger.warn(add_prefix("Failed to load eve entity: %s" % ex))
            raise ex

        return obj, created


class StructureManager(models.Manager):
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
        )

    def get_or_create_esi(self, structure_id: int, token: Token) -> tuple:
        """get or create a structure with data from ESI if needed

        structure_id: Structure ID of object in Eve Online

        token: ``esi.models.Token`` object with scope:
        ``esi-universe.read_structures.v1``

        Returns: object, created
        """
        try:
            obj = self.get(id=structure_id)
            created = False
        except self.model.DoesNotExist:
            obj, created = self.update_or_create_esi(structure_id, token)
        return obj, created

    def update_or_create_esi(self, structure_id: int, token: Token) -> tuple:
        """update or create a structure from ESI for given structure ID
        This will only fetch basic info about a structure

        structure_id: Structure ID of object in Eve Online

        token: ``esi.models.Token`` object with scope:
        ``esi-universe.read_structures.v1``

        Returns: object, created
        """
        from .models import Owner

        add_prefix = make_logger_prefix(
            "%s(id=%d)" % (self.model.__name__, structure_id)
        )
        logger.info(add_prefix("Trying to fetch structure from ESI"))

        try:
            if token is None:
                raise ValueError("Can not fetch structure without token")

            structure_info = esi_fetch(
                esi_path="Universe.get_universe_structures_structure_id",
                args={"structure_id": structure_id},
                token=token,
                logger_tag=add_prefix(),
            )
            structure = {
                "structure_id": structure_id,
                "name": self.model.extract_name_from_esi_respose(
                    structure_info["name"]
                ),
                "position": structure_info["position"],
                "type_id": structure_info["type_id"],
                "system_id": structure_info["solar_system_id"],
            }
            owner = Owner.objects.get(
                corporation__corporation_id=structure_info["corporation_id"]
            )
            obj, created = self.update_or_create_from_dict(
                structure=structure, owner=owner
            )

        except Exception as ex:
            logger.warn(add_prefix("Failed to load structure: {}".format(ex)))
            raise ex

        return obj, created

    def update_or_create_from_dict(self, structure: dict, owner: object) -> tuple:
        """update or create structure from given dict"""
        from .models import (
            EveType,
            EveSolarSystem,
            StructureService,
            EvePlanet,
            EveMoon,
        )
        from .models.eveuniverse import EveUniverse

        eve_type, _ = EveType.objects.get_or_create_esi(structure["type_id"])
        eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            structure["system_id"]
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
            self.model.get_matching_state_for_esi_state(structure["state"])
            if "state" in structure
            else self.model.STATE_UNKNOWN
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
            eve_planet, _ = EvePlanet.objects.get_or_create_esi(structure["planet_id"])
        else:
            eve_planet = None

        if "moon_id" in structure:
            eve_moon, _ = EveMoon.objects.get_or_create_esi(structure["moon_id"])
        else:
            eve_moon = None

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
        # save related structure services
        StructureService.objects.filter(structure=obj).delete()
        if "services" in structure and structure["services"]:
            for service in structure["services"]:
                state = StructureService.get_matching_state_for_esi_state(
                    service["state"]
                )
                args = {"structure": obj, "name": service["name"], "state": state}
                for lang in EveUniverse.ESI_LANGUAGES:
                    if lang != EveUniverse.ESI_DEFAULT_LANGUAGE:
                        field_name = "name_%s" % lang
                        if field_name in service:
                            args[field_name] = service[field_name]

                StructureService.objects.create(**args)

        if obj.structureservice_set.filter(
            state=StructureService.STATE_ONLINE
        ).exists():
            obj.last_online_at = now()
            obj.save()

        return obj, created


class StructureTagManager(models.Manager):
    def get_or_create_for_space_type(self, solar_system: object) -> tuple:
        if solar_system.space_type in self.model.SPACE_TYPE_MAP:
            name = self.model.SPACE_TYPE_MAP[solar_system.space_type]["name"]
        else:
            name = None

        if name:
            try:
                obj = self.get(name=name)
                created = False
            except self.model.DoesNotExist:
                obj, created = self.update_or_create_for_space_type(solar_system)

        else:
            obj = None
            created = None

        return obj, created

    def update_or_create_for_space_type(self, solar_system: object) -> tuple:
        if solar_system.space_type in self.model.SPACE_TYPE_MAP:
            params = self.model.SPACE_TYPE_MAP[solar_system.space_type]
        else:
            params = None

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
        else:
            return None, None

    def get_or_create_for_sov(self) -> tuple:
        try:
            obj = self.get(name=self.model.NAME_SOV_TAG)
            created = False
        except self.model.DoesNotExist:
            obj, created = self.update_or_create_for_sov()

        return obj, created

    def update_or_create_for_sov(self) -> tuple:
        obj, created = self.update_or_create(
            name=self.model.NAME_SOV_TAG,
            defaults={
                "style": self.model.STYLE_DARK_BLUE,
                "description": (
                    "Owner of this structure has sovereignty. system generated."
                ),
                "order": 20,
                "is_user_managed": False,
                "is_default": False,
            },
        )
        return obj, created


class NotificationQuerySet(models.QuerySet):
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


class NotificationManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return NotificationQuerySet(self.model, using=self._db)
