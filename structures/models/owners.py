"""Owner related models."""

import datetime as dt
import json
import os
import re
from email.utils import format_datetime, parsedate_to_datetime
from typing import Any, Iterable, List, Optional

from bravado.exception import HTTPForbidden, HTTPNotFound

from django.contrib.auth.models import Group, User
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import F
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from esi.errors import TokenError
from esi.models import Token
from eveuniverse.models import EveMoon, EvePlanet, EveSolarSystem, EveType

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
    STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED,
    STRUCTURES_DEVELOPER_MODE,
    STRUCTURES_ESI_DIRECTOR_ERROR_MAX_RETRIES,
    STRUCTURES_FEATURE_CUSTOMS_OFFICES,
    STRUCTURES_FEATURE_STARBASES,
    STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION,
    STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES,
    STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED,
    STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES,
)
from ..constants import EveGroupId, EveTypeId
from ..managers import OwnerManager
from ..providers import esi
from .eveuniverse import EveSovereigntyMap
from .notifications import (
    EveEntity,
    GeneratedNotification,
    Notification,
    NotificationType,
    Webhook,
)
from .structures import (
    PocoDetails,
    StarbaseDetail,
    StarbaseDetailFuel,
    Structure,
    StructureItem,
)

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
        verbose_name=_("corporation"),
        help_text=_("Corporation owning structures"),
    )
    # regular
    are_pocos_public = models.BooleanField(
        default=False,
        verbose_name=_("are pocos public"),
        help_text=_("whether pocos of this owner are shown on public POCO page"),
    )
    assets_last_update_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("assets last update at"),
        help_text=_("when the last successful update happened"),
    )
    character_ownership = models.ForeignKey(
        CharacterOwnership,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
        help_text="OUTDATED. Has been replaced by OwnerCharacter",  # TODO: Remove
    )
    forwarding_last_update_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("forwarding last update at"),
        help_text=_("when the last successful update happened"),
    )
    has_default_pings_enabled = models.BooleanField(
        default=True,
        verbose_name=_("has default pings enabled"),
        help_text=_(
            "to enable or disable pinging of notifications for this owner "
            "e.g. with @everyone and @here"
        ),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("is active"),
        help_text=_("whether this owner is currently included in the sync process"),
    )
    is_alliance_main = models.BooleanField(
        default=False,
        verbose_name=_("is alliance main"),
        help_text=_(
            "whether alliance wide notifications "
            "are forwarded for this owner (e.g. sov notifications)"
        ),
    )
    is_included_in_service_status = models.BooleanField(
        default=True,
        verbose_name=_("is included in service status"),
        help_text=_(
            "whether the sync status of this owner is included in "
            "the overall status of this services"
        ),
    )
    is_up = models.BooleanField(
        null=True,
        default=None,
        editable=False,
        verbose_name=_("is up"),
        help_text=_("whether all services for this owner are currently up"),
    )
    notifications_last_update_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("notifications last update at"),
        help_text=_("when the last successful update happened"),
    )
    ping_groups = models.ManyToManyField(
        Group,
        default=None,
        blank=True,
        related_name="+",
        verbose_name=_("ping groups"),
        help_text=_("Groups to be pinged for each notification. "),
    )
    structures_last_update_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("structures last update at"),
        help_text=_("when the last successful update happened"),
    )
    webhooks = models.ManyToManyField(
        "Webhook",
        default=None,
        blank=True,
        related_name="owners",
        verbose_name=_("webhooks"),
        help_text=_("Notifications are sent to these webhooks."),
    )

    objects = OwnerManager()

    class Meta:
        verbose_name = _("owner")
        verbose_name_plural = _("owners")

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
        return bool(
            self.structures_last_update_at
        ) and self.structures_last_update_at > (
            now() - dt.timedelta(minutes=STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES)
        )

    @property
    def is_notification_sync_fresh(self) -> bool:
        """True if last sync happened with grace time, else False."""
        return bool(
            self.notifications_last_update_at
        ) and self.notifications_last_update_at > (
            now() - dt.timedelta(minutes=STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES)
        )

    @property
    def is_forwarding_sync_fresh(self) -> bool:
        """True if last sync happened with grace time, else False."""
        return bool(
            self.forwarding_last_update_at
        ) and self.forwarding_last_update_at > (
            now() - dt.timedelta(minutes=STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES)
        )

    @property
    def is_assets_sync_fresh(self) -> bool:
        """True if last sync happened with grace time, else False."""
        return bool(self.assets_last_update_at) and self.assets_last_update_at > (
            now() - dt.timedelta(minutes=STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES)
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

    def has_sov(self, eve_solar_system: EveSolarSystem) -> bool:
        """Determine whether this owner has sov in the given solar system."""
        return EveSovereigntyMap.objects.corporation_has_sov(
            eve_solar_system=eve_solar_system, corporation=self.corporation
        )

    def delete_character(
        self,
        character: "OwnerCharacter",
        error: str,
        level: str = "warning",
        max_allowed_errors: int = 0,
    ) -> None:
        """Delete character and notify it's owner and admin about the reason

        Args:
        - character: Character this error refers to
        - error: Error text
        - level: context level for the notification
        - max_error: how many errors are permitted before character is deleted
        """
        if character.error_count < max_allowed_errors:
            logger.warning(
                (
                    "%s: Character encountered an error and will be deleted "
                    "if this occurs more often (%d/%d): %s"
                ),
                character,
                character.error_count + 1,
                max_allowed_errors,
                error,
            )
            with transaction.atomic():
                character.error_count = F("error_count") + 1
                character.save(update_fields=["error_count"])
            return

        title = f"{__title__}: {self}: Invalid character has been removed"
        message = (
            f"{character.character_ownership}: {error}\n"
            "The character has been removed. "
            "Please add a new character to restore the previous service level."
        )
        notify(
            user=character.character_ownership.user,
            title=title,
            message=message,
            level=level,
        )
        if self.characters.count() == 1:
            message += (
                " This owner has no configured characters anymore "
                "and it's services are now down."
            )
            level = "danger"
        notify_admins(title=f"FYI: {title}", message=message, level=level)
        character.delete()

    def _rotate_character(
        self,
        character: "OwnerCharacter",
        ignore_schedule: bool,
        rotate_characters: RotateCharactersType,
    ) -> None:
        """Rotate this character such that all are spread evenly
        across the ESI cache duration for each ESI call.
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

    def fetch_token(
        self,
        rotate_characters: Optional[RotateCharactersType] = None,
        ignore_schedule: bool = False,
    ) -> Token:
        """Fetch a valid token for the owner and return it.

        Args:
            rotate_characters: For which sync type to rotate through characters \
                with every new call
            ignore_schedule: Ignore current schedule when rotating

        Raises TokenError when no valid token can be provided.
        """
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
                self.delete_character(
                    character=character,
                    error="Character does no longer belong to the owner's corporation.",
                )
                continue
            elif not character.character_ownership.user.has_perm(
                "structures.add_structure_owner"
            ):
                self.delete_character(
                    character=character,
                    error="Character does not have sufficient permission to sync.",
                )
                continue
            token = character.valid_token()
            if not token:
                self.delete_character(
                    character=character,
                    error="Character has no valid token for sync.",
                )
                continue
            found_character = character
            break  # leave the for loop if we have found a valid token
        else:
            raise TokenError(
                f"{self}: No valid character found for sync. "
                "Service down for this owner."
            )
        if rotate_characters:
            self._rotate_character(
                character=found_character,
                ignore_schedule=ignore_schedule,
                rotate_characters=rotate_characters,
            )
        return token

    def _report_esi_issue(self, action: str, ex: Exception, token: Token):
        """Report an ESI issue to admins."""
        message = f"{self}: Failed to {action} from ESI with token {token} due to {ex}"
        logger.warning(message, exc_info=True)

    def update_structures_esi(self, user: Optional[User] = None):
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
        self, structures_qs: models.QuerySet, new_structures: Iterable
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

    def _fetch_locations_for_assets(
        self, item_ids: Iterable[int], token: Token
    ) -> dict:
        """Fetch locations for given asset items from ESI."""
        item_ids = list(item_ids)
        logger.info(
            "%s: Fetching locations for %d assets from ESI", self, len(item_ids)
        )
        locations_data = list()
        for item_ids_chunk in chunks(item_ids, 999):
            try:
                locations_data_chunk = (
                    esi.client.Assets.post_corporations_corporation_id_assets_locations(
                        corporation_id=self.corporation.corporation_id,
                        item_ids=item_ids_chunk,
                        token=token.valid_access_token(),
                    )
                ).results()
            except HTTPNotFound:
                pass
            else:
                locations_data += locations_data_chunk
        positions = {x["item_id"]: x["position"] for x in locations_data}
        return positions

    def _fetch_upwell_structures(self, token: Token) -> bool:
        """Fetch Upwell structures from ESI for self.

        Return True if successful, else False.
        """
        is_ok = True
        # fetch main list of structure for this corporation
        try:
            structures = (
                esi.client.Corporation.get_corporations_corporation_id_structures(
                    corporation_id=self.corporation.corporation_id,
                    token=token.valid_access_token(),
                ).results()
            )
        except OSError as ex:
            self._report_esi_issue("fetch corporation structures", ex, token)
            return False

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
                    structure_info = (
                        esi.client.Universe.get_universe_structures_structure_id(
                            structure_id=structure["structure_id"],
                            token=token.valid_access_token(),
                        )
                    ).results()
                except OSError as ex:
                    self._report_esi_issue(
                        f"fetch structure #{structure['structure_id']}", ex, token
                    )
                    structure["name"] = "(no data)"
                    is_ok = False
                else:
                    structure["name"] = Structure.extract_name_from_esi_response(
                        structure_info["name"]
                    )
                    structure["position"] = structure_info["position"]

            logger.info(
                "%s: Storing updates for %d upwell structures",
                self,
                len(structures),
            )
            for structure in structures:
                try:
                    Structure.objects.update_or_create_from_dict(structure, self)
                except OSError:
                    logger.warning(
                        "%s: Failed to store update for structure with ID %s",
                        self,
                        structure["structure_id"],
                    )
                    is_ok = False

        if STRUCTURES_DEVELOPER_MODE:
            self._store_raw_data("structures", structures)

        self._remove_structures_not_returned_from_esi(
            structures_qs=self.structures.filter_upwell_structures(),
            new_structures=structures,
        )
        return is_ok

    def _fetch_custom_offices(self, token: Token) -> bool:
        """Fetch custom offices from ESI for this owner.

        Return True when successful, else False.
        """
        structures = dict()
        try:
            pocos = esi.client.Planetary_Interaction.get_corporations_corporation_id_customs_offices(
                corporation_id=self.corporation.corporation_id,
                token=token.valid_access_token(),
            ).results()
            if not pocos:
                logger.info("%s: No custom offices retrieved from ESI", self)
            else:
                pocos_2 = {row["office_id"]: row for row in pocos}
                office_ids = list(pocos_2.keys())
                positions = self._fetch_locations_for_assets(office_ids, token)
                names = self._fetch_names_for_pocos(office_ids, token)

                # making sure we have all solar systems loaded
                # incl. their planets for later name matching
                for solar_system_id in {int(x["system_id"]) for x in pocos}:
                    EveSolarSystem.objects.get_or_create_esi(id=solar_system_id)

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
                            name = eve_planet.eve_type.name
                    else:
                        name = None
                        planet_id = None

                    reinforce_exit_start = dt.datetime(
                        year=2000, month=1, day=1, hour=poco["reinforce_exit_start"]
                    )
                    reinforce_hour = reinforce_exit_start + dt.timedelta(hours=1)
                    structure = {
                        "structure_id": office_id,
                        "type_id": EveTypeId.CUSTOMS_OFFICE,
                        "corporation_id": self.corporation.corporation_id,
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
                    "%s: Storing updates for %d customs offices", self, len(structures)
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
                self._store_raw_data("customs_offices", structures)

        except OSError as ex:
            self._report_esi_issue("fetch custom offices", ex, token)
            return False

        self._remove_structures_not_returned_from_esi(
            structures_qs=self.structures.filter_customs_offices(),
            new_structures=structures.values(),
        )
        return True

    def _fetch_names_for_pocos(self, item_ids: list, token: Token) -> dict:
        logger.info(
            "%s: Fetching names for %d custom office names from ESI",
            self,
            len(item_ids),
        )
        names_data = list()
        for item_ids_chunk in chunks(item_ids, 999):
            try:
                names_data_chunk = (
                    esi.client.Assets.post_corporations_corporation_id_assets_names(
                        corporation_id=self.corporation.corporation_id,
                        item_ids=item_ids_chunk,
                        token=token.valid_access_token(),
                    )
                ).results()
            except HTTPNotFound:
                pass
            else:
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
        try:
            starbases_data = (
                esi.client.Corporation.get_corporations_corporation_id_starbases(
                    corporation_id=self.corporation.corporation_id,
                    token=token.valid_access_token(),
                )
            ).results()
            if not starbases_data:
                logger.info("%s: This corporation has no starbases.", self)
            else:
                starbases_data = {obj["starbase_id"]: obj for obj in starbases_data}
                names = self._fetch_starbases_names(starbases_data.keys(), token)
                locations = self._fetch_locations_for_assets(
                    starbases_data.keys(), token
                )
                # convert starbases to structures
                for structure_id, starbase in starbases_data.items():
                    try:
                        name = names[structure_id]
                    except KeyError:
                        name = "Starbase"
                    structure = {
                        "structure_id": structure_id,
                        "type_id": starbase["type_id"],
                        "corporation_id": self.corporation.corporation_id,
                        "name": name,
                        "system_id": starbase["system_id"],
                    }
                    if structure_id in locations:
                        structure["position"] = locations[structure_id]
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
                    structure_obj, _ = Structure.objects.update_or_create_from_dict(
                        structure, self
                    )
                    detail = self._update_starbase_detail(
                        structure=structure_obj, token=token
                    )
                    fuel_expires_at = detail.calc_fuel_expires()
                    if fuel_expires_at:
                        structure_obj.fuel_expires_at = fuel_expires_at
                        structure_obj.save()
                    if (
                        structure_obj.state == Structure.State.POS_REINFORCED
                        and structure_obj.state_timer_end
                    ):
                        GeneratedNotification.objects.get_or_create_from_structure(
                            structure=structure_obj,
                            notif_type=NotificationType.TOWER_REINFORCED_EXTRA,
                        )

            if STRUCTURES_DEVELOPER_MODE:
                self._store_raw_data("starbases", structures)

        except HTTPForbidden:
            try:
                character = self.characters.get(
                    character_ownership__character__character_id=token.character_id
                )
            except ObjectDoesNotExist:
                pass
            else:
                self.delete_character(
                    character=character,
                    error=(
                        "Character is not a director or CEO and therefore "
                        "can not fetch starbases."
                    ),
                    max_allowed_errors=STRUCTURES_ESI_DIRECTOR_ERROR_MAX_RETRIES,
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

    def _fetch_starbases_names(self, item_ids: Iterable, token: Token) -> dict:
        item_ids = list(item_ids)
        logger.info("%s: Fetching names for %d starbases from ESI", self, len(item_ids))
        names_data = list()
        for item_ids_chunk in chunks(item_ids, 999):
            try:
                names_data_chunk = (
                    esi.client.Assets.post_corporations_corporation_id_assets_names(
                        corporation_id=self.corporation.corporation_id,
                        item_ids=item_ids_chunk,
                        token=token.valid_access_token(),
                    )
                ).results()
            except HTTPNotFound:
                pass
            else:
                names_data += names_data_chunk
        names = {x["item_id"]: x["name"] for x in names_data}
        return names

    def _update_starbase_detail(self, structure, token: Token) -> StarbaseDetail:
        """Update detail for the starbase from ESI."""
        operation = esi.client.Corporation.get_corporations_corporation_id_starbases_starbase_id(
            corporation_id=structure.owner.corporation.corporation_id,
            starbase_id=structure.id,
            system_id=structure.eve_solar_system.id,
            token=token.valid_access_token(),
        )
        operation.request_config.also_return_response = True
        data, response = operation.results()
        last_modified_at = parsedate_to_datetime(
            response.headers.get("Last-Modified", format_datetime(now()))
        )
        defaults = {
            "allow_alliance_members": data["allow_alliance_members"],
            "allow_corporation_members": data["allow_corporation_members"],
            "anchor_role": StarbaseDetail.Role.from_esi(data["anchor"]),
            "attack_if_at_war": data["attack_if_at_war"],
            "attack_if_other_security_status_dropping": data.get(
                "attack_if_other_security_status_dropping"
            ),
            "attack_security_status_threshold": data.get(
                "attack_security_status_threshold"
            ),
            "attack_standing_threshold": data.get("attack_standing_threshold"),
            "fuel_bay_take_role": StarbaseDetail.Role.from_esi(data["fuel_bay_take"]),
            "fuel_bay_view_role": StarbaseDetail.Role.from_esi(data["fuel_bay_view"]),
            "last_modified_at": last_modified_at,
            "offline_role": StarbaseDetail.Role.from_esi(data["offline"]),
            "online_role": StarbaseDetail.Role.from_esi(data["online"]),
            "unanchor_role": StarbaseDetail.Role.from_esi(data["unanchor"]),
            "use_alliance_standings": data["use_alliance_standings"],
        }
        for fuel in data["fuels"]:
            EveType.objects.get_or_create_esi(id=fuel["type_id"])
        with transaction.atomic():
            detail, _ = StarbaseDetail.objects.update_or_create(
                structure=structure, defaults=defaults
            )
            detail.fuels.all().delete()
            for fuel in data["fuels"]:
                StarbaseDetailFuel.objects.create(
                    eve_type_id=fuel["type_id"],
                    detail=detail,
                    quantity=fuel["quantity"],
                )
        return detail

    def add_or_remove_timers_from_notifications(self):
        """Add/remove timers from esi and generated notification of this owner."""
        self.notification_set.add_or_remove_timers()
        self.generatednotification_set.add_or_remove_timers()

    def fetch_notifications_esi(self, user: Optional[User] = None) -> None:
        """Fetch notifications for this owner from ESI and process them."""
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

    def _fetch_notifications_from_esi(self, token: Token) -> List[dict]:
        """fetching all notifications from ESI for current owner"""
        notifications = esi.client.Character.get_characters_character_id_notifications(
            character_id=token.character_id, token=token.valid_access_token()
        ).results()
        if STRUCTURES_DEVELOPER_MODE:
            self._store_raw_data("notifications", notifications)
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

    def _store_notifications(self, notifications: List[dict]) -> int:
        """Store new notifications in database.
        Returns number of newly created objects.
        """
        # identify new notifications
        existing_notification_ids = set(
            self.notification_set.values_list("notification_id", flat=True)
        )
        new_notifications = [
            obj
            for obj in notifications
            if obj["notification_id"] not in existing_notification_ids
        ]
        # create new notification objects
        for notification in new_notifications:
            if notification["sender_type"] == "other":
                sender = None
            else:
                sender, _ = EveEntity.objects.get_or_create_esi(
                    id=notification["sender_id"]
                )
            text = notification["text"] if "text" in notification else None
            is_read = notification["is_read"] if "is_read" in notification else None
            # at least one type has a trailing white space
            # which we need to remove
            notif_type = notification["type"].strip()
            Notification.objects.create(
                notification_id=notification["notification_id"],
                owner=self,
                sender=sender,
                timestamp=notification["timestamp"],
                notif_type=notif_type,
                text=text,
                is_read=is_read,
                last_updated=now(),
                created=now(),
            )
        return len(new_notifications)

    def _process_moon_notifications(self):
        """processes notifications for timers if any"""
        empty_refineries = Structure.objects.filter(
            owner=self,
            eve_type__eve_group_id=EveGroupId.REFINERY,
            eve_moon__isnull=True,
        )
        if empty_refineries.exists():
            logger.info(
                "%s: Trying to find moons for up to %d refineries which have no moon.",
                self,
                empty_refineries.count(),
            )
            notifications = (
                self.notification_set.filter(
                    notif_type__in=NotificationType.relevant_for_moonmining
                )
                .select_related("owner", "sender")
                .order_by("timestamp")
            )
            structure_id_2_moon_id = dict()
            for notification in notifications:
                parsed_text = notification.parsed_text()
                moon_id = parsed_text["moonID"]
                structure_id = parsed_text["structureID"]
                structure_id_2_moon_id[structure_id] = moon_id
            for refinery in empty_refineries:
                if refinery.id in structure_id_2_moon_id:
                    logger.info("%s: Updating moon for structure %s", self, refinery)
                    eve_moon, _ = EveMoon.objects.get_or_create_esi(
                        id=structure_id_2_moon_id[refinery.id]
                    )
                    refinery.eve_moon = eve_moon
                    refinery.save()

    def send_new_notifications(self, user: Optional[User] = None):
        """Forward all new notification of this owner to configured webhooks."""
        notifications_count = 0
        cutoff_dt_for_stale = now() - dt.timedelta(
            hours=STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
        )
        my_filter = {
            "notif_type__in": (
                Webhook.objects.enabled_notification_types()
                & NotificationType.relevant_for_forwarding
            ),
            "is_sent": False,
            "timestamp__gte": cutoff_dt_for_stale,
        }
        new_eve_notifications = (
            self.notification_set.filter(**my_filter)
            .select_related("owner", "sender", "owner__corporation")
            .order_by("timestamp")
        )
        for notif in new_eve_notifications:
            notif.send_to_configured_webhooks()
        new_generated_notifications = (
            self.generatednotification_set.filter(**my_filter)
            .select_related("owner", "owner__corporation")
            .order_by("timestamp")
        )
        for notif in new_generated_notifications:
            notif.send_to_configured_webhooks()
        if (
            not new_eve_notifications.exists()
            and not new_generated_notifications.exists()
        ):
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
            "Syncing of %(topic)s for %(owner)s %(result)s.\n %(message_details)s"
        ) % {
            "topic": topic,
            "owner": self.corporation.corporation_name,
            "result": _("completed successfully"),
            "message_details": message_details,
        }
        notify(
            user,
            title=_("%(title)s: %(topic)s updated for %(owner)s: %(result)s")
            % {
                "title": _(__title__),
                "topic": topic,
                "owner": self.corporation.corporation_name,
                "result": _("OK"),
            },
            message=message,
            level="success",
        )

    def _store_raw_data(self, name: str, data: Any):
        """store raw data for debug purposes"""
        with open(
            f"{name}_raw_{self.corporation.corporation_id}.json", "w", encoding="utf-8"
        ) as f:
            json.dump(data, f, cls=DjangoJSONEncoder, sort_keys=True, indent=4)

    def update_asset_esi(self, user: Optional[User] = None):
        token = self.fetch_token()
        assets_data = self._fetch_structure_assets_from_esi(token)
        self._store_items_for_upwell_structures(assets_data)
        self._store_items_for_starbases(assets_data)
        if user:
            self._send_report_to_user(
                topic="assets", topic_count=self.structures.count(), user=user
            )

    def _fetch_structure_assets_from_esi(self, token: Token) -> dict:
        assets_raw = esi.client.Assets.get_corporations_corporation_id_assets(
            corporation_id=self.corporation.corporation_id,
            token=token.valid_access_token(),
        ).results()
        assets = {asset["item_id"]: asset for asset in assets_raw}
        positions = self._fetch_locations_for_assets(assets.keys(), token)
        for item_id, asset in assets.items():
            asset["position"] = positions[item_id] if item_id in positions else None
        return assets

    def _store_items_for_upwell_structures(self, assets_data: dict):
        structure_ids = set(
            self.structures.filter_upwell_structures().values_list("id", flat=True)
        )
        assets_in_structures = {id: dict() for id in structure_ids}
        for item_id, item in assets_data.items():
            location_id = item["location_id"]
            if location_id in structure_ids and item["location_flag"] not in [
                StructureItem.LocationFlag.CORP_DELIVERIES,
                StructureItem.LocationFlag.OFFICE_FOLDER,
                StructureItem.LocationFlag.SECONDARY_STORAGE,
                StructureItem.LocationFlag.AUTOFIT,
            ]:
                assets_in_structures[location_id][item_id] = item
        for structure in self.structures.all():
            structure_items = list()
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

                for asset in structure_assets.values():
                    structure_items.append(
                        StructureItem.from_esi_asset(asset, structure)
                    )

            structure.update_items(structure_items)
            structure.reevaluate_jump_fuel_alerts()

        self.assets_last_update_at = now()
        self.save(update_fields=["assets_last_update_at"])

    def _store_items_for_starbases(self, assets_raw: dict):
        for structure in self.structures.filter_starbases().filter(
            position_x__isnull=False, position_y__isnull=False, position_z__isnull=False
        ):
            structure_items = list()
            for item_id, item in assets_raw.items():
                if (
                    item["location_id"] == structure.eve_solar_system_id
                    and item["location_type"] == "solar_system"
                    and item["location_flag"] == "AutoFit"
                    and item_id != structure.id
                    and item["position"]
                    and structure.has_position
                    and structure.distance_to_object(
                        item["position"]["x"],
                        item["position"]["y"],
                        item["position"]["z"],
                    )
                    < 100_000
                ):
                    structure_items.append(
                        StructureItem.from_esi_asset(item, structure)
                    )
            structure.update_items(structure_items)

    @staticmethod
    def get_esi_scopes() -> List[str]:
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
        Owner,
        on_delete=models.CASCADE,
        related_name="characters",
        verbose_name=_("owner"),
    )
    character_ownership = models.ForeignKey(
        CharacterOwnership,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("character_ownership"),
        help_text="character used for syncing",
    )
    structures_last_used_at = models.DateTimeField(
        null=True,
        default=None,
        editable=False,
        db_index=True,
        verbose_name=_("structures last used at"),
        help_text="when this character was last used for syncing structures",
    )
    notifications_last_used_at = models.DateTimeField(
        null=True,
        default=None,
        editable=False,
        db_index=True,
        verbose_name=_("notifications last used at"),
        help_text="when this character was last used for syncing notifications",
    )
    error_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("error count"),
        help_text="Count of ESI errors which happened with this character.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("owner character")
        verbose_name_plural = _("owner characters")
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
