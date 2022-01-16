"""Owner related models"""
import json
import math
import os
import re
from datetime import datetime, timedelta
from email.utils import format_datetime, parsedate_to_datetime
from typing import Optional

from bravado.exception import HTTPForbidden

from django.contrib.auth.models import Group, User
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from esi.errors import TokenError
from esi.models import Token

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCorporationInfo
from allianceauth.notifications import notify
from allianceauth.services.hooks import get_extension_logger
from app_utils.allianceauth import notify_admins
from app_utils.datetime import DATETIME_FORMAT
from app_utils.helpers import chunks
from app_utils.logging import LoggerAddTag

from .. import __title__
from ..app_settings import (
    STRUCTURES_ADD_TIMERS,
    STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED,
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_DEVELOPER_MODE,
    STRUCTURES_FEATURE_CUSTOMS_OFFICES,
    STRUCTURES_FEATURE_STARBASES,
    STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION,
    STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES,
    STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED,
    STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES,
)
from ..constants import EveGroupId, EveTypeId
from ..helpers.esi_fetch import _esi_client, esi_fetch, esi_fetch_with_localization
from ..managers import OwnerManager
from .eveuniverse import EveMoon, EvePlanet, EveSolarSystem, EveType, EveUniverse
from .notifications import EveEntity, Notification, NotificationType, Webhook
from .structures import PocoDetails, Structure, StructureItem

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class General(models.Model):
    """Meta model for global app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("basic_access", "Can access this app and view public pages"),
            ("view_corporation_structures", "Can view corporation structures"),
            ("view_alliance_structures", "Can view alliance structures"),
            ("view_all_structures", "Can view all structures"),
            ("add_structure_owner", "Can add new structure owner"),
            (
                "view_all_unanchoring_status",
                "Can view unanchoring timers for all structures the user can see",
            ),
            ("view_structure_fit", "Can view structure fit"),
        )


class Owner(models.Model):
    """A corporation that owns structures"""

    class RotateCharactersType(models.TextChoices):
        """Type of sync to rotate characters for."""

        STRUCTURES = "structures"
        NOTIFICATIONS = "notifications"

        @property
        def last_used_at_name(self) -> str:
            """Name of last used at property."""
            if self is self.STRUCTURES:
                return "structures_last_used_at"
            elif self is self.NOTIFICATIONS:
                return "notifications_last_used_at"
            raise NotImplementedError(f"Not defined for: {self}")

        @property
        def esi_cache_duration(self) -> int:
            """ESI cache duration in seconds."""
            if self is self.STRUCTURES:
                return 3600
            elif self is self.NOTIFICATIONS:
                return 600
            raise NotImplementedError(f"Not defined for: {self}")

    # PK
    corporation = models.OneToOneField(
        EveCorporationInfo,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="structure_owner",
        help_text="Corporation owning structures",
    )
    # regular
    are_pocos_public = models.BooleanField(
        default=False,
        help_text=("whether pocos of this owner are shown on public POCO page"),
    )
    assets_last_update_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="when the last successful update happened",
    )
    character_ownership = models.ForeignKey(
        CharacterOwnership,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
        help_text="OUTDATED. Has been replaced by OwnerCharacter",
    )
    forwarding_last_update_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="when the last successful update happened",
    )
    has_default_pings_enabled = models.BooleanField(
        default=True,
        help_text=(
            "to enable or disable pinging of notifications for this owner "
            "e.g. with @everyone and @here"
        ),
    )
    is_active = models.BooleanField(
        default=True,
        help_text=("whether this owner is currently included in the sync process"),
    )
    is_alliance_main = models.BooleanField(
        default=False,
        help_text=(
            "whether alliance wide notifications "
            "are forwarded for this owner (e.g. sov notifications)"
        ),
    )
    is_included_in_service_status = models.BooleanField(
        default=True,
        help_text=(
            "whether the sync status of this owner is included in "
            "the overall status of this services"
        ),
    )
    is_up = models.BooleanField(
        null=True,
        default=None,
        editable=False,
        help_text="whether all services for this owner are currently up",
    )
    notifications_last_update_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="when the last successful update happened",
    )
    ping_groups = models.ManyToManyField(
        Group,
        default=None,
        blank=True,
        help_text="Groups to be pinged for each notification - ",
    )
    structures_last_update_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="when the last successful update happened",
    )
    webhooks = models.ManyToManyField(
        "Webhook",
        default=None,
        blank=True,
        help_text="notifications are sent to these webhooks. ",
    )

    objects = OwnerManager()

    def __str__(self) -> str:
        return str(self.corporation.corporation_name)

    def __repr__(self):
        return "{}(pk={}, corporation='{}')".format(
            self.__class__.__name__, self.pk, self.corporation
        )

    def save(self, *args, **kwargs) -> None:
        if self.is_alliance_main:
            Owner.objects.filter(
                corporation__alliance_id=self.corporation.alliance_id
            ).exclude(corporation__alliance_id__isnull=True).update(
                is_alliance_main=False
            )
            if "update_fields" in kwargs:
                kwargs["update_fields"].append("is_alliance_main")
        super().save(*args, **kwargs)

    @property
    def is_structure_sync_fresh(self) -> bool:
        """True if last sync happened with grace time, else False."""
        return self.structures_last_update_at and self.structures_last_update_at > (
            now() - timedelta(minutes=STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES)
        )

    @property
    def is_notification_sync_fresh(self) -> bool:
        """True if last sync happened with grace time, else False."""
        return (
            self.notifications_last_update_at
            and self.notifications_last_update_at
            > (now() - timedelta(minutes=STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES))
        )

    @property
    def is_forwarding_sync_fresh(self) -> bool:
        """True if last sync happened with grace time, else False."""
        return self.forwarding_last_update_at and self.forwarding_last_update_at > (
            now() - timedelta(minutes=STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES)
        )

    @property
    def is_assets_sync_fresh(self) -> bool:
        """True if last sync happened with grace time, else False."""
        return self.assets_last_update_at and self.assets_last_update_at > (
            now() - timedelta(minutes=STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES)
        )

    @property
    def are_all_syncs_ok(self) -> bool:
        """returns true if they have been no errors
        and last syncing occurred within alloted time for all sync categories
        """
        return (
            self.is_structure_sync_fresh
            and self.is_notification_sync_fresh
            and self.is_forwarding_sync_fresh
            and self.is_assets_sync_fresh
        )

    def update_is_up(self) -> bool:
        """Check if all services for this owner are up, notify admins if necessary
        and store result.
        """

        def fresh_str(value: bool) -> str:
            return "up" if value else "down"

        is_up = self.are_all_syncs_ok
        if (
            STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED
            and self.is_included_in_service_status
        ):
            if self.is_up and is_up is False:
                title = f"{__title__}: Services are down for {self}"
                msg = (
                    f"Structure services for {self} are down. "
                    "Admin action is likely required to restore services.\n"
                    f"- Structures: {fresh_str(self.is_structure_sync_fresh)}\n"
                    f"- Notifications: {fresh_str(self.is_notification_sync_fresh)}\n"
                    f"- Forwarding: {fresh_str(self.is_forwarding_sync_fresh)}\n"
                    f"- Assets: {fresh_str(self.is_assets_sync_fresh)}\n"
                )
                notify_admins(message=msg, title=title, level="danger")
            elif self.is_up is False and is_up:
                title = f"{__title__}: Services restored for {self}"
                msg = f"Structure services for {self} have been restored. "
                notify_admins(message=msg, title=title, level="success")
            elif self.is_up is None and is_up:
                title = f"{__title__}: Services enabled {self}"
                msg = f"Structure services for {self} have been enabled. "
                notify_admins(message=msg, title=title, level="success")
        if self.is_up != is_up:
            self.is_up = is_up
            self.save(update_fields=["is_up"])
        return is_up

    def add_character(
        self, character_ownership: CharacterOwnership
    ) -> "OwnerCharacter":
        """Add character to this owner.

        Raises ValueError when character does not belong to owner's corporation.
        """
        if (
            character_ownership.character.corporation_id
            != self.corporation.corporation_id
        ):
            raise ValueError(
                f"Character {character_ownership.character} does not belong "
                "to owner corporation."
            )
        obj, _ = self.characters.get_or_create(character_ownership=character_ownership)
        return obj

    def characters_count(self) -> int:
        """Count of valid owner characters."""
        return self.characters.count()

    def fetch_token(
        self,
        rotate_characters: RotateCharactersType = None,
        ignore_schedule: bool = False,
    ) -> Token:
        """Fetch a valid token for the owner and return it.

        Args:
            rotate_characters: For which sync type to rotate through characters \
                with every new call
            ignore_schedule: Ignore current schedule when rotating

        Raises TokenError when no valid token can be provided.
        """
        token = None
        order_by_last_used = (
            rotate_characters.last_used_at_name
            if rotate_characters
            else "notifications_last_used_at"
        )
        for character in self.characters.order_by(order_by_last_used):
            if (
                character.character_ownership.character.corporation_id
                != self.corporation.corporation_id
            ):
                self._delete_character(
                    ("Character does no longer belong to the owner's corporation."),
                    character,
                )
                continue
            elif not character.character_ownership.user.has_perm(
                "structures.add_structure_owner"
            ):
                self._delete_character(
                    "Character does not have sufficient permission to sync.",
                    character,
                )
                continue
            token = character.valid_token()
            if not token:
                self._delete_character(
                    "Character has no valid token for sync.",
                    character,
                )
                continue
            break  # leave the for loop if we have found a valid token

        if not token:
            error = (
                f"{self}: No valid character found for sync. "
                "Service down for this owner."
            )
            raise TokenError(error)
        if rotate_characters:
            self._rotate_character(
                character=character,
                ignore_schedule=ignore_schedule,
                rotate_characters=rotate_characters,
            )
        return token

    def _delete_character(
        self,
        error: str,
        character: CharacterOwnership,
        level="warning",
    ) -> None:
        """Delete character and notify it's owner and admin about the reason

        Args:
        - error: Error text
        - character: Character this error refers to
        - level: context level for the notification
        - delete_character: will delete the character object if set true
        """
        title = f"{__title__}: {self}: Invalid character has been removed"
        error = (
            f"{character.character_ownership}: {error}\n"
            "The character has been removed. "
            "Please add a new character to restore the previous service level."
        )
        notify(
            user=character.character_ownership.user,
            title=title,
            message=error,
            level=level,
        )
        if self.characters.count() == 1:
            error += (
                " This owner has no configured characters anymore "
                "and it's services are now down."
            )
            level = "danger"
        notify_admins(title=f"FYI: {title}", message=error, level=level)
        character.delete()

    def _rotate_character(
        self,
        character: "OwnerCharacter",
        ignore_schedule: bool,
        rotate_characters: RotateCharactersType,
    ) -> None:
        """Rotate this character such that all are spread evently
        accross the ESI cache duration for each ESI call.
        """
        time_since_last_used = (
            (
                now() - getattr(character, rotate_characters.last_used_at_name)
            ).total_seconds()
            if getattr(character, rotate_characters.last_used_at_name)
            else None
        )
        try:
            minimum_time_between_rotations = max(
                rotate_characters.esi_cache_duration / self.characters.count(),
                60,
            )
        except ZeroDivisionError:
            minimum_time_between_rotations = rotate_characters.esi_cache_duration
        if (
            ignore_schedule
            or not time_since_last_used
            or time_since_last_used >= minimum_time_between_rotations
        ):
            setattr(character, rotate_characters.last_used_at_name, now())
            character.save()

    def _report_esi_issue(self, action: str, ex: Exception, token: Token):
        """Report an ESI issue to admins."""
        message = f"{self}: Failed to {action} from ESI with token {token} due to {ex}"
        logger.warning(message, exc_info=True)

    def update_structures_esi(self, user: User = None):
        """Updates all structures from ESI."""
        token = self.fetch_token(rotate_characters=self.RotateCharactersType.STRUCTURES)
        is_ok = self._fetch_upwell_structures(token)
        if STRUCTURES_FEATURE_CUSTOMS_OFFICES:
            is_ok &= self._fetch_custom_offices(token)
        if STRUCTURES_FEATURE_STARBASES:
            is_ok &= self._fetch_starbases(token)

        if is_ok:
            self.structures_last_update_at = now()
            self.save(update_fields=["structures_last_update_at"])
            if user:
                self._send_report_to_user(
                    topic="structures", topic_count=self.structures.count(), user=user
                )

    def _remove_structures_not_returned_from_esi(
        self, structures_qs: models.QuerySet, new_structures: list
    ):
        """Remove structures no longer returned from ESI."""
        ids_local = {x.id for x in structures_qs}
        ids_from_esi = {x["structure_id"] for x in new_structures}
        ids_to_remove = ids_local - ids_from_esi
        if len(ids_to_remove) > 0:
            structures_qs.filter(id__in=ids_to_remove).delete()
            logger.info(
                "Removed %d structures which apparently no longer exist.",
                len(ids_to_remove),
            )

    def _fetch_upwell_structures(self, token: Token) -> bool:
        """Fetch Upwell structures from ESI for self.

        Return True if successful, else False.
        """
        from .eveuniverse import EsiNameLocalization

        corporation_id = self.corporation.corporation_id
        structures = list()
        try:
            # fetch all structures incl. localizations for services
            structures_w_lang = esi_fetch_with_localization(
                esi_path="Corporation.get_corporations_corporation_id_structures",
                args={"corporation_id": corporation_id},
                token=token,
                languages=EsiNameLocalization.ESI_LANGUAGES,
                has_pages=True,
            )
        except OSError as ex:
            self._report_esi_issue("fetch corporation structures", ex, token)
            return False

        is_ok = True
        # reduce data
        structures = self._compress_services_localization(
            structures_w_lang, EveUniverse.ESI_DEFAULT_LANGUAGE
        )

        # fetch additional information for structures
        if not structures:
            logger.info("%s: No Upwell structures retrieved from ESI", self)
        else:
            logger.info(
                "%s: Fetching additional infos for %d Upwell structures from ESI",
                self,
                len(structures),
            )
            for structure in structures:
                try:
                    structure_info = esi_fetch(
                        "Universe.get_universe_structures_structure_id",
                        args={"structure_id": structure["structure_id"]},
                        token=token,
                    )
                    structure["name"] = Structure.extract_name_from_esi_respose(
                        structure_info["name"]
                    )
                    structure["position"] = structure_info["position"]
                except OSError as ex:
                    self._report_esi_issue(
                        f"fetch structure #{structure['structure_id']}", ex, token
                    )
                    structure["name"] = "(no data)"
                    is_ok = False

            logger.info(
                "%s: Storing updates for %d upwell structures",
                self,
                len(structures),
            )
            for structure in structures:
                Structure.objects.update_or_create_from_dict(structure, self)

        if STRUCTURES_DEVELOPER_MODE:
            self._store_raw_data("structures", structures, corporation_id)

        self._remove_structures_not_returned_from_esi(
            structures_qs=self.structures.filter_upwell_structures(),
            new_structures=structures,
        )
        return is_ok

    @staticmethod
    def _compress_services_localization(
        structures_w_lang: dict, default_lang: str
    ) -> list:
        """compress service names localizations for each structure
        We are assuming that services are returned from ESI in the same order
        for each language.
        """
        structures_services = Owner._collect_services_with_localizations(
            structures_w_lang, default_lang
        )
        structures = Owner._condense_services_localizations_into_structures(
            structures_w_lang, default_lang, structures_services
        )
        return structures

    @staticmethod
    def _collect_services_with_localizations(structures_w_lang, default_lang):
        """collect services with name localizations for all structures"""
        structures_services = dict()
        for lang, structures in structures_w_lang.items():
            if lang != default_lang:
                for structure in structures:
                    if "services" in structure and structure["services"]:
                        structure_id = structure["structure_id"]
                        if structure_id not in structures_services:
                            structures_services[structure_id] = dict()
                        structures_services[structure_id][lang] = list()
                        for service in structure["services"]:
                            structures_services[structure_id][lang].append(
                                service["name"]
                            )
        return structures_services

    @staticmethod
    def _condense_services_localizations_into_structures(
        structures_w_lang, default_lang, structures_services
    ):
        """add corresponding service name localizations to structure's services"""
        structures = structures_w_lang[default_lang]
        for structure in structures:
            if "services" in structure and structure["services"]:
                structure_id = structure["structure_id"]
                for lang in structures_w_lang.keys():
                    if (
                        lang != default_lang
                        and lang in structures_services[structure_id]
                    ):
                        for service, name_loc in zip(
                            structure["services"],
                            structures_services[structure_id][lang],
                        ):
                            service["name_" + lang] = name_loc
        return structures

    def _fetch_custom_offices(self, token: Token) -> bool:
        """Fetch custom offices from ESI for this owner.

        Return True when successful, else False.
        """

        corporation_id = self.corporation.corporation_id
        structures = dict()
        try:
            pocos = esi_fetch(
                "Planetary_Interaction.get_corporations_corporation_id_customs_offices",
                args={"corporation_id": corporation_id},
                token=token,
                has_pages=True,
            )
            if not pocos:
                logger.info("%s: No custom offices retrieved from ESI", self)
            else:
                pocos_2 = {row["office_id"]: row for row in pocos}
                office_ids = list(pocos_2.keys())
                positions = self._fetch_locations_for_pocos(
                    corporation_id, office_ids, token
                )
                names = self._fetch_names_for_pocos(corporation_id, office_ids, token)

                # making sure we have all solar systems loaded
                # incl. their planets for later name matching
                for solar_system_id in {int(x["system_id"]) for x in pocos}:
                    EveSolarSystem.objects.get_or_create_esi(solar_system_id)

                # compile pocos into structures list
                for office_id, poco in pocos_2.items():
                    planet_name = names.get(office_id, "")
                    if planet_name:
                        try:
                            eve_planet = EvePlanet.objects.get(name=planet_name)
                        except EvePlanet.DoesNotExist:
                            name = ""
                            planet_id = None
                        else:
                            planet_id = eve_planet.id
                            name = eve_planet.eve_type.name_localized_for_language(
                                STRUCTURES_DEFAULT_LANGUAGE
                            )
                    else:
                        name = None
                        planet_id = None

                    reinforce_exit_start = datetime(
                        year=2000, month=1, day=1, hour=poco["reinforce_exit_start"]
                    )
                    reinforce_hour = reinforce_exit_start + timedelta(hours=1)
                    structure = {
                        "structure_id": office_id,
                        "type_id": EveTypeId.CUSTOMS_OFFICE,
                        "corporation_id": corporation_id,
                        "name": name if name else "",
                        "system_id": poco["system_id"],
                        "reinforce_hour": reinforce_hour.hour,
                        "state": Structure.State.UNKNOWN,
                    }
                    if planet_id:
                        structure["planet_id"] = planet_id

                    if office_id in positions:
                        structure["position"] = positions[office_id]

                    structures[office_id] = structure

                logger.info(
                    "%s: Storing updates for %d customs offices", self, len(structure)
                )
                for office_id, structure in structures.items():
                    structure_obj, _ = Structure.objects.update_or_create_from_dict(
                        structure, self
                    )
                    try:
                        poco = pocos_2[office_id]
                    except KeyError:
                        logger.warning(
                            "%s: No details found for this POCO: %d", self, office_id
                        )
                    else:
                        standing_level = PocoDetails.StandingLevel.from_esi(
                            poco.get("standing_level")
                        )
                        PocoDetails.objects.update_or_create(
                            structure=structure_obj,
                            defaults={
                                "alliance_tax_rate": poco.get("alliance_tax_rate"),
                                "allow_access_with_standings": poco.get(
                                    "allow_access_with_standings"
                                ),
                                "allow_alliance_access": poco.get(
                                    "allow_alliance_access"
                                ),
                                "bad_standing_tax_rate": poco.get(
                                    "bad_standing_tax_rate"
                                ),
                                "corporation_tax_rate": poco.get(
                                    "corporation_tax_rate"
                                ),
                                "excellent_standing_tax_rate": poco.get(
                                    "excellent_standing_tax_rate"
                                ),
                                "good_standing_tax_rate": poco.get(
                                    "good_standing_tax_rate"
                                ),
                                "neutral_standing_tax_rate": poco.get(
                                    "neutral_standing_tax_rate"
                                ),
                                "reinforce_exit_end": poco.get("reinforce_exit_end"),
                                "reinforce_exit_start": poco.get(
                                    "reinforce_exit_start"
                                ),
                                "standing_level": standing_level,
                                "terrible_standing_tax_rate": poco.get(
                                    "terrible_standing_tax_rate"
                                ),
                            },
                        )

            if STRUCTURES_DEVELOPER_MODE:
                self._store_raw_data("customs_offices", structures, corporation_id)

        except OSError as ex:
            self._report_esi_issue("fetch custom offices", ex, token)
            return False

        self._remove_structures_not_returned_from_esi(
            structures_qs=self.structures.filter_customs_offices(),
            new_structures=structures.values(),
        )
        return True

    def _fetch_locations_for_pocos(self, corporation_id, item_ids, token):
        logger.info(
            "%s: Fetching locations for %d custom offices from ESI", self, len(item_ids)
        )
        locations_data = list()
        for item_ids_chunk in chunks(item_ids, 999):
            locations_data_chunk = esi_fetch(
                "Assets.post_corporations_corporation_id_assets_locations",
                args={
                    "corporation_id": corporation_id,
                    "item_ids": item_ids_chunk,
                },
                token=token,
            )
            locations_data += locations_data_chunk
        positions = {x["item_id"]: x["position"] for x in locations_data}
        return positions

    def _fetch_names_for_pocos(self, corporation_id, item_ids, token):

        logger.info(
            "%s: Fetching names for %d custom office names from ESI",
            self,
            len(item_ids),
        )
        names_data = list()
        for item_ids_chunk in chunks(item_ids, 999):
            names_data_chunk = esi_fetch(
                "Assets.post_corporations_corporation_id_assets_names",
                args={
                    "corporation_id": corporation_id,
                    "item_ids": item_ids_chunk,
                },
                token=token,
            )
            names_data += names_data_chunk

        names = {x["item_id"]: self._extract_planet_name(x["name"]) for x in names_data}
        return names

    @staticmethod
    def _extract_planet_name(text: str) -> str:
        """Extract name of planet from assert name for a customs office."""
        reg_ex = re.compile(r"Customs Office \((.+)\)")
        matches = reg_ex.match(text)
        return matches.group(1) if matches else ""

    def _fetch_starbases(self, token: Token) -> bool:
        """Fetch starbases from ESI for this owner.

        Return True when successful, else False.
        """
        structures = list()
        corporation_id = self.corporation.corporation_id
        try:
            starbases = esi_fetch(
                "Corporation.get_corporations_corporation_id_starbases",
                args={"corporation_id": corporation_id},
                token=token,
                has_pages=True,
            )
            if not starbases:
                logger.info("%s: No starbases retrieved from ESI", self)
            else:
                names = self._fetch_starbases_names(corporation_id, starbases, token)
                for starbase in starbases:
                    starbase["fuel_expires"] = self._calc_starbase_fuel_expires(
                        corporation_id, starbase, token
                    )
                # convert starbases to structures
                for starbase in starbases:
                    if starbase["starbase_id"] in names:
                        name = names[starbase["starbase_id"]]
                    else:
                        name = "Starbase"
                    structure = {
                        "structure_id": starbase["starbase_id"],
                        "type_id": starbase["type_id"],
                        "corporation_id": corporation_id,
                        "name": name,
                        "system_id": starbase["system_id"],
                    }
                    if "state" in starbase:
                        structure["state"] = starbase["state"]

                    if "moon_id" in starbase:
                        structure["moon_id"] = starbase["moon_id"]

                    if "fuel_expires" in starbase:
                        structure["fuel_expires"] = starbase["fuel_expires"]

                    if "reinforced_until" in starbase:
                        structure["state_timer_end"] = starbase["reinforced_until"]

                    if "unanchors_at" in starbase:
                        structure["unanchors_at"] = starbase["unanchors_at"]

                    structures.append(structure)

                logger.info(
                    "%s: Storing updates for %d starbases", self, len(structures)
                )
                for structure in structures:
                    Structure.objects.update_or_create_from_dict(structure, self)

            if STRUCTURES_DEVELOPER_MODE:
                self._store_raw_data("starbases", structures, corporation_id)

        except HTTPForbidden:
            try:
                character = self.characters.get(
                    character_ownership__character__character_id=token.character_id
                )
            except ObjectDoesNotExist:
                pass
            else:
                self._delete_character(
                    "Character is not a director or CEO and therefore "
                    "can not fetch starbases.",
                    character,
                )
            return False

        except OSError as ex:
            self._report_esi_issue("fetch starbases", ex, token)
            return False

        self._remove_structures_not_returned_from_esi(
            structures_qs=self.structures.filter_starbases(),
            new_structures=structures,
        )
        return True

    def _fetch_starbases_names(self, corporation_id, starbases, token):

        logger.info(
            "%s: Fetching names for %d starbases from ESI", self, len(starbases)
        )
        item_ids = [x["starbase_id"] for x in starbases]
        names_data = list()
        for item_ids_chunk in chunks(item_ids, 999):
            names_data_chunk = esi_fetch(
                "Assets.post_corporations_corporation_id_assets_names",
                args={
                    "corporation_id": corporation_id,
                    "item_ids": item_ids_chunk,
                },
                token=token,
            )
            names_data += names_data_chunk
        names = {x["item_id"]: x["name"] for x in names_data}

        for starbase in starbases:
            starbase_id = starbase["starbase_id"]
            starbase["name"] = (
                names[starbase_id] if starbase_id in names else "Starbase"
            )

        return names

    def _calc_starbase_fuel_expires(
        self, corporation_id: int, starbase: dict, token: Token
    ) -> datetime:
        """Estimate when fuel will expire for this starbase.

        Estimate will vary due to server caching of remaining fuel blocks.
        """
        if starbase["state"] == "offline":
            return None
        operation = _esi_client().Corporation.get_corporations_corporation_id_starbases_starbase_id(
            corporation_id=corporation_id,
            starbase_id=starbase["starbase_id"],
            system_id=starbase["system_id"],
            token=token.valid_access_token(),
        )
        operation.request_config.also_return_response = True
        starbase_details, response = operation.result()
        fuel_quantity = None
        if "fuels" in starbase_details:
            for fuel in starbase_details["fuels"]:
                fuel_type, _ = EveType.objects.get_or_create_esi(fuel["type_id"])
                if fuel_type.is_fuel_block:
                    fuel_quantity = fuel["quantity"]
        if fuel_quantity:
            starbase_type, _ = EveType.objects.get_or_create_esi(starbase["type_id"])
            solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                starbase["system_id"]
            )
            sov_discount = (
                0.25 if solar_system.corporation_has_sov(self.corporation) else 0
            )
            seconds = math.floor(
                3600
                * fuel_quantity
                / (starbase_type.starbase_fuel_per_hour * (1 - sov_discount))
            )
            last_modified = parsedate_to_datetime(
                response.headers.get("Last-Modified", format_datetime(now()))
            )
            fuel_expires_at = last_modified + timedelta(seconds=seconds)

        return fuel_expires_at

    def fetch_notifications_esi(self, user: User = None) -> None:
        """Fetch notifications for this owner from ESI and proceses them."""
        notifications_count_all = 0
        token = self.fetch_token(
            rotate_characters=self.RotateCharactersType.NOTIFICATIONS
        )
        notifications = self._fetch_notifications_from_esi(token)
        notifications_count_new = self._store_notifications(notifications)
        self._process_moon_notifications()
        if notifications_count_new > 0:
            logger.info(
                "%s: Received %d new notifications from ESI",
                self,
                notifications_count_new,
            )
            self._process_timers_for_notifications(token)
            notifications_count_all += notifications_count_new
        else:
            logger.info("%s: No new notifications received from ESI", self)

        self.notifications_last_update_at = now()
        self.save(update_fields=["notifications_last_update_at"])

        if user:
            self._send_report_to_user(
                topic="notifications",
                topic_count=notifications_count_all,
                user=user,
            )

    def _fetch_notifications_from_esi(self, token: Token) -> dict:
        """fetching all notifications from ESI for current owner"""

        notifications = esi_fetch(
            "Character.get_characters_character_id_notifications",
            args={"character_id": token.character_id},
            token=token,
        )
        if STRUCTURES_DEVELOPER_MODE:
            self._store_raw_data(
                "notifications", notifications, self.corporation.corporation_id
            )
        if STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED:
            self._store_raw_notifications(notifications)
        logger.debug(
            "%s: Processing %d notifications received from ESI",
            self,
            len(notifications),
        )
        return notifications

    def _store_raw_notifications(self, notifications):
        # store notifications to disk in continuous file per corp
        folder_name = "structures_notifications_archive"
        os.makedirs(folder_name, exist_ok=True)
        filename = "{}/notifications_{}_{}.txt".format(
            folder_name, self.corporation.corporation_id, now().date().isoformat()
        )
        logger.info(
            "%s: Storing notifications into archive file: %s", self, format(filename)
        )
        with open(file=filename, mode="a", encoding="utf-8") as f:
            f.write(
                "[{}] {}:\n".format(
                    now().strftime(DATETIME_FORMAT),
                    self.corporation.corporation_ticker,
                )
            )
            json.dump(notifications, f, cls=DjangoJSONEncoder, sort_keys=True, indent=4)
            f.write("\n")

    def _store_notifications(self, notifications: list) -> int:
        """stores new notifications in database.
        Returns number of newly created objects.
        """
        # identify new notifications
        existing_notification_ids = set(
            self.notifications.values_list("notification_id", flat=True)
        )
        new_notifications = [
            obj
            for obj in notifications
            if obj["notification_id"] not in existing_notification_ids
        ]
        # create new notif objects
        new_notification_objects = list()
        for notification in new_notifications:
            sender_type = EveEntity.Category.from_esi_name(notification["sender_type"])
            if sender_type != EveEntity.Category.OTHER:
                sender, _ = EveEntity.objects.get_or_create_esi(
                    eve_entity_id=notification["sender_id"]
                )
            else:
                sender, _ = EveEntity.objects.get_or_create(
                    id=notification["sender_id"],
                    defaults={"category": sender_type},
                )
            text = notification["text"] if "text" in notification else None
            is_read = notification["is_read"] if "is_read" in notification else None
            new_notification_objects.append(
                Notification(
                    notification_id=notification["notification_id"],
                    owner=self,
                    sender=sender,
                    timestamp=notification["timestamp"],
                    # at least one type has a trailing white space
                    # which we need to remove
                    notif_type=notification["type"].strip(),
                    text=text,
                    is_read=is_read,
                    last_updated=now(),
                    created=now(),
                )
            )

        Notification.objects.bulk_create(new_notification_objects)
        return len(new_notification_objects)

    def _process_timers_for_notifications(self, token: Token):
        """processes notifications for timers if any"""
        if STRUCTURES_ADD_TIMERS:
            cutoff_dt_for_stale = now() - timedelta(
                hours=STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
            )
            notifications = (
                self.notifications.filter(
                    notif_type__in=NotificationType.relevant_for_timerboard
                )
                .exclude(is_timer_added=True)
                .filter(timestamp__gte=cutoff_dt_for_stale)
                .select_related("owner", "sender")
                .order_by("timestamp")
            )
            if notifications.exists():
                if not token:
                    token = self.fetch_token()
                for notification in notifications:
                    notification.process_for_timerboard(token)

    def _process_moon_notifications(self):
        """processes notifications for timers if any"""
        empty_refineries = Structure.objects.filter(
            owner=self,
            eve_type__eve_group_id=EveGroupId.REFINERY,
            eve_moon__isnull=True,
        )
        if empty_refineries:
            logger.info(
                "%s: Trying to find moons for up to %d refineries which have no moon.",
                self,
                empty_refineries.count(),
            )
            notifications = (
                self.notifications.filter(
                    notif_type__in=NotificationType.relevant_for_moonmining
                )
                .select_related("owner", "sender")
                .order_by("timestamp")
            )
            structure_id_2_moon_id = dict()
            for notification in notifications:
                parsed_text = notification.get_parsed_text()
                moon_id = parsed_text["moonID"]
                structure_id = parsed_text["structureID"]
                structure_id_2_moon_id[structure_id] = moon_id

            for refinery in empty_refineries:
                if refinery.id in structure_id_2_moon_id:
                    logger.info("%s: Updating moon for structure %s", self, refinery)
                    eve_moon, _ = EveMoon.objects.get_or_create_esi(
                        eve_id=structure_id_2_moon_id[refinery.id]
                    )
                    refinery.eve_moon = eve_moon
                    refinery.save()

    def send_new_notifications(self, user: User = None):
        """Forward all new notification of this owner to configured webhooks."""
        notifications_count = 0
        cutoff_dt_for_stale = now() - timedelta(
            hours=STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
        )
        all_new_notifications = (
            self.notifications.filter(
                notif_type__in=(
                    Webhook.objects.enabled_notification_types()
                    & NotificationType.relevant_for_forwarding
                )
            )
            .filter(is_sent=False)
            .filter(timestamp__gte=cutoff_dt_for_stale)
            .select_related("owner", "sender", "owner__corporation")
            .order_by("timestamp")
        )
        for notif in all_new_notifications:
            notif.send_to_configured_webhooks()
        if not all_new_notifications:
            logger.info("%s: No new notifications found for forwarding", self)
        self.forwarding_last_update_at = now()
        self.save(update_fields=["forwarding_last_update_at"])
        if user:
            self._send_report_to_user(
                topic="notifications", topic_count=notifications_count, user=user
            )

    def _send_report_to_user(self, topic: str, topic_count: int, user: User):
        message_details = "%(count)s %(topic)s synced." % {
            "count": topic_count,
            "topic": topic,
        }
        message = _(
            'Syncing of %(topic)s for "%(owner)s" %(result)s.\n' "%(message_details)s"
        ) % {
            "topic": topic,
            "owner": self.corporation.corporation_name,
            "result": _("completed successfully"),
            "message_details": message_details,
        }

        notify(
            user,
            title=_("%(title)s: %(topic)s updated for " "%(owner)s: %(result)s")
            % {
                "title": _(__title__),
                "topic": topic,
                "owner": self.corporation.corporation_name,
                "result": _("OK"),
            },
            message=message,
            level="success",
        )

    @staticmethod
    def _store_raw_data(name: str, data: list, corporation_id: int):
        """store raw data for debug purposes"""
        with open(f"{name}_raw_{corporation_id}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, cls=DjangoJSONEncoder, sort_keys=True, indent=4)

    def update_asset_esi(self, user: User = None):
        assets_in_structures = self._fetch_structure_assets_from_esi()
        StructureItem.objects.filter(structure__owner=self).delete()  # clear all items
        for structure in self.structures.all():
            if structure.id in assets_in_structures.keys():
                structure_assets = assets_in_structures[structure.id]
                has_fitting = [
                    asset
                    for asset in structure_assets.values()
                    if asset["location_flag"]
                    != StructureItem.LocationFlag.QUANTUM_CORE_ROOM
                ]
                has_core = [
                    asset
                    for asset in structure_assets.values()
                    if asset["location_flag"]
                    == StructureItem.LocationFlag.QUANTUM_CORE_ROOM
                ]
                structure.has_fitting = bool(has_fitting)
                structure.has_core = bool(has_core)
                structure.save()

                structure_items = list()
                for item_id, asset in structure_assets.items():
                    eve_type, _ = EveType.objects.get_or_create_esi(asset["type_id"])
                    structure_items.append(
                        StructureItem(
                            id=item_id,
                            structure=structure,
                            eve_type=eve_type,
                            is_singleton=asset["is_singleton"],
                            location_flag=asset["location_flag"],
                            quantity=asset["quantity"],
                        )
                    )
                with transaction.atomic():
                    structure.items.all().delete()
                    structure.items.bulk_create(structure_items)

            structure.reevaluate_jump_fuel_alerts()

        self.assets_last_update_at = now()
        self.save(update_fields=["assets_last_update_at"])
        if user:
            self._send_report_to_user(
                topic="assets", topic_count=self.structures.count(), user=user
            )

    def _fetch_structure_assets_from_esi(self) -> dict:
        assets = esi_fetch(
            esi_path="Assets.get_corporations_corporation_id_assets",
            args={"corporation_id": self.corporation.corporation_id},
            token=self.fetch_token(),
            has_pages=True,
        )
        structure_ids = set(self.structures.values_list("id", flat=True))
        assets_in_structures = {id: dict() for id in structure_ids}
        for asset in assets:
            location_id = asset["location_id"]
            if location_id in structure_ids and asset["location_flag"] not in [
                StructureItem.LocationFlag.CORP_DELIVERIES,
                StructureItem.LocationFlag.OFFICE_FOLDER,
                StructureItem.LocationFlag.SECONDARY_STORAGE,
                StructureItem.LocationFlag.AUTOFIT,
            ]:
                assets_in_structures[location_id][asset["item_id"]] = asset
        return assets_in_structures

    @classmethod
    def get_esi_scopes(cls) -> list:
        scopes = [
            "esi-corporations.read_structures.v1",
            "esi-universe.read_structures.v1",
            "esi-characters.read_notifications.v1",
            "esi-assets.read_corporation_assets.v1",
        ]
        if STRUCTURES_FEATURE_CUSTOMS_OFFICES:
            scopes += ["esi-planets.read_customs_offices.v1"]
        if STRUCTURES_FEATURE_STARBASES:
            scopes += ["esi-corporations.read_starbases.v1"]
        return scopes


class OwnerCharacter(models.Model):
    """Character for syncing owner data with ESI."""

    owner = models.ForeignKey(
        "Owner", on_delete=models.CASCADE, related_name="characters"
    )
    character_ownership = models.ForeignKey(
        CharacterOwnership,
        on_delete=models.CASCADE,
        related_name="+",
        help_text="character used for syncing",
    )
    structures_last_used_at = models.DateTimeField(
        null=True,
        default=None,
        editable=False,
        db_index=True,
        help_text="when this character was last used for syncing structures",
    )
    notifications_last_used_at = models.DateTimeField(
        null=True,
        default=None,
        editable=False,
        db_index=True,
        help_text="when this character was last used for syncing notifications",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "character_ownership"], name="functional_pk_ownertoken"
            )
        ]

    def __str__(self) -> str:
        return (
            f"{self.owner.corporation.corporation_name}-"
            f"{self.character_ownership.character.character_name}"
        )

    def valid_token(self) -> Optional[Token]:
        """Provide a valid token or None if none can be found."""
        return (
            Token.objects.filter(
                user=self.character_ownership.user,
                character_id=self.character_ownership.character.character_id,
            )
            .require_scopes(Owner.get_esi_scopes())
            .require_valid()
            .first()
        )
