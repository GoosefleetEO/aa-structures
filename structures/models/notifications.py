"""Notification related models"""

import math
from typing import Tuple

import dhooks_lite
import yaml
from multiselectfield import MultiSelectField
from requests.exceptions import HTTPError

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import translation
from django.utils.functional import cached_property, classproperty
from django.utils.timezone import now
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from esi.models import Token

from allianceauth.eveonline.evelinks import dotlan, eveimageserver
from allianceauth.services.hooks import get_extension_logger
from app_utils.datetime import (
    DATETIME_FORMAT,
    ldap_time_2_datetime,
    ldap_timedelta_2_timedelta,
)
from app_utils.django import app_labels
from app_utils.logging import LoggerAddTag
from app_utils.urls import static_file_absolute_url

from .. import __title__, constants
from ..app_settings import (
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED,
    STRUCTURES_NOTIFICATION_DISABLE_ESI_FUEL_ALERTS,
    STRUCTURES_NOTIFICATION_SET_AVATAR,
    STRUCTURES_REPORT_NPC_ATTACKS,
    STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
)
from ..managers import EveEntityManager, NotificationManager
from ..webhooks.models import WebhookBase
from .eveuniverse import EveMoon, EvePlanet, EveSolarSystem
from .structures import Structure

if "timerboard" in app_labels():
    from allianceauth.timerboard.models import Timer as AuthTimer

    has_auth_timers = True
else:
    has_auth_timers = False

if "structuretimers" in app_labels():
    from structuretimers.models import Timer

    from eveuniverse.models import EveSolarSystem as EveSolarSystem2
    from eveuniverse.models import EveType as EveType2

    has_structure_timers = True
else:
    has_structure_timers = False

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

# Supported languages
LANGUAGES = (
    ("en", _("English")),
    ("de", _("German")),
    ("es", _("Spanish")),
    ("zh-hans", _("Chinese Simplified")),
    ("ru", _("Russian")),
    ("ko", _("Korean")),
)


class NotificationType(models.TextChoices):
    """Definition of all supported notification types."""

    # upwell structures
    STRUCTURE_ANCHORING = "StructureAnchoring", _("Upwell structure anchoring")
    STRUCTURE_ONLINE = "StructureOnline", _("Upwell structure went online")
    STRUCTURE_SERVICES_OFFLINE = "StructureServicesOffline", _(
        "Upwell structure services went offline"
    )
    STRUCTURE_WENT_HIGH_POWER = "StructureWentHighPower", _(
        "Upwell structure went high power"
    )
    STRUCTURE_WENT_LOW_POWER = "StructureWentLowPower", _(
        "Upwell structure went low power"
    )
    STRUCTURE_UNANCHORING = "StructureUnanchoring", _("Upwell structure unanchoring")
    STRUCTURE_FUEL_ALERT = "StructureFuelAlert", _("Upwell structure fuel alert")
    STRUCTURE_UNDER_ATTACK = "StructureUnderAttack", _(
        "Upwell structure is under attack"
    )
    STRUCTURE_LOST_SHIELD = "StructureLostShields", _("Upwell structure lost shields")
    STRUCTURE_LOST_ARMOR = "StructureLostArmor", _("Upwell structure lost armor")
    STRUCTURE_DESTROYED = "StructureDestroyed", _("Upwell structure destroyed")

    STRUCTURE_REINFORCE_CHANGED = "StructuresReinforcementChanged", _(
        "Upwell structure reinforcement time changed"
    )
    OWNERSHIP_TRANSFERRED = "OwnershipTransferred", _(
        "Upwell structure ownership transferred"
    )

    # customs offices
    ORBITAL_ATTACKED = "OrbitalAttacked", _("Customs office attacked")
    ORBITAL_REINFORCED = "OrbitalReinforced", _("Customs office reinforced")

    # starbases
    TOWER_ALERT_MSG = "TowerAlertMsg", _("Starbase attacked")
    TOWER_RESOURCE_ALERT_MSG = "TowerResourceAlertMsg", _("Starbase fuel alert")

    # moon mining
    MOONMINING_EXTRACTION_STARTED = "MoonminingExtractionStarted", _(
        "Moonmining extraction started"
    )
    MOONMINING_LASER_FIRED = "MoonminingLaserFired", _("Moonmining laser fired")
    MOONMINING_EXTRACTION_CANCELLED = "MoonminingExtractionCancelled", _(
        "Moonmining extraction cancelled"
    )
    MOONMINING_EXTRACTION_FINISHED = "MoonminingExtractionFinished", _(
        "Moonmining extraction finished"
    )
    MOONMINING_AUTOMATIC_FRACTURE = "MoonminingAutomaticFracture", _(
        "Moonmining automatic fracture triggered"
    )

    # sov
    SOV_STRUCTURE_REINFORCED = "SovStructureReinforced", _(
        "Sovereignty structure reinforced"
    )
    SOV_STRUCTURE_DESTROYED = "SovStructureDestroyed", _(
        "Sovereignty structure destroyed"
    )
    SOV_ENTOSIS_CAPTURE_STARTED = "EntosisCaptureStarted", _(
        "Sovereignty entosis capture started"
    )
    SOV_COMMAND_NODE_EVENT_STARTED = "SovCommandNodeEventStarted", _(
        "Sovereignty command node event started"
    )
    SOV_ALL_CLAIM_ACQUIRED_MSG = "SovAllClaimAquiredMsg", _(
        "Sovereignty claim acknowledgment"
    )
    SOV_ALL_CLAIM_LOST_MSG = "SovAllClaimLostMsg", _("Sovereignty lost")

    # wars
    WAR_WAR_DECLARED = "WarDeclared", _("War declared")
    WAR_ALLY_JOINED_WAR_AGGRESSOR_MSG = "AllyJoinedWarAggressorMsg", _(
        "War ally joined aggressor"
    )
    WAR_ALLY_JOINED_WAR_AllY_MSG = "AllyJoinedWarAllyMsg", _("War ally joined ally")
    WAR_ALLY_JOINED_WAR_DEFENDER_MSG = "AllyJoinedWarDefenderMsg", _(
        "War ally joined defender"
    )
    WAR_WAR_ADOPTED = "WarAdopted", _("War adopted")
    WAR_WAR_INHERITED = "WarInherited", _("War inherited")
    WAR_CORP_WAR_SURRENDER_MSG = "CorpWarSurrenderMsg", _("War party surrendered")
    WAR_WAR_RETRACTED_BY_CONCORD = "WarRetractedByConcord", _(
        "War retracted by Concord"
    )
    WAR_CORPORATION_BECAME_ELIGIBLE = "CorpBecameWarEligible", _(
        "War corporation became eligable"
    )
    WAR_CORPORATION_NO_LONGER_ELIGIBLE = "CorpNoLongerWarEligible", _(
        "War corporation no longer eligable"
    )

    # corporation membership
    CORP_APP_NEW_MSG = "CorpAppNewMsg", _("Character submitted application")
    CORP_APP_INVITED_MSG = "CorpAppInvitedMsg", _(
        "Character invited to join corporation"
    )
    CORP_APP_REJECT_CUSTOM_MSG = "CorpAppRejectCustomMsg", _(
        "Corp application rejected"
    )
    CHAR_APP_WITHDRAW_MSG = "CharAppWithdrawMsg", _("Character withdrew application")
    CHAR_APP_ACCEPT_MSG = "CharAppAcceptMsg", _("Character joins corporation")
    CHAR_LEFT_CORP_MSG = "CharLeftCorpMsg", _("Character leaves corporation")

    @classproperty
    def webhook_defaults(cls) -> list:
        """List of default notifications for new webhooks."""
        return [
            cls.STRUCTURE_ANCHORING,
            cls.STRUCTURE_DESTROYED,
            cls.STRUCTURE_FUEL_ALERT,
            cls.STRUCTURE_LOST_ARMOR,
            cls.STRUCTURE_LOST_SHIELD,
            cls.STRUCTURE_ONLINE,
            cls.STRUCTURE_SERVICES_OFFLINE,
            cls.STRUCTURE_UNDER_ATTACK,
            cls.STRUCTURE_WENT_HIGH_POWER,
            cls.STRUCTURE_WENT_LOW_POWER,
            cls.ORBITAL_ATTACKED,
            cls.ORBITAL_REINFORCED,
            cls.TOWER_ALERT_MSG,
            cls.TOWER_RESOURCE_ALERT_MSG,
            cls.SOV_STRUCTURE_REINFORCED,
            cls.SOV_STRUCTURE_DESTROYED,
        ]

    @classproperty
    def relevant_for_timerboard(cls) -> list:
        return [
            cls.STRUCTURE_LOST_SHIELD,
            cls.STRUCTURE_LOST_ARMOR,
            cls.ORBITAL_REINFORCED,
            cls.MOONMINING_EXTRACTION_STARTED,
            cls.MOONMINING_EXTRACTION_CANCELLED,
            cls.SOV_STRUCTURE_REINFORCED,
        ]

    @classproperty
    def relevant_for_alliance_level(cls) -> list:
        return [
            cls.SOV_ENTOSIS_CAPTURE_STARTED,
            cls.SOV_COMMAND_NODE_EVENT_STARTED,
            cls.SOV_ALL_CLAIM_ACQUIRED_MSG,
            cls.SOV_STRUCTURE_REINFORCED,
            cls.SOV_STRUCTURE_DESTROYED,
            cls.WAR_ALLY_JOINED_WAR_AGGRESSOR_MSG,
            cls.WAR_CORP_WAR_SURRENDER_MSG,
            cls.WAR_WAR_DECLARED,
            cls.WAR_WAR_RETRACTED_BY_CONCORD,
            cls.WAR_WAR_ADOPTED,
            cls.WAR_WAR_INHERITED,
            cls.WAR_CORPORATION_BECAME_ELIGIBLE,
            cls.WAR_CORPORATION_NO_LONGER_ELIGIBLE,
        ]

    @classproperty
    def relevant_for_moonmining(cls) -> list:
        return [
            cls.MOONMINING_EXTRACTION_STARTED,
            cls.MOONMINING_EXTRACTION_CANCELLED,
            cls.MOONMINING_LASER_FIRED,
            cls.MOONMINING_EXTRACTION_FINISHED,
            cls.MOONMINING_AUTOMATIC_FRACTURE,
        ]

    @classproperty
    def relevant_for_forwarding(cls) -> list:
        all = set(cls.values)
        if STRUCTURES_NOTIFICATION_DISABLE_ESI_FUEL_ALERTS:
            all.discard(cls.STRUCTURE_FUEL_ALERT)
            all.discard(cls.TOWER_RESOURCE_ALERT_MSG)
        return list(all)


def get_default_notification_types():
    """DEPRECATED: generates a set of all existing notification types as default-"""
    return tuple(sorted([str(x[0]) for x in NotificationType.values]))


class Webhook(WebhookBase):
    """A destination for forwarding notification alerts."""

    notification_types = MultiSelectField(
        choices=NotificationType.choices,
        default=NotificationType.webhook_defaults,
        help_text=(
            "select which type of notifications should be forwarded to this webhook"
        ),
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
        related_name="+",
        help_text="Groups to be pinged for each notification - ",
    )

    @staticmethod
    def text_bold(text) -> str:
        """Format the given text in bold."""
        return f"**{text}**" if text else ""


class EveEntity(models.Model):
    """An EVE entity like a character or an alliance."""

    class Category(models.IntegerChoices):
        CHARACTER = 1, "character"
        CORPORATION = 2, "corporation"
        ALLIANCE = 3, "alliance"
        FACTION = 4, "faction"
        OTHER = 5, "other"

        @classmethod
        def from_esi_name(cls, esi_name: str) -> "EveEntity.Category":
            """Returns category for given ESI name."""
            for choice in cls.choices:
                if esi_name == choice[1]:
                    return cls(choice[0])
            return cls.OTHER

    id = models.PositiveIntegerField(primary_key=True, help_text="Eve Online ID")
    category = models.IntegerField(choices=Category.choices)
    name = models.CharField(max_length=255, null=True, default=None, blank=True)

    objects = EveEntityManager()

    def __str__(self) -> str:
        return str(self.name)

    def __repr__(self) -> str:
        return "{}(id={}, category='{}', name='{}')".format(
            self.__class__.__name__, self.id, self.get_category_display(), self.name
        )

    def profile_url(self) -> str:
        """Returns link to website with profile info about this entity."""
        if self.category == self.Category.CORPORATION:
            url = dotlan.corporation_url(self.name)
        elif self.category == self.Category.ALLIANCE:
            url = dotlan.alliance_url(self.name)
        else:
            url = ""
        return url

    def icon_url(self, size: int = 32) -> str:
        if self.category == self.Category.ALLIANCE:
            return eveimageserver.alliance_logo_url(self.id, size)
        elif (
            self.category == self.Category.CORPORATION
            or self.category == self.Category.FACTION
        ):
            return eveimageserver.corporation_logo_url(self.id, size)
        elif self.category == self.Category.CHARACTER:
            return eveimageserver.character_portrait_url(self.id, size)
        else:
            raise NotImplementedError()


class AbstractNotification(models.Model):
    """Shared functionality for notifications and fuel alerts."""

    class Meta:
        abstract = True

    def send_to_webhook(self, webhook: Webhook) -> bool:
        """Sends this notification to the configured webhook.

        returns True if successful, else False
        """
        logger.info("%s: Trying to sent to webhook: %s", self, webhook)
        success = False
        try:
            embed, ping_type = self._generate_embed(webhook.language_code)
        except (OSError, NotImplementedError) as ex:
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

    @staticmethod
    def _import_discord() -> object:
        from allianceauth.services.modules.discord.models import DiscordUser

        return DiscordUser

    def _gen_avatar(self) -> Tuple[str, str]:
        if STRUCTURES_NOTIFICATION_SET_AVATAR:
            username = "Notifications"
            avatar_url = static_file_absolute_url("structures/img/structures_logo.png")
        else:
            username = None
            avatar_url = None

        return username, avatar_url


class Notification(AbstractNotification):
    """An EVE Online notification about structures."""

    HTTP_CODE_TOO_MANY_REQUESTS = 429

    # event type structure map
    MAP_CAMPAIGN_EVENT_2_TYPE_ID = {
        1: constants.EVE_TYPE_ID_TCU,
        2: constants.EVE_TYPE_ID_IHUB,
    }
    MAP_TYPE_ID_2_TIMER_STRUCTURE_NAME = {
        constants.EVE_TYPE_ID_POCO: "POCO",
        constants.EVE_TYPE_ID_TCU: "TCU",
        constants.EVE_TYPE_ID_IHUB: "I-HUB",
    }

    notification_id = models.PositiveBigIntegerField(verbose_name="id")
    owner = models.ForeignKey(
        "Owner",
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="Corporation that received this notification",
    )

    sender = models.ForeignKey(EveEntity, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(db_index=True)
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
        default=False,
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

    objects = NotificationManager()

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
        """Whether this is an alliance level notification."""
        return self.notif_type in NotificationType.relevant_for_alliance_level

    @property
    def can_be_rendered(self) -> bool:
        """Whether this notification can be rendered in Discord."""
        return self.notif_type in NotificationType.values

    @property
    def can_have_timer(self) -> bool:
        """Whether this notification can have a timer."""
        return self.notif_type in NotificationType.relevant_for_timerboard

    # @classmethod
    # def get_all_types(cls) -> Set[int]:
    #     """returns a set with all supported notification types"""
    #     return {x[0] for x in NotificationType.choices}

    def get_parsed_text(self) -> dict:
        """Returns the notifications's text as dict."""
        return yaml.safe_load(self.text)

    def is_npc_attacking(self) -> bool:
        """Whether this notification is about a NPC attacking."""
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
        """True when notification to be filtered out due to npc attacks."""
        return not STRUCTURES_REPORT_NPC_ATTACKS and self.is_npc_attacking()

    def filter_for_alliance_level(self) -> bool:
        """True when notification to be filtered out due to alliance level."""
        return self.is_alliance_level and not self.owner.is_alliance_main

    def _generate_embed(
        self, language_code: str
    ) -> Tuple[dhooks_lite.Embed, Webhook.PingType]:
        """Generates a Discord embed for this notification."""
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
        """Add/removes a timer related to this notification for some types

        Returns True when a timer was processed, else False
        """
        timer_created = False
        if (
            has_auth_timers or has_structure_timers
        ) and self.notif_type in NotificationType.relevant_for_timerboard:
            parsed_text = self.get_parsed_text()
            try:
                with translation.override(STRUCTURES_DEFAULT_LANGUAGE):
                    if self.notif_type in [
                        NotificationType.STRUCTURE_LOST_ARMOR,
                        NotificationType.STRUCTURE_LOST_SHIELD,
                    ]:
                        timer_created = self._gen_timer_structure_reinforcement(
                            parsed_text, token
                        )
                    elif self.notif_type == NotificationType.SOV_STRUCTURE_REINFORCED:
                        timer_created = self._gen_timer_sov_reinforcements(parsed_text)
                    elif self.notif_type == NotificationType.ORBITAL_REINFORCED:
                        timer_created = self._gen_timer_orbital_reinforcements(
                            parsed_text
                        )
                    elif self.notif_type in [
                        NotificationType.MOONMINING_EXTRACTION_STARTED,
                        NotificationType.MOONMINING_EXTRACTION_CANCELLED,
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
        """Generate timer for structure reinforcements"""
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

    def _gen_timer_sov_reinforcements(self, parsed_text: str) -> bool:
        """Generate timer for sov reinforcements."""
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
        """Generate timer for orbital reinforcements."""
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
                id=constants.EVE_TYPE_ID_POCO
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
        """Generate timer for moon mining extractions."""
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

        if self.notif_type == NotificationType.MOONMINING_EXTRACTION_STARTED:
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

        elif self.notif_type == NotificationType.MOONMINING_EXTRACTION_CANCELLED:
            notifications_qs = Notification.objects.filter(
                notif_type=NotificationType.MOONMINING_EXTRACTION_STARTED,
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
        """Return generated details notes string for Timers."""
        return (
            "Automatically created from structure notification for "
            f"{self.owner.corporation} at {self.timestamp.strftime(DATETIME_FORMAT)}"
        )


class FuelNotification(AbstractNotification):
    """A generated notification alerting about fuel getting low in structures."""

    structure = models.ForeignKey(
        "Structure", on_delete=models.CASCADE, related_name="fuel_notifications"
    )
    config = models.ForeignKey(
        "FuelNotificationConfig",
        on_delete=models.CASCADE,
        related_name="fuel_notifications",
    )
    hours = models.PositiveIntegerField(
        db_index=True,
        help_text="number of hours before fuel expiration this alert was sent",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.structure}-{self.config}-{self.hours}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["structure", "config", "hours"],
                name="functional_pk_fuelnotification",
            )
        ]

    @cached_property
    def owner(self) -> models.Model:
        return self.structure.owner

    @property
    def notif_type(self) -> NotificationType:
        if self.structure.eve_type.is_upwell_structure:
            return NotificationType.STRUCTURE_FUEL_ALERT
        elif self.structure.eve_type.is_starbase:
            return NotificationType.TOWER_RESOURCE_ALERT_MSG
        raise NotImplementedError("Undefined structure type.")

    @cached_property
    def text(self) -> str:
        if self.structure.eve_type.is_upwell_structure:
            data = {
                "solarsystemID": self.structure.eve_solar_system_id,
                "structureID": self.structure.id,
                "structureTypeID": self.structure.eve_type_id,
            }
        elif self.structure.eve_type.is_starbase:
            data = {
                "moonID": self.structure.eve_moon_id,
                "typeID": self.structure.eve_type_id,
            }
        else:
            raise NotImplementedError("Undefined structure type.")
        return yaml.dump(data)

    def _generate_embed(
        self, language_code: str
    ) -> Tuple[dhooks_lite.Embed, Webhook.PingType]:
        """Generates a Discord embed for this notification."""
        from ..core.notification_embeds import NotificationBaseEmbed

        logger.info("Creating embed with language = %s" % language_code)
        with translation.override(language_code):
            sender, _ = EveEntity.objects.get_or_create_esi(
                eve_entity_id=self.owner.corporation.corporation_id
            )
            notification = Notification(
                notification_id=1,
                owner=self.owner,
                sender=sender,
                timestamp=now(),
                notif_type=self.notif_type,
                text=self.text,
                last_updated=now(),
            )
            notification_embed = NotificationBaseEmbed.create(notification)
            embed = notification_embed.generate_embed(
                use_custom_color=True, custom_color=self.config.color
            )
            return embed, self.config.channel_ping_type


class FuelNotificationConfig(models.Model):
    """Configuration of fuel notifications."""

    channel_ping_type = models.CharField(
        max_length=2,
        choices=Webhook.PingType.choices,
        default=Webhook.PingType.HERE,
        verbose_name="channel pings",
        help_text=(
            "Option to ping every member of the channel. "
            "This setting can be overruled by the respective owner "
            "or webhook configuration"
        ),
    )
    end = models.PositiveIntegerField(
        help_text="End of alerts in hours before fuel expires"
    )
    repeat = models.PositiveIntegerField(
        help_text=(
            "Notifications will be repeated every x hours. Set to 0 for no repeats"
        )
    )
    color = models.IntegerField(
        choices=Webhook.Color.choices,
        default=Webhook.Color.WARNING,
        blank=True,
        null=True,
    )
    is_enabled = models.BooleanField(default=True)
    start = models.PositiveIntegerField(
        help_text="Start of alerts in hours before fuel expires"
    )

    def __str__(self) -> str:
        return f"#{self.pk}"

    def clean(self) -> None:
        if self.start <= self.end:
            raise ValidationError(
                _("Start must be before end, i.e. have a larger value.")
            )
        if self.repeat >= self.start - self.end:
            raise ValidationError(
                {"repeat": _("Repeat can not be larger that the interval size.")}
            )
        new = range(self.end, self.start)
        for config in FuelNotificationConfig.objects.exclude(pk=self.pk):
            current = range(config.end, config.start)
            overlap = range(max(new[0], current[0]), min(new[-1], current[-1]) + 1)
            if len(overlap) > 0:
                raise ValidationError(
                    _(
                        "This configuration may not overlap with an "
                        "existing configuration."
                    )
                )

    def save(self, *args, **kwargs) -> None:
        try:
            old_instance = FuelNotificationConfig.objects.get(pk=self.pk)
        except FuelNotificationConfig.DoesNotExist:
            old_instance = None
        super().save(*args, **kwargs)
        if old_instance and (
            old_instance.start != self.start
            or old_instance.end != self.end
            or old_instance.repeat != self.repeat
        ):
            self.fuel_notifications.all().delete()

    def send_new_notifications(self, force: bool = False) -> None:
        """Send new fuel notifications based on this config."""
        for structure in self._structures_queryset():
            hours_left = structure.hours_fuel_expires
            if self.start >= hours_left >= self.end:
                hours_last_alert = (
                    self.start
                    - (
                        math.floor((self.start - hours_left) / self.repeat)
                        * self.repeat
                    )
                    if self.repeat
                    else self.start
                )
                notif, created = FuelNotification.objects.get_or_create(
                    structure=structure, config=self, hours=hours_last_alert
                )
                if created or force:
                    for webhook in structure.owner.webhooks.filter(
                        is_active=True, notification_types__contains=notif.notif_type
                    ):
                        notif.send_to_webhook(webhook)

    @staticmethod
    def _structures_queryset():
        """Queryset of all relevant structures."""
        return Structure.objects.filter(
            eve_type__eve_group__eve_category_id__in=[
                constants.EVE_CATEGORY_ID_STARBASE,
                constants.EVE_CATEGORY_ID_STRUCTURE,
            ],
            fuel_expires_at__isnull=False,
        )

    @staticmethod
    def relevant_webhooks() -> models.QuerySet:
        """Webhooks relevant for processing fuel notifications based on this config."""
        return (
            Webhook.objects.filter(owner__isnull=False)
            .filter(is_active=True)
            .filter(
                Q(notification_types__contains=NotificationType.STRUCTURE_FUEL_ALERT)
                | Q(
                    notification_types__contains=NotificationType.TOWER_RESOURCE_ALERT_MSG
                )
            )
            .distinct()
        )
