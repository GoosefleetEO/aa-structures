"""Notification related models"""

from datetime import datetime, timedelta
import json
import logging
from time import sleep
import yaml

import pytz
import dhooks_lite

from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from django.utils.translation import gettext_lazy as _, gettext
from django.utils import translation

from allianceauth.eveonline.evelinks import dotlan

from esi.models import Token
from multiselectfield import MultiSelectField

from ..app_settings import (
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_DEVELOPER_MODE,
    STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED,
    STRUCTURES_NOTIFICATION_MAX_RETRIES,
    STRUCTURES_NOTIFICATION_WAIT_SEC,
    STRUCTURES_REPORT_NPC_ATTACKS,
    STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
)
from .. import __title__
from ..managers import EveEntityManager
from ..utils import LoggerAddTag, DATETIME_FORMAT, make_logger_prefix, app_labels
from .eveuniverse import EveType, EveSolarSystem, EveMoon, EvePlanet
from .structures import Structure

if "timerboard" in app_labels():
    from allianceauth.timerboard.models import Timer as AuthTimer

    has_auth_timers = True
else:
    has_auth_timers = False

if "structuretimers" in app_labels():
    from structuretimers.models import Timer
    from eveuniverse.models import (
        EveSolarSystem as EveSolarSystem2,
        EveType as EveType2,
    )

    has_structure_timers = True
else:
    has_structure_timers = False

logger = LoggerAddTag(logging.getLogger(__name__), __title__)

# Supported languages
LANGUAGES = (
    ("en", _("English")),
    ("de", _("German")),
    ("es", _("Spanish")),
    ("zh-hans", _("Chinese Simplified")),
    ("ru", _("Russian")),
    ("ko", _("Korean")),
)

# Notification types
NTYPE_MOONS_AUTOMATIC_FRACTURE = 401
NTYPE_MOONS_EXTRACTION_CANCELED = 402
NTYPE_MOONS_EXTRACTION_FINISHED = 403
NTYPE_MOONS_EXTRACTION_STARTED = 404
NTYPE_MOONS_LASER_FIRED = 405

NTYPE_STRUCTURE_ANCHORING = 501
NTYPE_STRUCTURE_DESTROYED = 502
NTYPE_STRUCTURE_FUEL_ALERT = 503
NTYPE_STRUCTURE_LOST_ARMOR = 504
NTYPE_STRUCTURE_LOST_SHIELD = 505
NTYPE_STRUCTURE_ONLINE = 506
NTYPE_STRUCTURE_SERVICES_OFFLINE = 507
NTYPE_STRUCTURE_UNANCHORING = 508
NTYPE_STRUCTURE_UNDER_ATTACK = 509
NTYPE_STRUCTURE_WENT_HIGH_POWER = 510
NTYPE_STRUCTURE_WENT_LOW_POWER = 511
NTYPE_STRUCTURE_REINFORCE_CHANGED = 512
NTYPE_OWNERSHIP_TRANSFERRED = 513

NTYPE_ORBITAL_ATTACKED = 601
NTYPE_ORBITAL_REINFORCED = 602

NTYPE_TOWER_ALERT_MSG = 701
NTYPE_TOWER_RESOURCE_ALERT_MSG = 702

NTYPE_SOV_ENTOSIS_CAPTURE_STARTED = 801
NTYPE_SOV_COMMAND_NODE_EVENT_STARTED = 802
NTYPE_SOV_ALL_CLAIM_ACQUIRED_MSG = 803
NTYPE_SOV_STRUCTURE_REINFORCED = 804
NTYPE_SOV_STRUCTURE_DESTROYED = 805

NTYPE_CHOICES = [
    # moon mining
    (NTYPE_MOONS_AUTOMATIC_FRACTURE, "MoonminingAutomaticFracture"),
    (NTYPE_MOONS_EXTRACTION_CANCELED, "MoonminingExtractionCancelled"),
    (NTYPE_MOONS_EXTRACTION_FINISHED, "MoonminingExtractionFinished"),
    (NTYPE_MOONS_EXTRACTION_STARTED, "MoonminingExtractionStarted"),
    (NTYPE_MOONS_LASER_FIRED, "MoonminingLaserFired"),
    # upwell structures general
    (NTYPE_OWNERSHIP_TRANSFERRED, "OwnershipTransferred"),
    (NTYPE_STRUCTURE_ANCHORING, "StructureAnchoring"),
    (NTYPE_STRUCTURE_DESTROYED, "StructureDestroyed"),
    (NTYPE_STRUCTURE_FUEL_ALERT, "StructureFuelAlert"),
    (NTYPE_STRUCTURE_LOST_ARMOR, "StructureLostArmor"),
    (NTYPE_STRUCTURE_LOST_SHIELD, "StructureLostShields"),
    (NTYPE_STRUCTURE_ONLINE, "StructureOnline"),
    (NTYPE_STRUCTURE_SERVICES_OFFLINE, "StructureServicesOffline"),
    (NTYPE_STRUCTURE_UNANCHORING, "StructureUnanchoring"),
    (NTYPE_STRUCTURE_UNDER_ATTACK, "StructureUnderAttack"),
    (NTYPE_STRUCTURE_WENT_HIGH_POWER, "StructureWentHighPower"),
    (NTYPE_STRUCTURE_WENT_LOW_POWER, "StructureWentLowPower"),
    # custom offices only
    (NTYPE_ORBITAL_ATTACKED, "OrbitalAttacked"),
    (NTYPE_ORBITAL_REINFORCED, "OrbitalReinforced"),
    # starbases only
    (NTYPE_TOWER_ALERT_MSG, "TowerAlertMsg"),
    (NTYPE_TOWER_RESOURCE_ALERT_MSG, "TowerResourceAlertMsg"),
    # sov
    (NTYPE_SOV_ENTOSIS_CAPTURE_STARTED, "EntosisCaptureStarted"),
    (NTYPE_SOV_COMMAND_NODE_EVENT_STARTED, "SovCommandNodeEventStarted"),
    (NTYPE_SOV_ALL_CLAIM_ACQUIRED_MSG, "SovAllClaimAquiredMsg"),
    (NTYPE_SOV_STRUCTURE_REINFORCED, "SovStructureReinforced"),
    (NTYPE_SOV_STRUCTURE_DESTROYED, "SovStructureDestroyed"),
]

_NTYPE_RELEVANT_FOR_TIMERBOARD = [
    NTYPE_STRUCTURE_LOST_SHIELD,
    NTYPE_STRUCTURE_LOST_ARMOR,
    NTYPE_STRUCTURE_ANCHORING,
    NTYPE_ORBITAL_REINFORCED,
    NTYPE_MOONS_EXTRACTION_STARTED,
    NTYPE_MOONS_EXTRACTION_CANCELED,
    NTYPE_SOV_STRUCTURE_REINFORCED,
]

NTYPE_FOR_ALLIANCE_LEVEL = [
    NTYPE_SOV_ENTOSIS_CAPTURE_STARTED,
    NTYPE_SOV_COMMAND_NODE_EVENT_STARTED,
    NTYPE_SOV_ALL_CLAIM_ACQUIRED_MSG,
    NTYPE_SOV_STRUCTURE_REINFORCED,
    NTYPE_SOV_STRUCTURE_DESTROYED,
]


def get_default_notification_types():
    """generates a set of all existing notification types as default"""
    return tuple(sorted([str(x[0]) for x in NTYPE_CHOICES]))


class Webhook(models.Model):
    """A destination for forwarding notification alerts"""

    TYPE_DISCORD = 1

    TYPE_CHOICES = [
        (TYPE_DISCORD, _("Discord Webhook")),
    ]

    name = models.CharField(
        max_length=64, unique=True, help_text="short name to identify this webhook"
    )
    webhook_type = models.IntegerField(
        choices=TYPE_CHOICES, default=TYPE_DISCORD, help_text="type of this webhook"
    )
    url = models.CharField(
        max_length=255,
        unique=True,
        help_text=(
            "URL of this webhook, e.g. "
            "https://discordapp.com/api/webhooks/123456/abcdef"
        ),
    )
    notes = models.TextField(
        null=True,
        default=None,
        blank=True,
        help_text="you can add notes about this webhook here if you want",
    )
    notification_types = MultiSelectField(
        choices=NTYPE_CHOICES,
        default=get_default_notification_types,
        help_text=("only notifications which selected types are sent to this webhook"),
    )
    language_code = models.CharField(
        max_length=8,
        choices=LANGUAGES,
        default=None,
        null=True,
        blank=True,
        verbose_name="language",
        help_text="language of notifications send to this webhook",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="whether notifications are currently sent to this webhook",
    )
    is_default = models.BooleanField(
        default=False,
        help_text=(
            "whether owners have this webhook automatically " "pre-set when created"
        ),
    )
    has_pings_enabled = models.BooleanField(
        default=True,
        help_text=(
            "to enable or disable pinging of notifications for this webhook "
            "e.g. with @everyone and @here"
        ),
    )

    def __str__(self):
        return self.name

    def __repr__(self):
        return "{}(id={}, name='{}')".format(
            self.__class__.__name__, self.id, self.name
        )

    def send_test_notification(self) -> str:
        """Sends a test notification to this webhook and returns send report"""
        hook = dhooks_lite.Webhook(self.url)
        response = hook.execute(
            _(
                "This is a test notification from %s.\n"
                "The webhook appears to be correctly configured."
            )
            % __title__,
            wait_for_response=True,
        )
        if response.status_ok:
            send_report_json = json.dumps(response.content, indent=4, sort_keys=True)
        else:
            send_report_json = "HTTP status code {}".format(response.status_code)
        return send_report_json


class EveEntity(models.Model):
    """An EVE entity like a character or an alliance"""

    CATEGORY_CHARACTER = 1
    CATEGORY_CORPORATION = 2
    CATEGORY_ALLIANCE = 3
    CATEGORY_FACTION = 4
    CATEGORY_OTHER = 5

    CATEGORY_CHOICES = [
        (CATEGORY_CHARACTER, "character"),
        (CATEGORY_CORPORATION, "corporation"),
        (CATEGORY_ALLIANCE, "alliance"),
        (CATEGORY_FACTION, "faction"),
        (CATEGORY_OTHER, "other"),
    ]

    id = models.PositiveIntegerField(primary_key=True, help_text="Eve Online ID")
    category = models.IntegerField(choices=CATEGORY_CHOICES)
    name = models.CharField(max_length=255, null=True, default=None, blank=True)

    objects = EveEntityManager()

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return "{}(id={}, category='{}', name='{}')".format(
            self.__class__.__name__, self.id, self.get_category_display(), self.name
        )

    def profile_url(self) -> str:
        """returns link to website with profile info about this entity"""
        if self.category == self.CATEGORY_CORPORATION:
            url = dotlan.corporation_url(self.name)
        elif self.category == self.CATEGORY_ALLIANCE:
            url = dotlan.alliance_url(self.name)
        else:
            url = ""
        return url

    @classmethod
    def get_matching_entity_category(cls, type_name) -> int:
        """returns category for given ESI name"""
        match = None
        for x in cls.CATEGORY_CHOICES:
            if type_name == x[1]:
                match = x
                break
        return match[0] if match else cls.CATEGORY_OTHER


class Notification(models.Model):
    """An EVE Online notification about structures"""

    # embed colors
    EMBED_COLOR_INFO = 0x5BC0DE
    EMBED_COLOR_SUCCESS = 0x5CB85C
    EMBED_COLOR_WARNING = 0xF0AD4E
    EMBED_COLOR_DANGER = 0xD9534F

    HTTP_CODE_TOO_MANY_REQUESTS = 429

    # event type structure map
    MAP_CAMPAIGN_EVENT_2_TYPE_ID = {
        1: EveType.EVE_TYPE_ID_TCU,
        2: EveType.EVE_TYPE_ID_IHUB,
    }

    MAP_TYPE_ID_2_TIMER_STRUCTURE_NAME = {2233: "POCO", 32226: "TCU", 32458: "I-HUB"}

    notification_id = models.BigIntegerField(validators=[MinValueValidator(0)])
    owner = models.ForeignKey(
        "Owner",
        on_delete=models.CASCADE,
        help_text="Corporation that received this notification",
    )
    sender = models.ForeignKey(EveEntity, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    notification_type = models.IntegerField(choices=NTYPE_CHOICES)
    text = models.TextField(
        null=True, default=None, blank=True, help_text="Notification details in YAML"
    )
    is_read = models.BooleanField(
        null=True,
        default=None,
        blank=True,
        help_text="True when this notification has read in the eve client",
    )
    is_sent = models.BooleanField(
        default=False,
        blank=True,
        help_text="True when this notification has been forwarded to Discord",
    )
    is_timer_added = models.BooleanField(
        null=True,
        default=None,
        blank=True,
        help_text="True when a timer has been added for this notification",
    )
    last_updated = models.DateTimeField(
        help_text="Date when this notification has last been updated from ESI"
    )
    created = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="Date when this notification was first received from ESI",
    )

    class Meta:
        unique_together = (("notification_id", "owner"),)

    def __str__(self):
        return str(self.notification_id)

    def __repr__(self):
        return "%s(notification_id=%d, owner='%s', notification_type='%s')" % (
            self.__class__.__name__,
            self.notification_id,
            self.owner,
            self.get_notification_type_display(),
        )

    @property
    def is_alliance_level(self):
        """whether this is an alliance level notification"""
        return self.notification_type in NTYPE_FOR_ALLIANCE_LEVEL

    @classmethod
    def get_all_types(cls):
        """returns a set with all supported notification types"""
        return {x[0] for x in NTYPE_CHOICES}

    @classmethod
    def get_all_type_names(cls):
        """returns a set with names of all supported notification types"""
        return {x[1] for x in NTYPE_CHOICES}

    @classmethod
    def get_types_for_timerboard(cls):
        """returns set of types relevant for the timerboard"""
        return _NTYPE_RELEVANT_FOR_TIMERBOARD

    @classmethod
    def get_matching_notification_type(cls, type_name) -> int:
        """returns matching notification type for given name or None"""
        match = None
        for x in NTYPE_CHOICES:
            if type_name == x[1]:
                match = x
                break

        return match[0] if match else None

    def get_parsed_text(self) -> dict:
        """returns the notifications's text as dict"""
        return yaml.safe_load(self.text)

    def is_npc_attacking(self):
        """ whether this notification is about a NPC attacking"""
        result = False
        if self.notification_type in [
            NTYPE_ORBITAL_ATTACKED,
            NTYPE_STRUCTURE_UNDER_ATTACK,
        ]:
            parsed_text = self.get_parsed_text()
            corporation_id = None
            if self.notification_type == NTYPE_STRUCTURE_UNDER_ATTACK:
                if (
                    "corpLinkData" in parsed_text
                    and len(parsed_text["corpLinkData"]) >= 3
                ):
                    corporation_id = int(parsed_text["corpLinkData"][2])

            if self.notification_type == NTYPE_ORBITAL_ATTACKED:
                if "aggressorCorpID" in parsed_text:
                    corporation_id = int(parsed_text["aggressorCorpID"])

            if 1000000 <= corporation_id <= 2000000:
                result = True

        return result

    def filter_for_npc_attacks(self):
        """true when notification to be filtered out due to npc attacks"""
        return not STRUCTURES_REPORT_NPC_ATTACKS and self.is_npc_attacking()

    def filter_for_alliance_level(self):
        """true when notification to be filtered out due to alliance level"""
        return self.is_alliance_level and not self.owner.is_alliance_main

    def send_to_webhook(self, webhook: Webhook) -> bool:
        """sends this notification to the configured webhook
        returns True if successful, else False
        """
        add_prefix = make_logger_prefix("notification:{}".format(self.notification_id))
        logger.info(add_prefix("Trying to sent to webhook: %s" % webhook))
        if self.is_alliance_level:
            avatar_url = self.owner.corporation.alliance.logo_url()
            ticker = self.owner.corporation.alliance.alliance_ticker
        else:
            avatar_url = self.owner.corporation.logo_url()
            ticker = self.owner.corporation.corporation_ticker

        username = gettext("%(ticker)s Notification") % {"ticker": ticker}
        hook = dhooks_lite.Webhook(
            webhook.url, username=username, avatar_url=avatar_url
        )
        success = False
        try:
            embed = self._generate_embed(webhook.language_code)
        except Exception as ex:
            logger.warning(add_prefix("Failed to generate embed: %s" % ex))
            raise ex
        else:
            if webhook.has_pings_enabled and self.owner.has_pings_enabled:
                if embed.color == self.EMBED_COLOR_DANGER:
                    content = "@everyone"
                elif embed.color == self.EMBED_COLOR_WARNING:
                    content = "@here"
                else:
                    content = None
            else:
                content = None

            success = self._execute_webhook(hook, content, embed, add_prefix)
        return success

    @classmethod
    def _ldap_datetime_2_dt(cls, ldap_dt: int) -> datetime:
        """converts ldap time to datatime"""
        return pytz.utc.localize(
            datetime.utcfromtimestamp((ldap_dt / 10000000) - 11644473600)
        )

    @classmethod
    def _ldap_timedelta_2_timedelta(cls, ldap_td: int) -> timedelta:
        """converts a ldap timedelta into a dt timedelta"""
        return timedelta(microseconds=ldap_td / 10)

    def _generate_embed(self, language_code: str) -> dhooks_lite.Embed:
        """generates a Discord embed for this notification"""

        logger.info("Creating embed with language = %s" % language_code)
        parsed_text = self.get_parsed_text()

        with translation.override(language_code):
            if self.notification_type in [
                NTYPE_STRUCTURE_FUEL_ALERT,
                NTYPE_STRUCTURE_SERVICES_OFFLINE,
                NTYPE_STRUCTURE_WENT_LOW_POWER,
                NTYPE_STRUCTURE_WENT_HIGH_POWER,
                NTYPE_STRUCTURE_UNANCHORING,
                NTYPE_STRUCTURE_UNDER_ATTACK,
                NTYPE_STRUCTURE_LOST_SHIELD,
                NTYPE_STRUCTURE_LOST_ARMOR,
                NTYPE_STRUCTURE_DESTROYED,
                NTYPE_STRUCTURE_ONLINE,
            ]:
                title, description, color, thumbnail = self._gen_embed_structures_1(
                    parsed_text
                )

            elif self.notification_type in [
                NTYPE_OWNERSHIP_TRANSFERRED,
                NTYPE_STRUCTURE_ANCHORING,
            ]:
                title, description, color, thumbnail = self._gen_embed_structures_2(
                    parsed_text
                )

            elif self.notification_type in [
                NTYPE_MOONS_AUTOMATIC_FRACTURE,
                NTYPE_MOONS_EXTRACTION_CANCELED,
                NTYPE_MOONS_EXTRACTION_FINISHED,
                NTYPE_MOONS_EXTRACTION_STARTED,
                NTYPE_MOONS_LASER_FIRED,
            ]:
                title, description, color, thumbnail = self._gen_embed_moons(
                    parsed_text
                )

            elif self.notification_type in [
                NTYPE_ORBITAL_ATTACKED,
                NTYPE_ORBITAL_REINFORCED,
            ]:
                title, description, color, thumbnail = self._gen_embed_pocos(
                    parsed_text
                )

            elif self.notification_type in [
                NTYPE_TOWER_ALERT_MSG,
                NTYPE_TOWER_RESOURCE_ALERT_MSG,
            ]:
                title, description, color, thumbnail = self._gen_embed_poses(
                    parsed_text
                )

            elif self.notification_type in [
                NTYPE_SOV_ENTOSIS_CAPTURE_STARTED,
                NTYPE_SOV_COMMAND_NODE_EVENT_STARTED,
                NTYPE_SOV_ALL_CLAIM_ACQUIRED_MSG,
                NTYPE_SOV_STRUCTURE_REINFORCED,
                NTYPE_SOV_STRUCTURE_DESTROYED,
            ]:
                title, description, color, thumbnail = self._gen_embed_sov(parsed_text)

            else:
                raise NotImplementedError("type: {}".format(self.notification_type))

        if STRUCTURES_DEVELOPER_MODE:
            footer = dhooks_lite.Footer(self.notification_id)
        else:
            footer = None

        return dhooks_lite.Embed(
            title=title,
            description=description,
            color=color,
            thumbnail=thumbnail,
            timestamp=self.timestamp,
            footer=footer,
        )

    def _gen_embed_structures_1(self, parsed_text: dict) -> tuple:

        try:
            my_structure = Structure.objects.get(id=parsed_text["structureID"])
            structure_name = my_structure.name
            structure_type = my_structure.eve_type
            structure_solar_system = my_structure.eve_solar_system
        except Structure.DoesNotExist:
            my_structure = None
            structure_name = gettext("(unknown)")
            structure_type, _ = EveType.objects.get_or_create_esi(
                parsed_text["structureTypeID"]
            )
            structure_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                parsed_text["solarsystemID"]
            )

        description = gettext(
            "The %(structure_type)s %(structure_name)s in %(solar_system)s "
        ) % {
            "structure_type": structure_type.name_localized,
            "structure_name": "**%s**" % structure_name,
            "solar_system": self._gen_solar_system_text(structure_solar_system),
        }
        if self.notification_type == NTYPE_STRUCTURE_ONLINE:
            title = gettext("Structure online")
            description += gettext("is now online.")
            color = self.EMBED_COLOR_SUCCESS

        elif self.notification_type == NTYPE_STRUCTURE_FUEL_ALERT:
            title = gettext("Structure fuel alert")
            description += gettext("has less then 24hrs fuel left.")
            color = self.EMBED_COLOR_WARNING

        elif self.notification_type == NTYPE_STRUCTURE_SERVICES_OFFLINE:
            title = gettext("Structure services off-line")
            description += gettext("has all services off-lined.")
            if my_structure and my_structure.structureservice_set.count() > 0:
                qs = my_structure.structureservice_set.all().order_by("name")
                services_list = "\n".join([x.name for x in qs])
                description += "\n*{}*".format(services_list)

            color = self.EMBED_COLOR_DANGER

        elif self.notification_type == NTYPE_STRUCTURE_WENT_LOW_POWER:
            title = gettext("Structure low power")
            description += gettext("went to low power mode.")
            color = self.EMBED_COLOR_WARNING

        elif self.notification_type == NTYPE_STRUCTURE_WENT_HIGH_POWER:
            title = gettext("Structure full power")
            description += gettext("went to full power mode.")
            color = self.EMBED_COLOR_SUCCESS

        elif self.notification_type == NTYPE_STRUCTURE_UNANCHORING:
            title = gettext("Structure un-anchoring")
            unanchored_at = self.timestamp + self._ldap_timedelta_2_timedelta(
                parsed_text["timeLeft"]
            )
            description += gettext(
                "has started un-anchoring. " "It will be fully un-anchored at: %s"
            ) % unanchored_at.strftime(DATETIME_FORMAT)
            color = self.EMBED_COLOR_INFO

        elif self.notification_type == NTYPE_STRUCTURE_UNDER_ATTACK:
            title = gettext("Structure under attack")
            description += gettext("is under attack by %s") % self._get_attacker_link(
                parsed_text
            )
            color = self.EMBED_COLOR_DANGER

        elif self.notification_type == NTYPE_STRUCTURE_LOST_SHIELD:
            title = gettext("Structure lost shield")
            timer_ends_at = self.timestamp + self._ldap_timedelta_2_timedelta(
                parsed_text["timeLeft"]
            )
            description += gettext(
                "has lost its shields. Armor timer end at: %s"
            ) % timer_ends_at.strftime(DATETIME_FORMAT)
            color = self.EMBED_COLOR_DANGER

        elif self.notification_type == NTYPE_STRUCTURE_LOST_ARMOR:
            title = gettext("Structure lost armor")
            timer_ends_at = self.timestamp + self._ldap_timedelta_2_timedelta(
                parsed_text["timeLeft"]
            )
            description += gettext(
                "has lost its armor. Hull timer end at: %s"
            ) % timer_ends_at.strftime(DATETIME_FORMAT)
            color = self.EMBED_COLOR_DANGER

        elif self.notification_type == NTYPE_STRUCTURE_DESTROYED:
            title = gettext("Structure destroyed")
            description += gettext("has been destroyed.")
            color = self.EMBED_COLOR_DANGER

        else:
            raise NotImplementedError()

        thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())
        return title, description, color, thumbnail

    def _gen_embed_structures_2(self, parsed_text: dict) -> tuple:
        structure_type, _ = EveType.objects.get_or_create_esi(
            parsed_text["structureTypeID"]
        )
        if self.notification_type == NTYPE_OWNERSHIP_TRANSFERRED:
            solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                parsed_text["solarSystemID"]
            )
            description = gettext(
                "The %(structure_type)s %(structure_name)s " "in %(solar_system)s "
            ) % {
                "structure_type": structure_type.name,
                "structure_name": "**%s**" % parsed_text["structureName"],
                "solar_system": self._gen_solar_system_text(solar_system),
            }
            from_corporation, _ = EveEntity.objects.get_or_create_esi(
                parsed_text["oldOwnerCorpID"]
            )
            to_corporation, _ = EveEntity.objects.get_or_create_esi(
                parsed_text["newOwnerCorpID"]
            )
            character, _ = EveEntity.objects.get_or_create_esi(parsed_text["charID"])
            description += gettext(
                "has been transferred from %(from_corporation)s "
                "to %(to_corporation)s by %(character)s."
            ) % {
                "from_corporation": self._gen_corporation_link(from_corporation.name),
                "to_corporation": self._gen_corporation_link(to_corporation.name),
                "character": character.name,
            }
            title = gettext("Ownership transferred")
            color = self.EMBED_COLOR_INFO

        elif self.notification_type == NTYPE_STRUCTURE_ANCHORING:
            solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                parsed_text["solarsystemID"]
            )
            description = gettext(
                "%(structure_type)s has started anchoring " "in %(solar_system)s. "
            ) % {
                "structure_type": structure_type.name_localized,
                "solar_system": self._gen_solar_system_text(solar_system),
            }
            if not solar_system.is_null_sec:
                unanchored_at = self.timestamp + timedelta(hours=24)
                description += "The anchoring timer ends at: {}".format(
                    unanchored_at.strftime(DATETIME_FORMAT)
                )
            title = gettext("Structure anchoring")
            color = self.EMBED_COLOR_INFO

        else:
            raise NotImplementedError()

        thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())
        return title, description, color, thumbnail

    def _gen_embed_moons(self, parsed_text: dict) -> tuple:
        moon, _ = EveMoon.objects.get_or_create_esi(parsed_text["moonID"])
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text["solarSystemID"]
        )
        solar_system_link = self._gen_solar_system_text(solar_system)
        structure_name = parsed_text["structureName"]
        if self.notification_type == NTYPE_MOONS_EXTRACTION_STARTED:
            started_by, _ = EveEntity.objects.get_or_create_esi(
                parsed_text["startedBy"]
            )
            ready_time = self._ldap_datetime_2_dt(parsed_text["readyTime"])
            auto_time = self._ldap_datetime_2_dt(parsed_text["autoTime"])
            title = gettext("Moon mining extraction started")
            description = gettext(
                "A moon mining extraction has been started "
                "for %(structure_name)s at %(moon)s in %(solar_system)s. "
                "Extraction was started by %(character)s.\n"
                "The chunk will be ready on location at %(ready_time)s, "
                "and will autofracture on %(auto_time)s.\n"
            ) % {
                "structure_name": "**%s**" % structure_name,
                "moon": moon.name_localized,
                "solar_system": solar_system_link,
                "character": started_by,
                "ready_time": ready_time.strftime(DATETIME_FORMAT),
                "auto_time": auto_time.strftime(DATETIME_FORMAT),
            }
            color = self.EMBED_COLOR_INFO

        elif self.notification_type == NTYPE_MOONS_EXTRACTION_FINISHED:
            auto_time = self._ldap_datetime_2_dt(parsed_text["autoTime"])
            title = gettext("Extraction finished")
            description = gettext(
                "The extraction for %(structure_name)s at %(moon)s "
                "in %(solar_system)s is finished and the chunk is ready "
                "to be shot at.\n"
                "The chunk will automatically fracture on %(auto_time)s."
            ) % {
                "structure_name": "**%s**" % structure_name,
                "moon": moon.name_localized,
                "solar_system": solar_system_link,
                "auto_time": auto_time.strftime(DATETIME_FORMAT),
            }
            color = self.EMBED_COLOR_INFO

        elif self.notification_type == NTYPE_MOONS_AUTOMATIC_FRACTURE:
            title = gettext("Automatic Fracture")
            description = gettext(
                "The moondrill fitted to %(structure_name)s at %(moon)s"
                " in %(solar_system)s has automatically been fired "
                "and the moon products are ready to be harvested.\n"
            ) % {
                "structure_name": "**%s**" % structure_name,
                "moon": moon.name_localized,
                "solar_system": solar_system_link,
            }
            color = self.EMBED_COLOR_SUCCESS

        elif self.notification_type == NTYPE_MOONS_EXTRACTION_CANCELED:
            if parsed_text["cancelledBy"]:
                cancelled_by, _ = EveEntity.objects.get_or_create_esi(
                    parsed_text["cancelledBy"]
                )
            else:
                cancelled_by = gettext("(unknown)")
            title = gettext("Extraction cancelled")
            description = gettext(
                "An ongoing extraction for %(structure_name)s at %(moon)s "
                "in %(solar_system)s has been cancelled by %(character)s."
            ) % {
                "structure_name": "**%s**" % structure_name,
                "moon": moon.name_localized,
                "solar_system": solar_system_link,
                "character": cancelled_by,
            }

            color = self.EMBED_COLOR_WARNING

        elif self.notification_type == NTYPE_MOONS_LASER_FIRED:
            fired_by, _ = EveEntity.objects.get_or_create_esi(parsed_text["firedBy"])
            title = gettext("Moondrill fired")
            description = gettext(
                "The moondrill fitted to %(structure_name)s at %(moon)s "
                "in %(solar_system)s has been fired by %(character)s "
                "and the moon products are ready to be harvested."
            ) % {
                "structure_name": "**%s**" % structure_name,
                "moon": moon.name_localized,
                "solar_system": solar_system_link,
                "character": fired_by,
            }
            color = self.EMBED_COLOR_SUCCESS

        else:
            raise NotImplementedError()

        structure_type, _ = EveType.objects.get_or_create_esi(
            parsed_text["structureTypeID"]
        )
        thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())
        return title, description, color, thumbnail

    def _gen_embed_pocos(self, parsed_text: dict) -> tuple:
        planet, _ = EvePlanet.objects.get_or_create_esi(parsed_text["planetID"])
        structure_type, _ = EveType.objects.get_or_create_esi(EveType.EVE_TYPE_ID_POCO)
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text["solarSystemID"]
        )
        solar_system_link = self._gen_solar_system_text(solar_system)
        aggressor_link = self._get_aggressor_link(parsed_text)

        if self.notification_type == NTYPE_ORBITAL_ATTACKED:
            title = gettext("Orbital under attack")
            description = gettext(
                "The %(structure_type)s at %(planet)s in %(solar_system)s "
                "is under attack by %(aggressor)s."
            ) % {
                "structure_type": structure_type.name_localized,
                "planet": planet.name_localized,
                "solar_system": solar_system_link,
                "aggressor": aggressor_link,
            }
            color = self.EMBED_COLOR_WARNING

        elif self.notification_type == NTYPE_ORBITAL_REINFORCED:
            reinforce_exit_time = self._ldap_datetime_2_dt(
                parsed_text["reinforceExitTime"]
            )
            title = gettext("Orbital reinforced")
            description = gettext(
                "The %(structure_type)s at %(planet)s in %(solar_system)s "
                "has been reinforced by %(aggressor)s "
                "and will come out at: %(date)s."
            ) % {
                "structure_type": structure_type.name_localized,
                "planet": planet.name_localized,
                "solar_system": solar_system_link,
                "aggressor": aggressor_link,
                "date": reinforce_exit_time.strftime(DATETIME_FORMAT),
            }
            color = self.EMBED_COLOR_DANGER

        else:
            raise NotImplementedError()

        thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())
        return title, description, color, thumbnail

    def _gen_embed_poses(self, parsed_text: dict) -> tuple:
        eve_moon, _ = EveMoon.objects.get_or_create_esi(parsed_text["moonID"])
        structure_type, _ = EveType.objects.get_or_create_esi(parsed_text["typeID"])
        solar_system_link = self._gen_solar_system_text(eve_moon.eve_solar_system)
        qs_structures = Structure.objects.filter(eve_moon=eve_moon)
        if qs_structures.exists():
            structure_name = qs_structures.first().name
        else:
            structure_name = structure_type.name_localized

        if self.notification_type == NTYPE_TOWER_ALERT_MSG:
            aggressor_link = self._get_aggressor_link(parsed_text)
            damage_labels = [
                ("shield", gettext("shield")),
                ("armor", gettext("armor")),
                ("hull", gettext("hull")),
            ]
            damage_parts = list()
            for prop in damage_labels:
                prop_yaml = prop[0] + "Value"
                if prop_yaml in parsed_text:
                    damage_parts.append(
                        "{}: {:.0f}%".format(prop[1], parsed_text[prop_yaml] * 100)
                    )
            damage_text = " | ".join(damage_parts)
            title = gettext("Starbase under attack")
            description = gettext(
                "The starbase %(structure_name)s at %(moon)s "
                "in %(solar_system)s is under attack by %(aggressor)s.\n"
                "%(damage_text)s"
            ) % {
                "structure_name": "**%s**" % structure_name,
                "moon": eve_moon.name_localized,
                "solar_system": solar_system_link,
                "aggressor": aggressor_link,
                "damage_text": damage_text,
            }
            color = self.EMBED_COLOR_WARNING

        elif self.notification_type == NTYPE_TOWER_RESOURCE_ALERT_MSG:
            quantity = parsed_text["wants"][0]["quantity"]
            title = gettext("Starbase low on fuel")
            description = gettext(
                "The starbase %(structure_name)s at %(moon)s "
                "in %(solar_system)s is low on fuel. "
                "It has %(quantity)d fuel blocks left."
            ) % {
                "structure_name": "**%s**" % structure_name,
                "moon": eve_moon.name_localized,
                "solar_system": solar_system_link,
                "quantity": quantity,
            }
            color = self.EMBED_COLOR_WARNING

        else:
            raise NotImplementedError()

        thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())
        return title, description, color, thumbnail

    def _gen_embed_sov(self, parsed_text: dict) -> tuple:
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text["solarSystemID"]
        )
        solar_system_link = self._gen_solar_system_text(solar_system)

        if "structureTypeID" in parsed_text:
            structure_type_id = parsed_text["structureTypeID"]
        elif "campaignEventType" in parsed_text:
            structure_type_id = self._get_type_id_from_event_type(
                parsed_text["campaignEventType"]
            )
        else:
            structure_type_id = EveType.EVE_TYPE_ID_TCU

        structure_type, _ = EveType.objects.get_or_create_esi(structure_type_id)
        structure_type_name = structure_type.name_localized
        sov_owner_link = self._gen_alliance_link(
            self.owner.corporation.alliance.alliance_name
        )
        if self.notification_type == NTYPE_SOV_ENTOSIS_CAPTURE_STARTED:
            title = gettext(
                "%(structure_type)s in %(solar_system)s is being captured"
            ) % {
                "structure_type": "**%s**" % structure_type_name,
                "solar_system": solar_system.name_localized,
            }
            description = gettext(
                "A capsuleer has started to influence the %(type)s "
                "in %(solar_system)s belonging to %(owner)s "
                "with an Entosis Link."
            ) % {
                "type": structure_type_name,
                "solar_system": solar_system_link,
                "owner": sov_owner_link,
            }
            color = self.EMBED_COLOR_WARNING

        elif self.notification_type == NTYPE_SOV_COMMAND_NODE_EVENT_STARTED:
            title = gettext(
                "Command nodes for %(structure_type)s in %(solar_system)s "
                "have begun to decloak"
            ) % {
                "structure_type": "**%s**" % structure_type_name,
                "solar_system": solar_system.name_localized,
            }
            description = gettext(
                "Command nodes for %(structure_type)s in %(solar_system)s "
                "can now be found throughout "
                "the %(constellation)s constellation"
            ) % {
                "structure_type": "**%s**" % structure_type_name,
                "solar_system": solar_system_link,
                "constellation": solar_system.eve_constellation.name_localized,
            }
            color = self.EMBED_COLOR_WARNING

        elif self.notification_type == NTYPE_SOV_ALL_CLAIM_ACQUIRED_MSG:
            alliance, _ = EveEntity.objects.get_or_create_esi(parsed_text["allianceID"])
            corporation, _ = EveEntity.objects.get_or_create_esi(parsed_text["corpID"])
            title = (
                gettext("DED Sovereignty claim acknowledgment: %s")
                % solar_system.name_localized
            )

            description = gettext(
                "DED now officially acknowledges that your "
                "member corporation %(corporation)s has claimed "
                "sovereignty on behalf of %(alliance)s in %(solar_system)s."
            ) % {
                "corporation": self._gen_corporation_link(corporation.name),
                "alliance": self._gen_alliance_link(alliance.name),
                "solar_system": solar_system_link,
            }
            color = self.EMBED_COLOR_SUCCESS

        elif self.notification_type == NTYPE_SOV_STRUCTURE_REINFORCED:
            timer_starts = self._ldap_datetime_2_dt(parsed_text["decloakTime"])
            title = gettext(
                "%(structure_type)s in %(solar_system)s " "has entered reinforced mode"
            ) % {
                "structure_type": "**%s**" % structure_type_name,
                "solar_system": solar_system.name_localized,
            }
            description = gettext(
                "The %(structure_type)s in %(solar_system)s belonging "
                "to %(owner)s has been reinforced by "
                "hostile forces and command nodes "
                "will begin decloaking at %(date)s"
            ) % {
                "structure_type": "**%s**" % structure_type_name,
                "solar_system": solar_system_link,
                "owner": sov_owner_link,
                "date": timer_starts.strftime(DATETIME_FORMAT),
            }
            color = self.EMBED_COLOR_DANGER

        elif self.notification_type == NTYPE_SOV_STRUCTURE_DESTROYED:
            title = gettext(
                "%(structure_type)s in %(solar_system)s has been destroyed"
            ) % {
                "structure_type": "**%s**" % structure_type_name,
                "solar_system": solar_system.name_localized,
            }
            description = gettext(
                "The command nodes for %(structure_type)s "
                "in %(solar_system)s belonging to %(owner)s have been "
                "destroyed by hostile forces."
            ) % {
                "structure_type": "**%s**" % structure_type_name,
                "solar_system": solar_system_link,
                "owner": sov_owner_link,
            }
            color = self.EMBED_COLOR_DANGER

        else:
            raise NotImplementedError()

        thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())
        return title, description, color, thumbnail

    @classmethod
    def _gen_solar_system_text(cls, solar_system: EveSolarSystem) -> str:
        text = "[{}]({}) ({})".format(
            solar_system.name_localized,
            dotlan.solar_system_url(solar_system.name),
            solar_system.eve_constellation.eve_region.name_localized,
        )
        return text

    @classmethod
    def _gen_alliance_link(cls, alliance_name):
        return "[{}]({})".format(alliance_name, dotlan.alliance_url(alliance_name))

    @classmethod
    def _gen_corporation_link(cls, corporation_name):
        return "[{}]({})".format(
            corporation_name, dotlan.corporation_url(corporation_name)
        )

    @classmethod
    def _get_attacker_link(cls, parsed_text):
        """returns the attacker link from a parsed_text
        For Upwell structures only
        """
        if "allianceName" in parsed_text:
            name = cls._gen_alliance_link(parsed_text["allianceName"])
        elif "corpName" in parsed_text:
            name = cls._gen_corporation_link(parsed_text["corpName"])
        else:
            name = "(unknown)"

        return name

    @classmethod
    def _get_aggressor_link(cls, parsed_text: dict) -> str:
        """returns the aggressor link from a parsed_text
        for POS and POCOs only
        """
        if "aggressorAllianceID" in parsed_text:
            key = "aggressorAllianceID"
        elif "aggressorCorpID" in parsed_text:
            key = "aggressorCorpID"
        elif "aggressorID" in parsed_text:
            key = "aggressorID"
        else:
            return "(Unknown aggressor)"

        entity, _ = EveEntity.objects.get_or_create_esi(parsed_text[key])
        return "[{}]({})".format(entity.name, entity.profile_url())

    @classmethod
    def _get_type_id_from_event_type(cls, event_type: int) -> int:
        if event_type in cls.MAP_CAMPAIGN_EVENT_2_TYPE_ID:
            return cls.MAP_CAMPAIGN_EVENT_2_TYPE_ID[event_type]
        else:
            return None

    def _execute_webhook(self, hook, content, embed, add_prefix) -> bool:
        """executes webhook for sending the message, will retry on errors
        
        Sets this notification as "sent" if successful
        
        returns True/False on success
        """
        success = False
        max_retries = STRUCTURES_NOTIFICATION_MAX_RETRIES
        for retry_count in range(max_retries + 1):
            if retry_count > 0:
                logger.warn(
                    add_prefix("Retry {} / {}".format(retry_count, max_retries))
                )
            try:
                res = hook.execute(
                    content=content, embeds=[embed], wait_for_response=True
                )
                if res.status_ok:
                    self.is_sent = True
                    self.save()
                    success = True
                    break

                elif res.status_code == self.HTTP_CODE_TOO_MANY_REQUESTS:
                    if "retry_after" in res.content:
                        retry_after = res.content["retry_after"] / 1000
                    else:
                        retry_after = STRUCTURES_NOTIFICATION_WAIT_SEC
                    logger.warn(
                        add_prefix(
                            "rate limited - will retry after %d secs" % retry_after
                        )
                    )
                    sleep(retry_after)

                else:
                    logger.warn(add_prefix("Failed to send message"))
                    break

            except Exception as ex:
                logger.warn(
                    add_prefix("Unexpected issue when trying to send message: %s" % ex)
                )
                if settings.DEBUG:
                    raise ex
                else:
                    break

        return success

    def process_for_timerboard(self, token: Token = None) -> bool:
        """add/removes a timer related to this notification for some types
        returns True when a timer was processed, else False
        """
        timer_created = False
        if (
            has_auth_timers or has_structure_timers
        ) and self.notification_type in _NTYPE_RELEVANT_FOR_TIMERBOARD:
            parsed_text = self.get_parsed_text()
            try:
                with translation.override(STRUCTURES_DEFAULT_LANGUAGE):
                    if self.notification_type in [
                        NTYPE_STRUCTURE_LOST_ARMOR,
                        NTYPE_STRUCTURE_LOST_SHIELD,
                    ]:
                        timer_created = self._gen_timer_structure_reinforcement(
                            parsed_text, token
                        )
                    elif self.notification_type == NTYPE_STRUCTURE_ANCHORING:
                        timer_created = self._gen_timer_structure_anchoring(parsed_text)
                    elif self.notification_type == NTYPE_SOV_STRUCTURE_REINFORCED:
                        timer_created = self._gen_timer_sov_reinforcements(parsed_text)
                    elif self.notification_type == NTYPE_ORBITAL_REINFORCED:
                        timer_created = self._gen_timer_orbital_reinforcements(
                            parsed_text
                        )
                    elif self.notification_type in [
                        NTYPE_MOONS_EXTRACTION_STARTED,
                        NTYPE_MOONS_EXTRACTION_CANCELED,
                    ]:
                        if not STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED:
                            timer_created = None
                        else:
                            timer_created = self._gen_timer_moon_extraction(parsed_text)
                    else:
                        raise NotImplementedError()

                if timer_created:
                    logger.info(
                        "{}: added timer_created related notification".format(
                            self.notification_id
                        )
                    )

                self.is_timer_added = timer_created
                self.save()

            except Exception as ex:
                logger.exception(
                    "{}: Failed to add timer from notification: {}".format(
                        self.notification_id, ex
                    )
                )
                if settings.DEBUG:
                    raise ex

        return timer_created

    def _gen_timer_structure_reinforcement(
        self, parsed_text: str, token: Token
    ) -> bool:
        """generate timer for structure reinforcements"""
        structure_obj, _ = Structure.objects.get_or_create_esi(
            parsed_text["structureID"], token
        )
        eve_time = self.timestamp + self._ldap_timedelta_2_timedelta(
            parsed_text["timeLeft"]
        )
        timer_added = False
        if has_auth_timers:
            details_map = {
                NTYPE_STRUCTURE_LOST_SHIELD: gettext("Armor timer"),
                NTYPE_STRUCTURE_LOST_ARMOR: gettext("Final timer"),
            }
            AuthTimer.objects.create(
                details=details_map.get(self.notification_type, ""),
                system=structure_obj.eve_solar_system.name,
                planet_moon="",
                structure=structure_obj.eve_type.name,
                objective="Friendly",
                eve_time=eve_time,
                eve_corp=self.owner.corporation,
                corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
            )
            timer_added = True

        if has_structure_timers:
            timer_map = {
                NTYPE_STRUCTURE_LOST_SHIELD: Timer.TYPE_ARMOR,
                NTYPE_STRUCTURE_LOST_ARMOR: Timer.TYPE_HULL,
            }
            eve_solar_system, _ = EveSolarSystem2.objects.get_or_create_esi(
                id=structure_obj.eve_solar_system_id
            )
            structure_type, _ = EveType2.objects.get_or_create_esi(
                id=structure_obj.eve_type_id
            )
            visibility = (
                Timer.VISIBILITY_CORPORATION
                if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
                else Timer.VISIBILITY_UNRESTRICTED
            )
            Timer.objects.create(
                eve_solar_system=eve_solar_system,
                structure_type=structure_type,
                timer_type=timer_map.get(self.notification_type),
                objective=Timer.OBJECTIVE_FRIENDLY,
                date=eve_time,
                eve_corporation=self.owner.corporation,
                eve_alliance=self.owner.corporation.alliance,
                visibility=visibility,
                structure_name=structure_obj.name,
                owner_name=self.owner.corporation.corporation_name,
                details_notes=(
                    "Automatically created from structure notification for "
                    f"{self.owner.corporation}"
                ),
            )
            timer_added = True

        return timer_added

    def _gen_timer_structure_anchoring(self, parsed_text: str) -> bool:
        """generate timer for structure anchoring"""
        structure_type, _ = EveType.objects.get_or_create_esi(
            parsed_text["structureTypeID"]
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text["solarsystemID"]
        )
        timer_added = False
        if not solar_system.is_null_sec:
            eve_time = self.timestamp + timedelta(hours=24)
            if has_auth_timers:
                AuthTimer.objects.create(
                    details=gettext("Anchor timer"),
                    system=solar_system.name,
                    planet_moon="",
                    structure=structure_type.name,
                    objective="Friendly",
                    eve_time=eve_time,
                    eve_corp=self.owner.corporation,
                    corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
                )
                timer_added = True

            if has_structure_timers:
                eve_solar_system, _ = EveSolarSystem2.objects.get_or_create_esi(
                    id=parsed_text["solarsystemID"]
                )
                structure_type, _ = EveType2.objects.get_or_create_esi(
                    id=parsed_text["structureTypeID"]
                )
                visibility = (
                    Timer.VISIBILITY_CORPORATION
                    if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
                    else Timer.VISIBILITY_UNRESTRICTED
                )
                Timer.objects.create(
                    eve_solar_system=eve_solar_system,
                    structure_type=structure_type,
                    timer_type=Timer.TYPE_ANCHORING,
                    objective=Timer.OBJECTIVE_FRIENDLY,
                    date=eve_time,
                    eve_corporation=self.owner.corporation,
                    eve_alliance=self.owner.corporation.alliance,
                    visibility=visibility,
                    owner_name=self.owner.corporation.corporation_name,
                    details_notes=(
                        "Automatically created from structure notification for "
                        f"{self.owner.corporation}"
                    ),
                )
                timer_added = True

        return timer_added

    def _gen_timer_sov_reinforcements(self, parsed_text: str) -> bool:
        """generate timer for sov reinforcements"""
        if not self.owner.is_alliance_main:
            return False

        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text["solarSystemID"]
        )
        event_type = parsed_text["campaignEventType"]
        if event_type in self.MAP_CAMPAIGN_EVENT_2_TYPE_ID:
            structure_type_name = self.MAP_TYPE_ID_2_TIMER_STRUCTURE_NAME[
                self._get_type_id_from_event_type(parsed_text["campaignEventType"])
            ]
        else:
            structure_type_name = "Other"

        eve_time = self._ldap_datetime_2_dt(parsed_text["decloakTime"])
        timer_added = False
        if has_auth_timers:
            AuthTimer.objects.create(
                details=gettext("Sov timer"),
                system=solar_system.name,
                planet_moon="",
                structure=structure_type_name,
                objective="Friendly",
                eve_time=eve_time,
                eve_corp=self.owner.corporation,
                corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
            )
            timer_added = True

        if has_structure_timers:
            eve_solar_system, _ = EveSolarSystem2.objects.get_or_create_esi(
                id=parsed_text["solarSystemID"]
            )
            structure_type, _ = EveType2.objects.get_or_create_esi(
                id=self._get_type_id_from_event_type(parsed_text["campaignEventType"])
            )
            visibility = (
                Timer.VISIBILITY_CORPORATION
                if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
                else Timer.VISIBILITY_UNRESTRICTED
            )
            Timer.objects.create(
                eve_solar_system=eve_solar_system,
                structure_type=structure_type,
                timer_type=Timer.TYPE_FINAL,
                objective=Timer.OBJECTIVE_FRIENDLY,
                date=eve_time,
                eve_corporation=self.owner.corporation,
                eve_alliance=self.owner.corporation.alliance,
                visibility=visibility,
                owner_name=self.owner.corporation.corporation_name,
                details_notes=(
                    "Automatically created from structure notification for "
                    f"{self.owner.corporation}"
                ),
            )
            timer_added = True

        return timer_added

    def _gen_timer_orbital_reinforcements(self, parsed_text: str) -> bool:
        """generate timer for orbital reinforcements"""
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text["solarSystemID"]
        )
        planet, _ = EvePlanet.objects.get_or_create_esi(parsed_text["planetID"])
        eve_time = self._ldap_datetime_2_dt(parsed_text["reinforceExitTime"])
        timer_added = False
        if has_auth_timers:
            AuthTimer.objects.create(
                details=gettext("Final timer"),
                system=solar_system.name,
                planet_moon=planet.name,
                structure="POCO",
                objective="Friendly",
                eve_time=eve_time,
                eve_corp=self.owner.corporation,
                corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
            )
            timer_added = True

        if has_structure_timers:
            eve_solar_system, _ = EveSolarSystem2.objects.get_or_create_esi(
                id=parsed_text["solarSystemID"]
            )
            structure_type, _ = EveType2.objects.get_or_create_esi(
                id=EveType.EVE_TYPE_ID_POCO
            )
            visibility = (
                Timer.VISIBILITY_CORPORATION
                if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
                else Timer.VISIBILITY_UNRESTRICTED
            )
            Timer.objects.create(
                eve_solar_system=eve_solar_system,
                structure_type=structure_type,
                timer_type=Timer.TYPE_FINAL,
                objective=Timer.OBJECTIVE_FRIENDLY,
                date=eve_time,
                location_details=planet.name,
                eve_corporation=self.owner.corporation,
                eve_alliance=self.owner.corporation.alliance,
                visibility=visibility,
                structure_name="Customs Office",
                owner_name=self.owner.corporation.corporation_name,
                details_notes=(
                    "Automatically created from structure notification for "
                    f"{self.owner.corporation}"
                ),
            )
            timer_added = True

        return timer_added

    def _gen_timer_moon_extraction(self, parsed_text: str) -> bool:
        """generate timer for moon mining extractions"""
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text["solarSystemID"]
        )
        moon, _ = EveMoon.objects.get_or_create_esi(parsed_text["moonID"])
        if "readyTime" in parsed_text:
            eve_time = self._ldap_datetime_2_dt(parsed_text["readyTime"])
        else:
            eve_time = None
        details = gettext("Extraction ready")
        system = solar_system.name
        planet_moon = moon.name
        structure_type_name = "Moon Mining Cycle"
        objective = "Friendly"
        timer_added = False

        if has_structure_timers:
            eve_solar_system, _ = EveSolarSystem2.objects.get_or_create_esi(
                id=parsed_text["solarSystemID"]
            )
            structure_type, _ = EveType2.objects.get_or_create_esi(
                id=parsed_text["structureTypeID"]
            )
            visibility = (
                Timer.VISIBILITY_CORPORATION
                if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
                else Timer.VISIBILITY_UNRESTRICTED
            )
        else:
            eve_solar_system = None
            structure_type = None
            visibility = None

        if self.notification_type == NTYPE_MOONS_EXTRACTION_STARTED:
            if has_auth_timers:
                AuthTimer.objects.create(
                    details=details,
                    system=system,
                    planet_moon=planet_moon,
                    structure=structure_type_name,
                    objective=objective,
                    eve_time=eve_time,
                    eve_corp=self.owner.corporation,
                    corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
                )
                timer_added = True

            if has_structure_timers:
                eve_solar_system, _ = EveSolarSystem2.objects.get_or_create_esi(
                    id=parsed_text["solarSystemID"]
                )
                structure_type, _ = EveType2.objects.get_or_create_esi(
                    id=parsed_text["structureTypeID"]
                )
                visibility = (
                    Timer.VISIBILITY_CORPORATION
                    if STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
                    else Timer.VISIBILITY_UNRESTRICTED
                )
                Timer.objects.create(
                    eve_solar_system=eve_solar_system,
                    structure_type=structure_type,
                    timer_type=Timer.TYPE_MOONMINING,
                    objective=Timer.OBJECTIVE_FRIENDLY,
                    date=eve_time,
                    location_details=moon.name,
                    eve_corporation=self.owner.corporation,
                    eve_alliance=self.owner.corporation.alliance,
                    visibility=visibility,
                    structure_name=parsed_text["structureName"],
                    owner_name=self.owner.corporation.corporation_name,
                    details_notes=(
                        "Automatically created from structure notification for "
                        f"{self.owner.corporation}"
                    ),
                )
                timer_added = True

        elif self.notification_type == NTYPE_MOONS_EXTRACTION_CANCELED:
            notifications_qs = Notification.objects.filter(
                notification_type=NTYPE_MOONS_EXTRACTION_STARTED,
                owner=self.owner,
                is_timer_added=True,
                timestamp__lte=self.timestamp,
            ).order_by("-timestamp")

            for notification in notifications_qs:
                parsed_text_2 = notification.get_parsed_text()
                my_structure_type_id = parsed_text_2["structureTypeID"]
                if my_structure_type_id == parsed_text["structureTypeID"]:
                    eve_time = self._ldap_datetime_2_dt(parsed_text_2["readyTime"])
                    if has_auth_timers:
                        timer_query = AuthTimer.objects.filter(
                            system=system,
                            planet_moon=planet_moon,
                            structure=structure_type_name,
                            objective=objective,
                            eve_time=eve_time,
                        )
                        deleted_count, _ = timer_query.delete()
                        logger.info(
                            f"{self.notification_id}: removed {deleted_count} "
                            "obsolete Auth timers related to notification"
                        )

                    if has_structure_timers:
                        timer_query = Timer.objects.filter(
                            eve_solar_system=eve_solar_system,
                            structure_type=structure_type,
                            timer_type=Timer.TYPE_MOONMINING,
                            location_details=moon.name,
                            date=eve_time,
                            objective=Timer.OBJECTIVE_FRIENDLY,
                            eve_corporation=self.owner.corporation,
                            eve_alliance=self.owner.corporation.alliance,
                            visibility=visibility,
                            structure_name=parsed_text["structureName"],
                            owner_name=self.owner.corporation.corporation_name,
                        )
                        deleted_count, _ = timer_query.delete()
                        logger.info(
                            f"{self.notification_id}: removed {deleted_count} "
                            "obsolete structure timers related to notification"
                        )

        return timer_added
