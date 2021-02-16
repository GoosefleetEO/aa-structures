"""Notification related models"""

from datetime import timedelta
from enum import Enum
import logging
import yaml
from typing import List, Tuple

import dhooks_lite

from requests.exceptions import HTTPError

from django.db import models
from django.contrib.auth.models import Group
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext_lazy as _, gettext

from app_utils.django import app_labels
from app_utils.datetime import (
    DATETIME_FORMAT,
    ldap_time_2_datetime,
    ldap_timedelta_2_timedelta,
)
from app_utils.logging import LoggerAddTag
from app_utils.urls import static_file_absolute_url
from esi.models import Token
from multiselectfield import MultiSelectField

from allianceauth.eveonline.evelinks import dotlan, eveimageserver

from .eveuniverse import EveType, EveSolarSystem, EveMoon, EvePlanet

from .. import __title__
from ..app_settings import (
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED,
    STRUCTURES_NOTIFICATION_SET_AVATAR,
    STRUCTURES_REPORT_NPC_ATTACKS,
    STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
)
from ..managers import EveEntityManager
from .structures import Structure
from ..webhooks.models import WebhookBase


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


class NotificationGroup(models.IntegerChoices):
    """Definition of all supported notification groups"""

    CORPORATION_MEMBER = 10
    MOON_MINING = 20
    UPWELL_STRUCTURE = 30
    CUSTOMS_OFFICE = 40
    STARBASE = 50
    SOVEREIGNTY = 60
    WAR = 70


class NotificationType(Enum):
    """Definition of all supported notification types

    Each member is a tuple of id, group
    """

    # character
    CHAR_APP_ACCEPT_MSG = "CharAppAcceptMsg", NotificationGroup.CORPORATION_MEMBER
    CHAR_LEFT_CORP_MSG = "CharLeftCorpMsg", NotificationGroup.CORPORATION_MEMBER

    # moon mining
    MOONS_AUTOMATIC_FRACTURE = (
        "MoonminingAutomaticFracture",
        NotificationGroup.MOON_MINING,
    )
    MOONS_EXTRACTION_CANCELED = (
        "MoonminingExtractionCancelled",
        NotificationGroup.MOON_MINING,
    )
    MOONS_EXTRACTION_FINISHED = (
        "MoonminingExtractionFinished",
        NotificationGroup.MOON_MINING,
    )
    MOONS_EXTRACTION_STARTED = (
        "MoonminingExtractionStarted",
        NotificationGroup.MOON_MINING,
    )
    MOONS_LASER_FIRED = "MoonminingLaserFired", NotificationGroup.MOON_MINING

    # upwell structures
    STRUCTURE_ANCHORING = "StructureAnchoring", NotificationGroup.UPWELL_STRUCTURE
    STRUCTURE_DESTROYED = "StructureDestroyed", NotificationGroup.UPWELL_STRUCTURE
    STRUCTURE_FUEL_ALERT = "StructureFuelAlert", NotificationGroup.UPWELL_STRUCTURE
    STRUCTURE_LOST_ARMOR = "StructureLostArmor", NotificationGroup.UPWELL_STRUCTURE
    STRUCTURE_LOST_SHIELD = "StructureLostShields", NotificationGroup.UPWELL_STRUCTURE
    STRUCTURE_ONLINE = "StructureOnline", NotificationGroup.UPWELL_STRUCTURE
    STRUCTURE_SERVICES_OFFLINE = (
        "StructureServicesOffline",
        NotificationGroup.UPWELL_STRUCTURE,
    )
    STRUCTURE_UNANCHORING = "StructureUnanchoring", NotificationGroup.UPWELL_STRUCTURE
    STRUCTURE_UNDER_ATTACK = "StructureUnderAttack", NotificationGroup.UPWELL_STRUCTURE
    STRUCTURE_WENT_HIGH_POWER = (
        "StructureWentHighPower",
        NotificationGroup.UPWELL_STRUCTURE,
    )
    STRUCTURE_WENT_LOW_POWER = (
        "StructureWentLowPower",
        NotificationGroup.UPWELL_STRUCTURE,
    )

    # STRUCTURE_REINFORCE_CHANGED = "StructureReinforceChange",NotificationGroup.UPWELL_STRUCTURE
    OWNERSHIP_TRANSFERRED = "OwnershipTransferred", NotificationGroup.UPWELL_STRUCTURE

    # customs offices
    ORBITAL_ATTACKED = "OrbitalAttacked", NotificationGroup.CUSTOMS_OFFICE
    ORBITAL_REINFORCED = "OrbitalReinforced", NotificationGroup.CUSTOMS_OFFICE

    # starbases
    TOWER_ALERT_MSG = "TowerAlertMsg", NotificationGroup.STARBASE
    TOWER_RESOURCE_ALERT_MSG = "TowerResourceAlertMsg", NotificationGroup.STARBASE

    # sov
    SOV_ENTOSIS_CAPTURE_STARTED = "EntosisCaptureStarted", NotificationGroup.SOVEREIGNTY
    SOV_COMMAND_NODE_EVENT_STARTED = (
        "SovCommandNodeEventStarted",
        NotificationGroup.SOVEREIGNTY,
    )
    SOV_ALL_CLAIM_ACQUIRED_MSG = "SovAllClaimAquiredMsg", NotificationGroup.SOVEREIGNTY
    SOV_STRUCTURE_REINFORCED = "SovStructureReinforced", NotificationGroup.SOVEREIGNTY
    SOV_STRUCTURE_DESTROYED = "SovStructureDestroyed", NotificationGroup.SOVEREIGNTY

    # wars
    WAR_ALLY_JOINED_WAR_AGGRESSOR_MSG = (
        "AllyJoinedWarAggressorMsg",
        NotificationGroup.WAR,
    )
    WAR_CORP_WAR_SURRENDER_MSG = "CorpWarSurrenderMsg", NotificationGroup.WAR
    WAR_WAR_ADOPTED = "WarAdopted", NotificationGroup.WAR
    WAR_WAR_DECLARED = "WarDeclared", NotificationGroup.WAR
    WAR_WAR_INHERITED = "WarInherited", NotificationGroup.WAR
    WAR_WAR_RETRACTED_BY_CONCORD = "WarRetractedByConcord", NotificationGroup.WAR

    def __init__(self, id, group) -> None:
        self.id = id
        self.group = group

    def __eq__(self, o: object) -> bool:
        """Compare with id instead of tuple"""
        return self.id == o

    @classmethod
    def ids(cls) -> list:
        return [x.id for x in cls]

    @classmethod
    def ids_for_group(cls, group) -> list:
        return [x.id for x in cls if int(x.group) == int(group)]

    @classmethod
    def relevant_for_timerboard(cls) -> list:
        return [
            cls.STRUCTURE_LOST_SHIELD.id,
            cls.STRUCTURE_LOST_ARMOR.id,
            cls.STRUCTURE_ANCHORING.id,
            cls.ORBITAL_REINFORCED.id,
            cls.MOONS_EXTRACTION_STARTED.id,
            cls.MOONS_EXTRACTION_CANCELED.id,
            cls.SOV_STRUCTURE_REINFORCED.id,
        ]

    @classmethod
    def relevant_for_alliance_level(cls) -> list:
        return [
            cls.SOV_ENTOSIS_CAPTURE_STARTED.id,
            cls.SOV_COMMAND_NODE_EVENT_STARTED.id,
            cls.SOV_ALL_CLAIM_ACQUIRED_MSG.id,
            cls.SOV_STRUCTURE_REINFORCED.id,
            cls.SOV_STRUCTURE_DESTROYED.id,
            cls.WAR_ALLY_JOINED_WAR_AGGRESSOR_MSG.id,
            cls.WAR_CORP_WAR_SURRENDER_MSG.id,
            cls.WAR_WAR_DECLARED.id,
            cls.WAR_WAR_RETRACTED_BY_CONCORD.id,
            cls.WAR_WAR_ADOPTED.id,
            cls.WAR_WAR_INHERITED.id,
        ]


def get_default_notification_types():
    """DEPRECATED: generates a set of all existing notification types as default"""
    return tuple(sorted([str(x[0]) for x in NotificationType.ids]))


class Webhook(WebhookBase):
    """A destination for forwarding notification alerts"""

    notification_groups = MultiSelectField(
        choices=NotificationGroup.choices,
        default="",
        help_text=("only notifications from selected groups are sent to this webhook"),
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
    is_default = models.BooleanField(
        default=False,
        help_text=(
            "whether owners have this webhook automatically pre-set when created"
        ),
    )
    has_default_pings_enabled = models.BooleanField(
        default=True,
        help_text=(
            "to enable or disable pinging of notifications for this webhook "
            "e.g. with @everyone and @here"
        ),
    )
    ping_groups = models.ManyToManyField(
        Group,
        default=None,
        blank=True,
        help_text="Groups to be pinged for each notification - ",
    )

    @property
    def notification_types(self) -> list:
        result = list()
        for group in self.notification_groups:
            result += NotificationType.ids_for_group(group)
        return result


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

    def __str__(self) -> str:
        return str(self.name)

    def __repr__(self) -> str:
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

    def icon_url(self, size: int = 32) -> str:
        if self.category == self.CATEGORY_ALLIANCE:
            return eveimageserver.alliance_logo_url(self.id, size)
        elif (
            self.category == self.CATEGORY_CORPORATION
            or self.category == self.CATEGORY_FACTION
        ):
            return eveimageserver.corporation_logo_url(self.id, size)
        elif self.category == self.CATEGORY_CHARACTER:
            return eveimageserver.character_portrait_url(self.id, size)
        else:
            raise NotImplementedError()

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

    HTTP_CODE_TOO_MANY_REQUESTS = 429

    # event type structure map
    MAP_CAMPAIGN_EVENT_2_TYPE_ID = {
        1: EveType.EVE_TYPE_ID_TCU,
        2: EveType.EVE_TYPE_ID_IHUB,
    }
    MAP_TYPE_ID_2_TIMER_STRUCTURE_NAME = {2233: "POCO", 32226: "TCU", 32458: "I-HUB"}

    notification_id = models.PositiveBigIntegerField(verbose_name="id")
    owner = models.ForeignKey(
        "Owner",
        on_delete=models.CASCADE,
        help_text="Corporation that received this notification",
    )
    sender = models.ForeignKey(EveEntity, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    notif_type = models.CharField(
        max_length=100,
        default="",
        db_index=True,
        verbose_name="type",
        help_text="type of this notification as reported by ESI",
    )
    text = models.TextField(
        null=True, default=None, blank=True, help_text="Notification details in YAML"
    )
    is_read = models.BooleanField(
        null=True,
        default=None,
        help_text="True when this notification has read in the eve client",
    )
    is_sent = models.BooleanField(
        default=False,
        help_text="True when this notification has been forwarded to Discord",
    )
    is_timer_added = models.BooleanField(
        null=True,
        default=None,
        help_text="True when a timer has been added for this notification",
    )
    last_updated = models.DateTimeField(
        help_text="Date when this notification has last been updated from ESI"
    )
    created = models.DateTimeField(
        null=True,
        default=None,
        help_text="Date when this notification was first received from ESI",
    )

    class Meta:
        unique_together = (("notification_id", "owner"),)

    def __str__(self) -> str:
        return str(self.notification_id)

    def __repr__(self) -> str:
        return "%s(notification_id=%d, owner='%s', notif_type='%s')" % (
            self.__class__.__name__,
            self.notification_id,
            self.owner,
            self.notif_type,
        )

    @property
    def is_alliance_level(self) -> bool:
        """whether this is an alliance level notification"""
        return self.notif_type in NotificationType.relevant_for_alliance_level()

    # @classmethod
    # def get_all_types(cls) -> Set[int]:
    #     """returns a set with all supported notification types"""
    #     return {x[0] for x in NotificationType.choices}

    @classmethod
    def get_types_for_timerboard(cls) -> List[int]:
        """returns set of types relevant for the timerboard"""
        return NotificationType.relevant_for_timerboard()

    @classmethod
    def get_matching_notification_type(cls, type_name: str) -> int:
        """returns matching notification type for given name or None"""
        match = None
        for x in NotificationType.choices:
            if type_name == x[1]:
                match = x
                break

        return match[0] if match else None

    def get_parsed_text(self) -> dict:
        """returns the notifications's text as dict"""
        return yaml.safe_load(self.text)

    def is_npc_attacking(self) -> bool:
        """whether this notification is about a NPC attacking"""
        result = False
        if self.notif_type in [
            NotificationType.ORBITAL_ATTACKED,
            NotificationType.STRUCTURE_UNDER_ATTACK,
        ]:
            parsed_text = self.get_parsed_text()
            corporation_id = None
            if self.notif_type == NotificationType.STRUCTURE_UNDER_ATTACK:
                if (
                    "corpLinkData" in parsed_text
                    and len(parsed_text["corpLinkData"]) >= 3
                ):
                    corporation_id = int(parsed_text["corpLinkData"][2])

            if self.notif_type == NotificationType.ORBITAL_ATTACKED:
                if "aggressorCorpID" in parsed_text:
                    corporation_id = int(parsed_text["aggressorCorpID"])

            if 1000000 <= corporation_id <= 2000000:
                result = True

        return result

    def filter_for_npc_attacks(self) -> bool:
        """true when notification to be filtered out due to npc attacks"""
        return not STRUCTURES_REPORT_NPC_ATTACKS and self.is_npc_attacking()

    def filter_for_alliance_level(self) -> bool:
        """true when notification to be filtered out due to alliance level"""
        return self.is_alliance_level and not self.owner.is_alliance_main

    def send_to_webhook(self, webhook: Webhook) -> bool:
        """sends this notification to the configured webhook
        returns True if successful, else False
        """
        logger.info("%s: Trying to sent to webhook: %s", self, webhook)
        success = False
        try:
            embed, ping_type = self._generate_embed(webhook.language_code)
        except Exception as ex:
            logger.warning("%s: Failed to generate embed: %s", self, ex, exc_info=True)
            return False

        if webhook.has_default_pings_enabled and self.owner.has_default_pings_enabled:
            if ping_type == Webhook.PingType.EVERYONE:
                content = "@everyone"
            elif ping_type == Webhook.PingType.HERE:
                content = "@here"
            else:
                content = ""
        else:
            content = ""

        if webhook.ping_groups.count() > 0 or self.owner.ping_groups.count() > 0:
            if "discord" in app_labels():
                DiscordUser = self._import_discord()

                groups = set(self.owner.ping_groups.all()) | set(
                    webhook.ping_groups.all()
                )
                for group in groups:
                    try:
                        role = DiscordUser.objects.group_to_role(group)
                    except HTTPError:
                        logger.warning("Failed to get Discord roles", exc_info=True)
                    else:
                        if role:
                            content += f" <@&{role['id']}>"

        username, avatar_url = self._gen_avatar()
        success = webhook.send_message(
            content=content,
            embeds=[embed],
            username=username,
            avatar_url=avatar_url,
        )
        if success:
            self.is_sent = True
            self.save()

        return success

    def _gen_avatar(self) -> Tuple[str, str]:
        if STRUCTURES_NOTIFICATION_SET_AVATAR:
            username = "Notifications"
            avatar_url = static_file_absolute_url("structures/structures_logo.png")
        else:
            username = None
            avatar_url = None

        return username, avatar_url

    @staticmethod
    def _import_discord() -> object:
        from allianceauth.services.modules.discord.models import DiscordUser

        return DiscordUser

    def _generate_embed(
        self, language_code: str
    ) -> Tuple[dhooks_lite.Embed, Webhook.PingType]:
        """generates a Discord embed for this notification"""
        from ..core.notification_embeds import NotificationBaseEmbed

        logger.info("Creating embed with language = %s" % language_code)
        with translation.override(language_code):
            notification_embed = NotificationBaseEmbed.create(self)
            return notification_embed.generate_embed(), notification_embed.ping_type

    @classmethod
    def type_id_from_event_type(cls, event_type: int) -> int:
        if event_type in cls.MAP_CAMPAIGN_EVENT_2_TYPE_ID:
            return cls.MAP_CAMPAIGN_EVENT_2_TYPE_ID[event_type]
        else:
            return None

    def process_for_timerboard(self, token: Token = None) -> bool:
        """add/removes a timer related to this notification for some types
        returns True when a timer was processed, else False
        """
        timer_created = False
        if (
            has_auth_timers or has_structure_timers
        ) and self.notif_type in NotificationType.relevant_for_timerboard():
            parsed_text = self.get_parsed_text()
            try:
                with translation.override(STRUCTURES_DEFAULT_LANGUAGE):
                    if self.notif_type in [
                        NotificationType.STRUCTURE_LOST_ARMOR.id,
                        NotificationType.STRUCTURE_LOST_SHIELD.id,
                    ]:
                        timer_created = self._gen_timer_structure_reinforcement(
                            parsed_text, token
                        )
                    elif self.notif_type == NotificationType.STRUCTURE_ANCHORING:
                        timer_created = self._gen_timer_structure_anchoring(parsed_text)
                    elif self.notif_type == NotificationType.SOV_STRUCTURE_REINFORCED:
                        timer_created = self._gen_timer_sov_reinforcements(parsed_text)
                    elif self.notif_type == NotificationType.ORBITAL_REINFORCED:
                        timer_created = self._gen_timer_orbital_reinforcements(
                            parsed_text
                        )
                    elif self.notif_type in [
                        NotificationType.MOONS_EXTRACTION_STARTED.id,
                        NotificationType.MOONS_EXTRACTION_CANCELED.id,
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
        eve_time = self.timestamp + ldap_timedelta_2_timedelta(parsed_text["timeLeft"])
        timer_added = False
        if has_auth_timers:
            details_map = {
                NotificationType.STRUCTURE_LOST_SHIELD.id: gettext("Armor timer"),
                NotificationType.STRUCTURE_LOST_ARMOR.id: gettext("Final timer"),
            }
            AuthTimer.objects.create(
                details=details_map.get(self.notif_type, ""),
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
                NotificationType.STRUCTURE_LOST_SHIELD.id: Timer.TYPE_ARMOR,
                NotificationType.STRUCTURE_LOST_ARMOR.id: Timer.TYPE_HULL,
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
                timer_type=timer_map.get(self.notif_type),
                objective=Timer.OBJECTIVE_FRIENDLY,
                date=eve_time,
                eve_corporation=self.owner.corporation,
                eve_alliance=self.owner.corporation.alliance,
                visibility=visibility,
                structure_name=structure_obj.name,
                owner_name=self.owner.corporation.corporation_name,
                details_notes=self._timer_details_notes(),
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
                    details_notes=self._timer_details_notes(),
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
                self.type_id_from_event_type(parsed_text["campaignEventType"])
            ]
        else:
            structure_type_name = "Other"

        eve_time = ldap_time_2_datetime(parsed_text["decloakTime"])
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
                id=self.type_id_from_event_type(parsed_text["campaignEventType"])
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
                owner_name=self.sender.name,
                details_notes=self._timer_details_notes(),
            )
            timer_added = True

        return timer_added

    def _gen_timer_orbital_reinforcements(self, parsed_text: str) -> bool:
        """generate timer for orbital reinforcements"""
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text["solarSystemID"]
        )
        planet, _ = EvePlanet.objects.get_or_create_esi(parsed_text["planetID"])
        eve_time = ldap_time_2_datetime(parsed_text["reinforceExitTime"])
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
                details_notes=self._timer_details_notes(),
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
            eve_time = ldap_time_2_datetime(parsed_text["readyTime"])
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

        if self.notif_type == NotificationType.MOONS_EXTRACTION_STARTED:
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
                    details_notes=self._timer_details_notes(),
                )
                timer_added = True

        elif self.notif_type == NotificationType.MOONS_EXTRACTION_CANCELED:
            notifications_qs = Notification.objects.filter(
                notif_type=NotificationType.MOONS_EXTRACTION_STARTED.id,
                owner=self.owner,
                is_timer_added=True,
                timestamp__lte=self.timestamp,
            ).order_by("-timestamp")

            for notification in notifications_qs:
                parsed_text_2 = notification.get_parsed_text()
                my_structure_type_id = parsed_text_2["structureTypeID"]
                if my_structure_type_id == parsed_text["structureTypeID"]:
                    eve_time = ldap_time_2_datetime(parsed_text_2["readyTime"])
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

    def _timer_details_notes(self) -> str:
        """returns generated details notes string for Timers"""
        return (
            "Automatically created from structure notification for "
            f"{self.owner.corporation} at {self.timestamp.strftime(DATETIME_FORMAT)}"
        )
