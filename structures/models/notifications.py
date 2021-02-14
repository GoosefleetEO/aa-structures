"""Notification related models"""

from datetime import timedelta
import logging
import yaml
from typing import List, Set, Tuple

import dhooks_lite

from requests.exceptions import HTTPError

from django.db import models
from django.contrib.auth.models import Group
from django.core.validators import MinValueValidator
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext_lazy as _, gettext

from allianceauth.eveonline.evelinks import dotlan, eveimageserver

from esi.models import Token
from multiselectfield import MultiSelectField

from .eveuniverse import EveType, EveSolarSystem, EveMoon, EvePlanet

from .. import __title__
from ..app_settings import (
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED,
    STRUCTURES_NOTIFICATION_SET_AVATAR,
    STRUCTURES_REPORT_NPC_ATTACKS,
    STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
)
from ..helpers.eveonline import ldap_datetime_2_dt, ldap_timedelta_2_timedelta
from ..helpers.urls import static_file_absolute_url
from ..managers import EveEntityManager
from .structures import Structure
from ..utils import (
    app_labels,
    LoggerAddTag,
    DATETIME_FORMAT,
    make_logger_prefix,
)
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


class NotificationType(models.IntegerChoices):
    """Definition of all supported notification types"""

    # character
    CHAR_APP_ACCEPT_MSG = 201, "CharAppAcceptMsg"
    CHAR_LEFT_CORP_MSG = 202, "CharLeftCorpMsg"

    # moon mining
    MOONS_AUTOMATIC_FRACTURE = 401, "MoonminingAutomaticFracture"
    MOONS_EXTRACTION_CANCELED = 402, "MoonminingExtractionCancelled"
    MOONS_EXTRACTION_FINISHED = 403, "MoonminingExtractionFinished"
    MOONS_EXTRACTION_STARTED = 404, "MoonminingExtractionStarted"
    MOONS_LASER_FIRED = 405, "MoonminingLaserFired"

    # upwell structures
    STRUCTURE_ANCHORING = 501, "StructureAnchoring"
    STRUCTURE_DESTROYED = 502, "StructureDestroyed"
    STRUCTURE_FUEL_ALERT = 503, "StructureFuelAlert"
    STRUCTURE_LOST_ARMOR = 504, "StructureLostArmor"
    STRUCTURE_LOST_SHIELD = 505, "StructureLostShields"
    STRUCTURE_ONLINE = 506, "StructureOnline"
    STRUCTURE_SERVICES_OFFLINE = 507, "StructureServicesOffline"
    STRUCTURE_UNANCHORING = 508, "StructureUnanchoring"
    STRUCTURE_UNDER_ATTACK = 509, "StructureUnderAttack"
    STRUCTURE_WENT_HIGH_POWER = 510, "StructureWentHighPower"
    STRUCTURE_WENT_LOW_POWER = 511, "StructureWentLowPower"

    # STRUCTURE_REINFORCE_CHANGED = 512, "StructureReinforceChange"
    OWNERSHIP_TRANSFERRED = 513, "OwnershipTransferred"

    # customs offices
    ORBITAL_ATTACKED = 601, "OrbitalAttacked"
    ORBITAL_REINFORCED = 602, "OrbitalReinforced"

    # starbases
    TOWER_ALERT_MSG = 701, "TowerAlertMsg"
    TOWER_RESOURCE_ALERT_MSG = 702, "TowerResourceAlertMsg"

    # sov
    SOV_ENTOSIS_CAPTURE_STARTED = 801, "EntosisCaptureStarted"
    SOV_COMMAND_NODE_EVENT_STARTED = 802, "SovCommandNodeEventStarted"
    SOV_ALL_CLAIM_ACQUIRED_MSG = 803, "SovAllClaimAquiredMsg"
    SOV_STRUCTURE_REINFORCED = 804, "SovStructureReinforced"
    SOV_STRUCTURE_DESTROYED = 805, "SovStructureDestroyed"

    @classmethod
    def relevant_for_timerboard(cls) -> list:
        return [
            cls.STRUCTURE_LOST_SHIELD,
            cls.STRUCTURE_LOST_ARMOR,
            cls.STRUCTURE_ANCHORING,
            cls.ORBITAL_REINFORCED,
            cls.MOONS_EXTRACTION_STARTED,
            cls.MOONS_EXTRACTION_CANCELED,
            cls.SOV_STRUCTURE_REINFORCED,
        ]

    @classmethod
    def relevant_for_alliance_level(cls) -> list:
        return [
            cls.SOV_ENTOSIS_CAPTURE_STARTED,
            cls.SOV_COMMAND_NODE_EVENT_STARTED,
            cls.SOV_ALL_CLAIM_ACQUIRED_MSG,
            cls.SOV_STRUCTURE_REINFORCED,
            cls.SOV_STRUCTURE_DESTROYED,
        ]

    @classmethod
    def enabled_by_default(cls) -> list:
        return list(
            set(NotificationType.values)
            - {cls.CHAR_APP_ACCEPT_MSG, cls.CHAR_LEFT_CORP_MSG}
        )


def get_default_notification_types():
    """DEPRECATED: generates a set of all existing notification types as default"""
    return tuple(sorted([str(x[0]) for x in NotificationType.choices]))


class Webhook(WebhookBase):
    """A destination for forwarding notification alerts"""

    notification_types = MultiSelectField(
        choices=NotificationType.choices,
        default=NotificationType.enabled_by_default(),
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
    is_default = models.BooleanField(
        default=False,
        help_text=(
            "whether owners have this webhook automatically " "pre-set when created"
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

    notification_id = models.BigIntegerField(validators=[MinValueValidator(0)])
    owner = models.ForeignKey(
        "Owner",
        on_delete=models.CASCADE,
        help_text="Corporation that received this notification",
    )
    sender = models.ForeignKey(EveEntity, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    notification_type = models.IntegerField(choices=NotificationType.choices)
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

    def __str__(self) -> str:
        return str(self.notification_id)

    def __repr__(self) -> str:
        return "%s(notification_id=%d, owner='%s', notification_type='%s')" % (
            self.__class__.__name__,
            self.notification_id,
            self.owner,
            self.get_notification_type_display(),
        )

    @property
    def is_alliance_level(self) -> bool:
        """whether this is an alliance level notification"""
        return self.notification_type in NotificationType.relevant_for_alliance_level()

    @classmethod
    def get_all_types(cls) -> Set[int]:
        """returns a set with all supported notification types"""
        return {x[0] for x in NotificationType.choices}

    @classmethod
    def get_all_type_names(cls) -> Set[str]:
        """returns a set with names of all supported notification types"""
        return {x[1] for x in NotificationType.choices}

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
        if self.notification_type in [
            NotificationType.ORBITAL_ATTACKED,
            NotificationType.STRUCTURE_UNDER_ATTACK,
        ]:
            parsed_text = self.get_parsed_text()
            corporation_id = None
            if self.notification_type == NotificationType.STRUCTURE_UNDER_ATTACK:
                if (
                    "corpLinkData" in parsed_text
                    and len(parsed_text["corpLinkData"]) >= 3
                ):
                    corporation_id = int(parsed_text["corpLinkData"][2])

            if self.notification_type == NotificationType.ORBITAL_ATTACKED:
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
        add_prefix = make_logger_prefix("notification:{}".format(self.notification_id))
        logger.info(add_prefix("Trying to sent to webhook: %s" % webhook))
        success = False
        try:
            embed, ping_type = self._generate_embed(webhook.language_code)
        except Exception as ex:
            logger.warning(add_prefix("Failed to generate embed: %s" % ex))
            raise ex
        else:
            if (
                webhook.has_default_pings_enabled
                and self.owner.has_default_pings_enabled
            ):
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
        ) and self.notification_type in NotificationType.relevant_for_timerboard():
            parsed_text = self.get_parsed_text()
            try:
                with translation.override(STRUCTURES_DEFAULT_LANGUAGE):
                    if self.notification_type in [
                        NotificationType.STRUCTURE_LOST_ARMOR,
                        NotificationType.STRUCTURE_LOST_SHIELD,
                    ]:
                        timer_created = self._gen_timer_structure_reinforcement(
                            parsed_text, token
                        )
                    elif self.notification_type == NotificationType.STRUCTURE_ANCHORING:
                        timer_created = self._gen_timer_structure_anchoring(parsed_text)
                    elif (
                        self.notification_type
                        == NotificationType.SOV_STRUCTURE_REINFORCED
                    ):
                        timer_created = self._gen_timer_sov_reinforcements(parsed_text)
                    elif self.notification_type == NotificationType.ORBITAL_REINFORCED:
                        timer_created = self._gen_timer_orbital_reinforcements(
                            parsed_text
                        )
                    elif self.notification_type in [
                        NotificationType.MOONS_EXTRACTION_STARTED,
                        NotificationType.MOONS_EXTRACTION_CANCELED,
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
                NotificationType.STRUCTURE_LOST_SHIELD: gettext("Armor timer"),
                NotificationType.STRUCTURE_LOST_ARMOR: gettext("Final timer"),
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
                NotificationType.STRUCTURE_LOST_SHIELD: Timer.TYPE_ARMOR,
                NotificationType.STRUCTURE_LOST_ARMOR: Timer.TYPE_HULL,
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

        eve_time = ldap_datetime_2_dt(parsed_text["decloakTime"])
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
        eve_time = ldap_datetime_2_dt(parsed_text["reinforceExitTime"])
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
            eve_time = ldap_datetime_2_dt(parsed_text["readyTime"])
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

        if self.notification_type == NotificationType.MOONS_EXTRACTION_STARTED:
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

        elif self.notification_type == NotificationType.MOONS_EXTRACTION_CANCELED:
            notifications_qs = Notification.objects.filter(
                notification_type=NotificationType.MOONS_EXTRACTION_STARTED,
                owner=self.owner,
                is_timer_added=True,
                timestamp__lte=self.timestamp,
            ).order_by("-timestamp")

            for notification in notifications_qs:
                parsed_text_2 = notification.get_parsed_text()
                my_structure_type_id = parsed_text_2["structureTypeID"]
                if my_structure_type_id == parsed_text["structureTypeID"]:
                    eve_time = ldap_datetime_2_dt(parsed_text_2["readyTime"])
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
