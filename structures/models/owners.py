"""Owner related models"""

import json
import math
import os
import re
from datetime import datetime, timedelta

from bravado.exception import HTTPError

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from esi.errors import TokenError, TokenExpiredError, TokenInvalidError
from esi.models import Token

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCorporationInfo
from allianceauth.notifications import notify
from allianceauth.services.hooks import get_extension_logger
from app_utils.datetime import DATETIME_FORMAT
from app_utils.helpers import chunks
from app_utils.logging import LoggerAddTag

from .. import __title__, constants
from ..app_settings import (
    STRUCTURES_ADD_TIMERS,
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_DEVELOPER_MODE,
    STRUCTURES_FEATURE_CUSTOMS_OFFICES,
    STRUCTURES_FEATURE_STARBASES,
    STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES,
    STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION,
    STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES,
    STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED,
    STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES,
)
from ..helpers.esi_fetch import esi_fetch, esi_fetch_with_localization
from ..managers import OwnerAssetManager
from .eveuniverse import EveMoon, EvePlanet, EveSolarSystem, EveType, EveUniverse
from .notifications import EveEntity, Notification, NotificationType
from .structures import Structure

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

    # errors
    ERROR_NONE = 0
    ERROR_TOKEN_INVALID = 1
    ERROR_TOKEN_EXPIRED = 2
    ERROR_INSUFFICIENT_PERMISSIONS = 3
    ERROR_NO_CHARACTER = 4
    ERROR_ESI_UNAVAILABLE = 5
    ERROR_OPERATION_MODE_MISMATCH = 6
    ERROR_UNKNOWN = 99

    ERRORS_LIST = [
        (ERROR_NONE, "No error"),
        (ERROR_TOKEN_INVALID, "Invalid token"),
        (ERROR_TOKEN_EXPIRED, "Expired token"),
        (ERROR_INSUFFICIENT_PERMISSIONS, "Insufficient permissions"),
        (ERROR_NO_CHARACTER, "No character set for fetching data from ESI"),
        (ERROR_ESI_UNAVAILABLE, "ESI API is currently unavailable"),
        (
            ERROR_OPERATION_MODE_MISMATCH,
            "Operaton mode does not match with current setting",
        ),
        (ERROR_UNKNOWN, "Unknown error"),
    ]

    corporation = models.OneToOneField(
        EveCorporationInfo,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="structure_owner",
        help_text="Corporation owning structures",
    )
    character = models.ForeignKey(
        CharacterOwnership,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
        help_text="character used for syncing structures",
    )
    structures_last_sync = models.DateTimeField(
        null=True, default=None, blank=True, help_text="when the last sync happened"
    )
    structures_last_error = models.IntegerField(
        choices=ERRORS_LIST,
        default=ERROR_NONE,
        help_text="error that occurred at the last sync atttempt (if any)",
    )
    assets_last_sync = models.DateTimeField(
        null=True, default=None, blank=True, help_text="when the last sync happened"
    )
    assets_last_error = models.IntegerField(
        choices=ERRORS_LIST,
        default=ERROR_NONE,
        help_text="error that occurred at the last sync atttempt (if any)",
    )
    notifications_last_sync = models.DateTimeField(
        null=True, default=None, blank=True, help_text="when the last sync happened"
    )
    notifications_last_error = models.IntegerField(
        choices=ERRORS_LIST,
        default=ERROR_NONE,
        help_text="error that occurred at the last sync atttempt (if any)",
    )
    forwarding_last_sync = models.DateTimeField(
        null=True, default=None, blank=True, help_text="when the last sync happened"
    )
    forwarding_last_error = models.IntegerField(
        choices=ERRORS_LIST,
        default=ERROR_NONE,
        help_text="error that occurred at the last sync atttempt (if any)",
    )
    webhooks = models.ManyToManyField(
        "Webhook",
        default=None,
        blank=True,
        help_text="notifications are sent to these webhooks. ",
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
    has_default_pings_enabled = models.BooleanField(
        default=True,
        help_text=(
            "to enable or disable pinging of notifications for this owner "
            "e.g. with @everyone and @here"
        ),
    )
    ping_groups = models.ManyToManyField(
        Group,
        default=None,
        blank=True,
        help_text="Groups to be pinged for each notification - ",
    )

    def __str__(self) -> str:
        return str(self.corporation.corporation_name)

    def __repr__(self):
        return "{}(pk={}, corporation='{}')".format(
            self.__class__.__name__, self.pk, self.corporation
        )

    @property
    def is_structure_sync_ok(self) -> bool:
        """returns true if they have been no errors
        and last syncing occurred within alloted time
        """
        return (
            self.structures_last_error == self.ERROR_NONE
            and self.structures_last_sync
            and self.structures_last_sync
            > (now() - timedelta(minutes=STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES))
        )

    @property
    def is_notification_sync_ok(self) -> bool:
        """returns true if they have been no errors
        and last syncing occurred within alloted time
        """
        return (
            self.notifications_last_error == self.ERROR_NONE
            and self.notifications_last_sync
            and self.notifications_last_sync
            > (now() - timedelta(minutes=STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES))
        )

    @property
    def is_forwarding_sync_ok(self) -> bool:
        """returns true if they have been no errors
        and last syncing occurred within alloted time
        """
        return (
            self.forwarding_last_error == self.ERROR_NONE
            and self.forwarding_last_sync
            and self.forwarding_last_sync
            > (now() - timedelta(minutes=STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES))
        )

    @property
    def is_asset_sync_ok(self) -> bool:
        """returns true if they have been no errors
        and last syncing occurred within alloted time
        """
        return (
            self.assets_last_error == self.ERROR_NONE
            and self.assets_last_sync
            and self.assets_last_sync
            > (now() - timedelta(minutes=STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES))
        )

    @property
    def are_all_syncs_ok(self) -> bool:
        """returns true if they have been no errors
        and last syncing occurred within alloted time for all sync categories
        """
        return (
            self.is_structure_sync_ok
            and self.is_notification_sync_ok
            and self.is_forwarding_sync_ok
        )

    @classmethod
    def to_friendly_error_message(cls, error) -> str:
        msg = [(x, y) for x, y in cls.ERRORS_LIST if x == error]
        return msg[0][1] if len(msg) > 0 else "Undefined error"

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

    def update_structures_esi(self, user: User = None):
        """updates all structures from ESI"""

        try:
            token, error = self.token()
            if error:
                self.structures_last_error = error
                self.structures_last_sync = now()
                self.save()
                raise TokenError(self.to_friendly_error_message(error))

            try:
                structures = self._fetch_upwell_structures(token)
                if STRUCTURES_FEATURE_CUSTOMS_OFFICES:
                    structures += self._fetch_custom_offices(token)

                if STRUCTURES_FEATURE_STARBASES:
                    structures += self._fetch_starbases(token)

                if structures:
                    logger.info(
                        "%s: Storing updates for %d structures", self, len(structures)
                    )
                else:
                    logger.info(
                        "%s: This corporation does not appear to have any structures",
                        self,
                    )

                # update structures
                for structure in structures:
                    Structure.objects.update_or_create_from_dict(structure, self)
                self.structures_last_error = self.ERROR_NONE
                self.structures_last_sync = now()
                self.save()

            except Exception as ex:
                logger.exception("%s: An unexpected error ocurred", self)
                self.structures_last_error = self.ERROR_UNKNOWN
                self.structures_last_sync = now()
                self.save()
                raise ex

        except Exception as ex:
            success = False
            error_code = str(ex)
        else:
            success = True
            error_code = None

        if user:
            self._send_report_to_user(
                "structures", self.structures.count(), success, error_code, user
            )

        return success

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

    def _fetch_upwell_structures(self, token: Token) -> list:
        """fetch Upwell structures from ESI for self"""
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
                    except HTTPError as ex:
                        logger.exception(
                            "Failed to load details for structure with ID %d due "
                            "to the following exception: %s"
                            % (structure["structure_id"], ex)
                        )
                        structure["name"] = "(no data)"

            if STRUCTURES_DEVELOPER_MODE:
                self._store_raw_data("structures", structures, corporation_id)

        except (HTTPError, ConnectionError):
            logger.exception("%s: Failed to fetch upwell structures", self)
        else:
            self._remove_structures_not_returned_from_esi(
                structures_qs=self.structures.filter_upwell_structures(),
                new_structures=structures,
            )
        return structures

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

    def _fetch_custom_offices(self, token: Token) -> list:
        """fetch custom offices from ESI for self"""

        corporation_id = self.corporation.corporation_id
        structures = list()
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
                item_ids = [x["office_id"] for x in pocos]
                positions = self._fetch_locations_for_pocos(
                    corporation_id, item_ids, token
                )
                names = self._fetch_names_for_pocos(corporation_id, item_ids, token)

                # making sure we have all solar systems loaded
                # incl. their planets for later name matching
                for solar_system_id in {int(x["system_id"]) for x in pocos}:
                    EveSolarSystem.objects.get_or_create_esi(solar_system_id)

                # compile pocos into structures list
                for poco in pocos:
                    office_id = poco["office_id"]
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
                        "type_id": constants.EVE_TYPE_ID_POCO,
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

                    structures.append(structure)

            if STRUCTURES_DEVELOPER_MODE:
                self._store_raw_data("customs_offices", structures, corporation_id)

        except (HTTPError, ConnectionError):
            logger.exception("%s: Failed to fetch custom offices", self)
        else:
            self._remove_structures_not_returned_from_esi(
                structures_qs=self.structures.filter_customs_offices(),
                new_structures=structures,
            )

        return structures

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

    def _fetch_starbases(self, token: Token) -> list:
        """Fetch starbases from ESI for self."""

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

            if STRUCTURES_DEVELOPER_MODE:
                self._store_raw_data("starbases", structures, corporation_id)

        except (HTTPError, ConnectionError):
            logger.exception("%s: Failed to fetch starbases")
        else:
            self._remove_structures_not_returned_from_esi(
                structures_qs=self.structures.filter_starbases(),
                new_structures=structures,
            )
        return structures

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

    def _calc_starbase_fuel_expires(self, corporation_id, starbase, token):

        fuel_expires_at = None
        if starbase["state"] != "offline":
            starbase_details = esi_fetch(
                "Corporation.get_corporations_corporation_id_starbases_starbase_id",
                args={
                    "corporation_id": corporation_id,
                    "starbase_id": starbase["starbase_id"],
                    "system_id": starbase["system_id"],
                },
                token=token,
            )
            fuel_quantity = None
            if "fuels" in starbase_details:
                for fuel in starbase_details["fuels"]:
                    fuel_type, _ = EveType.objects.get_or_create_esi(fuel["type_id"])
                    if fuel_type.is_fuel_block:
                        fuel_quantity = fuel["quantity"]
            if fuel_quantity:
                starbase_type, _ = EveType.objects.get_or_create_esi(
                    starbase["type_id"]
                )
                solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                    starbase["system_id"]
                )
                sov_discount = (
                    0.25 if solar_system.corporation_has_sov(self.corporation) else 0
                )
                hours = math.floor(
                    fuel_quantity
                    / (starbase_type.starbase_fuel_per_hour * (1 - sov_discount))
                )
                fuel_expires_at = now() + timedelta(hours=hours)

        return fuel_expires_at

    def fetch_notifications_esi(self, user: User = None) -> bool:
        """fetches notification for the current owners and proceses them"""
        notifications_count_all = 0
        try:
            token, error = self.token()
            if error:
                self.notifications_last_error = error
                self.notifications_last_sync = now()
                self.save()
                raise TokenError(self.to_friendly_error_message(error))

            # fetch notifications from ESI
            try:
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

                self.notifications_last_error = self.ERROR_NONE
                self.notifications_last_sync = now()
                self.save()

            except Exception as ex:
                logger.exception("%s: An unexpected error ocurred %s", self, ex)
                self.notifications_last_error = self.ERROR_UNKNOWN
                self.notifications_last_sync = now()
                self.save()
                raise ex

        except Exception as ex:
            success = False
            error_code = str(ex)
        else:
            success = True
            error_code = None

        if user:
            self._send_report_to_user(
                "notifications", notifications_count_all, success, error_code, user
            )

        return success

    def _fetch_notifications_from_esi(self, token: Token) -> dict:
        """fetching all notifications from ESI for current owner"""

        notifications = esi_fetch(
            "Character.get_characters_character_id_notifications",
            args={"character_id": self.character.character.character_id},
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
        self.notifications_last_error = self.ERROR_NONE
        self.save()
        return len(new_notification_objects)

    def _process_timers_for_notifications(self, token: Token):
        """processes notifications for timers if any"""
        if STRUCTURES_ADD_TIMERS:
            cutoff_dt_for_stale = now() - timedelta(
                hours=STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
            )
            notifications = (
                Notification.objects.filter(owner=self)
                .filter(notif_type__in=NotificationType.relevant_for_timerboard)
                .exclude(is_timer_added=True)
                .filter(timestamp__gte=cutoff_dt_for_stale)
                .select_related("owner", "sender")
                .order_by("timestamp")
            )
            if notifications.exists():
                if not token:
                    token = self.token()
                for notification in notifications:
                    notification.process_for_timerboard(token)

    def _process_moon_notifications(self):
        """processes notifications for timers if any"""
        empty_refineries = Structure.objects.filter(
            owner=self,
            eve_type__eve_group_id=constants.EVE_GROUP_ID_REFINERY,
            eve_moon__isnull=True,
        )
        if empty_refineries:
            logger.info(
                "%s: Trying to find moons for up to %d refineries which have no moon.",
                self,
                empty_refineries.count(),
            )
            notifications = (
                Notification.objects.filter(owner=self)
                .filter(notif_type__in=NotificationType.relevant_for_moonmining)
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

    def send_new_notifications(self, user: User = None) -> bool:
        """forwards all new notification for this owner to Discord"""

        notifications_count = 0
        try:
            try:
                cutoff_dt_for_stale = now() - timedelta(
                    hours=STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
                )
                all_new_notifications = list(
                    Notification.objects.filter(owner=self)
                    .filter(notif_type__in=NotificationType.values)
                    .filter(is_sent=False)
                    .filter(timestamp__gte=cutoff_dt_for_stale)
                    .select_related()
                    .order_by("timestamp")
                )
                new_notifications_count = 0
                active_webhooks_count = 0
                for webhook in self.webhooks.filter(is_active=True):
                    active_webhooks_count += 1
                    new_notifications = [
                        notif
                        for notif in all_new_notifications
                        if str(notif.notif_type) in webhook.notification_types
                    ]
                    if len(new_notifications) > 0:
                        new_notifications_count += len(new_notifications)
                        logger.info(
                            "%s: Found %d new notifications for webhook %s",
                            self,
                            len(new_notifications),
                            webhook,
                        )
                        notifications_count += self._send_notifications_to_webhook(
                            new_notifications, webhook
                        )

                if active_webhooks_count == 0:
                    logger.info("%s: No active webhooks", self)

                if new_notifications_count == 0:
                    logger.info("%s: No new notifications found", self)

                self.forwarding_last_error = self.ERROR_NONE
                self.forwarding_last_sync = now()
                self.save()

            except TokenError:
                pass

            except Exception as ex:
                logger.exception("%s: An unexpected error ocurred", self)
                self.forwarding_last_error = self.ERROR_UNKNOWN
                self.forwarding_last_sync = now()
                self.save()
                raise ex

        except Exception as ex:
            success = False
            error_code = str(ex)
        else:
            success = True
            error_code = None

        if user:
            self._send_report_to_user(
                "notifications", notifications_count, success, error_code, user
            )

        return success

    def _send_notifications_to_webhook(self, new_notifications, webhook) -> int:
        """sends all notifications to given webhook"""
        sent_count = 0
        for notification in new_notifications:
            if (
                not notification.filter_for_npc_attacks()
                and not notification.filter_for_alliance_level()
            ):
                if notification.send_to_webhook(webhook):
                    sent_count += 1

        return sent_count

    def token(self) -> Token:
        """returns a valid Token for the owner"""
        token = None
        error = None

        # abort if character is not configured
        if self.character is None:
            logger.error("%s: No character configured to sync", self)
            error = self.ERROR_NO_CHARACTER

        # abort if character does not have sufficient permissions
        elif not self.character.user.has_perm("structures.add_structure_owner"):
            logger.error(
                "%s: self character does not have sufficient permission to sync", self
            )
            error = self.ERROR_INSUFFICIENT_PERMISSIONS

        else:
            try:
                # get token
                token = (
                    Token.objects.filter(
                        user=self.character.user,
                        character_id=self.character.character.character_id,
                    )
                    .require_scopes(self.get_esi_scopes())
                    .require_valid()
                    .first()
                )
            except TokenInvalidError:
                logger.error("%s: Invalid token for fetching structures", self)
                error = self.ERROR_TOKEN_INVALID
            except TokenExpiredError:
                logger.error("%s: Token expired for fetching structures", self)
                error = self.ERROR_TOKEN_EXPIRED
            else:
                if not token:
                    logger.error("%s: No token found with sufficient scopes", self)
                    error = self.ERROR_TOKEN_INVALID

        return token, error

    def _send_report_to_user(
        self, topic: str, topic_count: int, success: bool, error_code, user
    ):

        try:
            if success:
                message_details = "%(count)s %(topic)s synced." % {
                    "count": topic_count,
                    "topic": topic,
                }
            else:
                message_details = _("Error: %s") % error_code

            message = _(
                'Syncing of %(topic)s for "%(owner)s" %(result)s.\n'
                "%(message_details)s"
            ) % {
                "topic": topic,
                "owner": self.corporation.corporation_name,
                "result": _("completed successfully") if success else _("has failed"),
                "message_details": message_details,
            }

            notify(
                user,
                title=_("%(title)s: %(topic)s updated for " "%(owner)s: %(result)s")
                % {
                    "title": _(__title__),
                    "topic": topic,
                    "owner": self.corporation.corporation_name,
                    "result": _("OK") if success else _("FAILED"),
                },
                message=message,
                level="success" if success else "danger",
            )
        except Exception as ex:
            logger.exception(
                "%s: An unexpected error ocurred while trying to report to user", self
            )
            if settings.DEBUG:
                raise ex

    @staticmethod
    def _store_raw_data(name: str, data: list, corporation_id: int):
        """store raw data for debug purposes"""
        with open(f"{name}_raw_{corporation_id}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, cls=DjangoJSONEncoder, sort_keys=True, indent=4)

    def update_asset_esi(self, user: User = None):
        """Update all assets for owner where location_id is in the active structure list from esi"""

        try:
            token, error = self.token()
            if error:
                self.assets_last_error = error
                self.assets_last_sync = now()
                self.save()
                raise TokenError(self.to_friendly_error_message(error))

            try:
                structure_ids = {x.id for x in Structure.objects.filter(owner=self)}
                OwnerAsset.objects.update_or_create_for_structures_esi(
                    structure_ids, self.corporation.corporation_id, token
                )
            except Exception as ex:
                logger.exception("%s: An unexpected error ocurred", self)
                self.assets_last_error = self.ERROR_UNKNOWN
                self.assets_last_sync = now()
                self.save()
                raise ex
        except Exception as ex:
            success = False
            error_code = str(ex)
        else:
            success = True
            error_code = None
            self.assets_last_error = self.ERROR_NONE
            self.assets_last_sync = now()
            self.save()

        if user:
            self._send_report_to_user(
                "assets", self.structures.count(), success, error_code, user
            )


class OwnerAsset(models.Model):
    """An asset for a corporation"""

    id = models.BigIntegerField(primary_key=True, help_text="The Item ID of the assets")
    eve_type = models.ForeignKey(
        "EveType",
        on_delete=models.CASCADE,
        help_text="type of the assets",
        related_name="+",
    )
    owner = models.ForeignKey(
        "Owner",
        on_delete=models.CASCADE,
        related_name="assets",
        help_text="Corporation that owns the assets",
    )
    is_singleton = models.BooleanField(null=False)
    location_flag = models.CharField(max_length=255)
    location_id = models.BigIntegerField(null=False, db_index=True)
    location_type = models.CharField(max_length=255)
    quantity = models.IntegerField(null=False)
    last_updated_at = models.DateTimeField(auto_now=True)

    objects = OwnerAssetManager()

    def __str__(self) -> str:
        return str(self.eve_type.name)

    def __repr__(self):
        return "{}(pk={}, owner=<{}>, eve_type=<{}>)".format(
            self.__class__.__name__, self.pk, self.owner, self.eve_type
        )
