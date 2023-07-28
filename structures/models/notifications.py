"""Notification related models for Structures."""

# pylint: disable = duplicate-code

import math
from typing import Optional, Tuple, Union

import dhooks_lite
import yaml
from multiselectfield import MultiSelectField
from requests.exceptions import HTTPError

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import translation
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from eveuniverse.models import EveEntity, EveMoon, EvePlanet, EveSolarSystem, EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.django import app_labels
from app_utils.logging import LoggerAddTag
from app_utils.urls import static_file_absolute_url

from structures import __title__
from structures.app_settings import (  # STRUCTURES_NOTIFICATION_DISABLE_ESI_FUEL_ALERTS,
    STRUCTURES_ADD_TIMERS,
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_NOTIFICATION_SET_AVATAR,
    STRUCTURES_REPORT_NPC_ATTACKS,
)
from structures.constants import EveCategoryId, EveCorporationId, EveTypeId
from structures.core.notification_types import NotificationType
from structures.managers import (
    GeneratedNotificationManager,
    NotificationManager,
    WebhookManager,
)
from structures.webhooks.models import WebhookBase

from .structures_1 import Structure

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


def get_default_notification_types():
    """DEPRECATED: generates a set of all existing notification types as default.
    Required to support older migrations."""
    return tuple(sorted([str(x[0]) for x in NotificationType.values]))


class Webhook(WebhookBase):
    """A destination for forwarding notification alerts."""

    notification_types = MultiSelectField(
        choices=NotificationType.choices,
        default=NotificationType.webhook_defaults(),
        verbose_name=_("notification types"),
        help_text=_(
            "Select which type of notifications should be forwarded to this webhook"
        ),
    )
    language_code = models.CharField(
        max_length=8,
        choices=LANGUAGES,
        default=None,
        null=True,
        blank=True,
        verbose_name=_("language"),
        help_text=_("language of notifications send to this webhook"),
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("is default"),
        help_text=_(
            "Whether owners have this webhook automatically pre-set when created"
        ),
    )
    has_default_pings_enabled = models.BooleanField(
        default=True,
        verbose_name=_("has default pings enabled"),
        help_text=(
            "To enable or disable pinging of notifications for this webhook "
            "e.g. with @everyone and @here"
        ),
    )
    ping_groups = models.ManyToManyField(
        Group,
        default=None,
        blank=True,
        related_name="+",
        verbose_name=_("ping groups"),
        help_text=_("Groups to be pinged for each notification - "),
    )
    objects = WebhookManager()

    class Meta:
        verbose_name = _("webhook")
        verbose_name_plural = _("webhooks")

    @staticmethod
    def text_bold(text) -> str:
        """Format the given text in bold."""
        return f"**{text}**" if text else ""


# pylint: disable = too-many-public-methods
class NotificationBase(models.Model):
    """Base model for a notification."""

    is_sent = models.BooleanField(
        default=False,
        verbose_name=_("is sent"),
        help_text=_("True when this notification has been forwarded to Discord"),
    )
    is_timer_added = models.BooleanField(
        null=True,
        default=False,
        verbose_name=_("is timer added"),
        help_text=_("True when a timer has been added for this notification"),
    )
    notif_type = models.CharField(
        max_length=100,
        default="",
        db_index=True,
        verbose_name=_("type"),
        help_text=_("type of this notification"),
    )
    owner = models.ForeignKey(
        "Owner",
        on_delete=models.CASCADE,
        verbose_name=_("owner"),
        help_text=_("Corporation that owns this notification"),
    )
    structures = models.ManyToManyField(
        Structure,
        verbose_name=_("structures"),
        help_text=_("Structures this notification is about (if any)"),
    )

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ping_type_override = None
        self._color_override = None
        self._parsed_text = {}

    def __str__(self) -> str:
        return f"{self.notification_id}:{self.notif_type}"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"notification_id={self.notification_id}, "
            f"owner='{self.owner}', "
            f"notif_type='{self.notif_type}'"
            ")"
        )

    @property
    def is_alliance_level(self) -> bool:
        """Whether this is an alliance level notification."""
        return self.notif_type in NotificationType.relevant_for_alliance_level()

    @property
    def can_be_rendered(self) -> bool:
        """Whether this notification can be rendered in Discord."""
        return self.notif_type in NotificationType.values

    @property
    def can_have_timer(self) -> bool:
        """Whether this notification can have a timer."""
        return self.notif_type in NotificationType.relevant_for_timerboard()

    @property
    def is_structure_related(self) -> bool:
        """Weather this notification related to a structure."""
        return self.notif_type in NotificationType.structure_related()

    @property
    def is_generated(self) -> bool:
        """Return True if this notification is generated, else False."""
        raise NotImplementedError()

    @property
    def is_temporary(self) -> bool:
        """Return True if this is a temporary notification, else False."""
        raise NotImplementedError()

    @property
    def color_override(self) -> Optional[int]:
        """Return overridden color if set, else None."""
        return self._color_override

    @property
    def ping_type_override(self) -> Optional[Webhook.PingType]:
        """Return overridden ping type if set, else None."""
        return self._ping_type_override

    def is_npc_attacking(self) -> bool:
        """Return True if this notification is about NPC attacking, else False."""
        raise NotImplementedError()

    def parsed_text(self) -> dict:
        """Return parsed text of this notification."""
        return self._parsed_text

    def eve_moon(self, key: str = "moonID") -> EveMoon:
        """Return it's moon extracted from the notification text.
        Will raise KeyError if not found.
        """
        obj_id = self._parsed_text[key]
        obj, _ = EveMoon.objects.get_or_create_esi(id=obj_id)
        return obj

    def eve_planet(self, key: str = "planetID") -> EvePlanet:
        """Return it's moon extracted from the notification text.
        Will raise KeyError if not found.
        """
        obj_id = self._parsed_text[key]
        obj, _ = EvePlanet.objects.get_or_create_esi(id=obj_id)
        return obj

    def eve_solar_system(self, key: str = "solarSystemID") -> EveSolarSystem:
        """Return solar system extracted from the notification text.
        Will raise KeyError if not found.
        """
        obj_id = self._parsed_text[key]
        obj, _ = EveSolarSystem.objects.get_or_create_esi(id=obj_id)
        return obj

    def eve_structure_type(self, key: str = "structureTypeID") -> EveType:
        """Return structure type extracted from the notification text.
        Will raise KeyError if not found.
        """
        obj_id = self._parsed_text[key]
        obj, _ = EveType.objects.get_or_create_esi(id=obj_id)
        return obj

    def send_to_configured_webhooks(
        self,
        ping_type_override: Optional[Union[Webhook.PingType, str]] = None,
        use_color_override: bool = False,
        color_override: Optional[int] = None,
    ) -> Optional[bool]:
        """Send this notification to all active webhooks which have this
        notification type configured
        and apply filter for NPC attacks and alliance level if needed.

        Returns True, if notifications has been successfully send to webhooks
        Returns None, if owner has no fitting webhook
        Returns False, if sending to any webhooks failed
        """
        if self.filter_for_npc_attacks():
            logger.debug("%s: Will not send NPC attacks", self)
            return None

        if self.filter_for_alliance_level():
            logger.debug(
                "%s: Alliance level notifications are not enabled for this owner", self
            )
            return None

        webhooks_qs = self.relevant_webhooks()
        if not webhooks_qs.exists():
            logger.debug("%s: No relevant webhook found", self)
            return None

        if ping_type_override:
            self._ping_type_override = Webhook.PingType(ping_type_override)
        if use_color_override:
            self._color_override = color_override
        success = True
        for webhook in webhooks_qs:
            success &= self.send_to_webhook(webhook)
        return success

    def filter_for_npc_attacks(self) -> bool:
        """True when notification to be filtered out due to npc attacks."""
        return not STRUCTURES_REPORT_NPC_ATTACKS and self.is_npc_attacking()

    def filter_for_alliance_level(self) -> bool:
        """True when notification to be filtered out due to alliance level."""
        return (
            self.is_alliance_level
            and self.owner.corporation.alliance is not None
            and not self.owner.is_alliance_main
        )

    def relevant_webhooks(self) -> models.QuerySet:
        """Determine relevant webhooks matching this notification type."""
        if not self.is_structure_related:
            structures_qs = Structure.objects.none()
        else:
            structures_qs = self.calc_related_structures()
        if (
            structures_qs.exists()
            and structures_qs.filter(webhooks__isnull=False).count() == 1
        ):
            webhooks_qs = structures_qs.first().webhooks.filter(
                notification_types__contains=self.notif_type, is_active=True
            )
        else:
            webhooks_qs = self.owner.webhooks.filter(
                notification_types__contains=self.notif_type, is_active=True
            )
        return webhooks_qs

    def calc_related_structures(self) -> models.QuerySet[Structure]:
        """Identify structures this notification is related to.

        Returns:
        - structures if any found or empty list if there are no related structures
        """
        if not self._parsed_text:
            return Structure.objects.none()

        if self.notif_type in {
            NotificationType.STRUCTURE_ONLINE,
            NotificationType.STRUCTURE_FUEL_ALERT,
            NotificationType.STRUCTURE_JUMP_FUEL_ALERT,
            NotificationType.STRUCTURE_REFUELED_EXTRA,
            NotificationType.STRUCTURE_SERVICES_OFFLINE,
            NotificationType.STRUCTURE_WENT_LOW_POWER,
            NotificationType.STRUCTURE_WENT_HIGH_POWER,
            NotificationType.STRUCTURE_UNANCHORING,
            NotificationType.STRUCTURE_UNDER_ATTACK,
            NotificationType.STRUCTURE_LOST_SHIELD,
            NotificationType.STRUCTURE_LOST_ARMOR,
            NotificationType.STRUCTURE_DESTROYED,
            NotificationType.OWNERSHIP_TRANSFERRED,
            NotificationType.STRUCTURE_ANCHORING,
            NotificationType.MOONMINING_EXTRACTION_STARTED,
            NotificationType.MOONMINING_EXTRACTION_FINISHED,
            NotificationType.MOONMINING_AUTOMATIC_FRACTURE,
            NotificationType.MOONMINING_EXTRACTION_CANCELLED,
            NotificationType.MOONMINING_LASER_FIRED,
        }:
            structure_id = self._parsed_text["structureID"]
            return Structure.objects.filter(id=structure_id)

        if self.notif_type == NotificationType.STRUCTURE_REINFORCE_CHANGED:
            structure_ids = [
                structure_info[0]
                for structure_info in self._parsed_text["allStructureInfo"]
            ]
            return Structure.objects.filter(id__in=structure_ids)

        if self.notif_type in {
            NotificationType.ORBITAL_ATTACKED,
            NotificationType.ORBITAL_REINFORCED,
        }:
            return Structure.objects.filter(
                eve_planet_id=self._parsed_text["planetID"],
                eve_type_id=self._parsed_text["typeID"],
            )

        if self.notif_type in {
            NotificationType.TOWER_ALERT_MSG,
            NotificationType.TOWER_RESOURCE_ALERT_MSG,
            NotificationType.TOWER_REFUELED_EXTRA,
        }:
            return Structure.objects.filter(
                eve_moon_id=self._parsed_text["moonID"],
                eve_type_id=self._parsed_text["typeID"],
            )

        return Structure.objects.none()

    def send_to_webhook(self, webhook: Webhook) -> bool:
        """Send this notification to a webhook.

        Return True if successful, else False.
        """
        logger.info("%s: Trying to sent to webhook: %s", self, webhook)
        try:
            embed, ping_type = self._generate_embed(webhook.language_code)
        except (OSError, NotImplementedError) as ex:
            logger.warning("%s: Failed to generate embed: %s", self, ex, exc_info=True)
            return False

        content = self._create_content_with_pings(webhook, ping_type)
        content += self._add_discord_group_pings(webhook)

        username, avatar_url = self._gen_avatar()
        new_queue_size = webhook.send_message(
            content=content, embeds=[embed], username=username, avatar_url=avatar_url
        )
        success = new_queue_size > 0
        if success and not self.is_temporary:
            self.is_sent = True
            self.save()
        return success

    def _create_content_with_pings(self, webhook, ping_type):
        if webhook.has_default_pings_enabled and self.owner.has_default_pings_enabled:
            if ping_type == Webhook.PingType.EVERYONE:
                return "@everyone"

            if ping_type == Webhook.PingType.HERE:
                return "@here"

        return ""

    def _add_discord_group_pings(self, webhook) -> str:
        if not webhook.ping_groups.exists() and not self.owner.ping_groups.exists():
            return ""

        if "discord" not in app_labels():
            return ""

        DiscordUser = self._import_discord()
        groups = set(self.owner.ping_groups.all()) | set(webhook.ping_groups.all())
        content = ""
        for group in groups:
            try:
                role = DiscordUser.objects.group_to_role(group)
            except HTTPError:
                logger.warning("Failed to get Discord roles", exc_info=True)
            else:
                if role:
                    content += f" <@&{role['id']}>"

        return content

    def _generate_embed(
        self, language_code: Optional[str]
    ) -> Tuple[dhooks_lite.Embed, Optional[Webhook.PingType]]:
        """Generates a Discord embed for this notification."""
        from structures.core.notification_embeds import NotificationBaseEmbed

        logger.info("Creating embed with language = %s", language_code)
        with translation.override(language_code):
            notification_embed = NotificationBaseEmbed.create(self)
            embed = notification_embed.generate_embed()
            return embed, notification_embed.ping_type

    @staticmethod
    def _import_discord() -> object:
        from allianceauth.services.modules.discord.models import DiscordUser

        return DiscordUser

    def _gen_avatar(self) -> Tuple[Optional[str], Optional[str]]:
        if STRUCTURES_NOTIFICATION_SET_AVATAR:
            username = "Notifications"
            avatar_url = static_file_absolute_url("structures/img/structures_logo.png")
        else:
            username = None
            avatar_url = None
        return username, avatar_url

    def add_or_remove_timer(self) -> bool:
        """Add/remove a timer related to this notification for some types.

        Returns True when timers where added or removed, else False
        """
        if (
            not STRUCTURES_ADD_TIMERS
            or self.notif_type not in NotificationType.relevant_for_timerboard()
        ):
            return False

        from structures.core import notification_timers

        try:
            with translation.override(STRUCTURES_DEFAULT_LANGUAGE):
                return notification_timers.add_or_remove_timer(self)
        except OSError as ex:
            logger.warning(
                "%s: Failed to add timer from notification: %s",
                self,
                ex,
                exc_info=True,
            )
        return False


class Notification(NotificationBase):
    """A notification in Eve Online.

    Notifications are usually created from Eve Online notifications received from ESI,
    but they can also be generated directly by Structures.
    """

    TEMPORARY_NOTIFICATION_ID = 999999999999

    notification_id = models.PositiveBigIntegerField(verbose_name=_("id"))
    created = models.DateTimeField(
        null=True,
        default=None,
        verbose_name=_("created"),
        help_text=_("Date when this notification was first received from ESI"),
    )
    is_read = models.BooleanField(
        null=True,
        default=None,
        verbose_name=_("is read"),
        help_text=_("True when this notification has read in the eve client"),
    )
    last_updated = models.DateTimeField(
        verbose_name=_("last updated"),
        help_text=_("Date when this notification has last been updated from ESI"),
    )
    sender = models.ForeignKey(
        EveEntity,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name=_("sender"),
    )

    text = models.TextField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("text"),
        help_text=_("Notification details in YAML"),
    )
    timestamp = models.DateTimeField(db_index=True, verbose_name=_("timestamp"))

    objects = NotificationManager()

    class Meta:
        verbose_name = _("eve notification")
        verbose_name_plural = _("eve notifications")
        unique_together = (("notification_id", "owner"),)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._parsed_text = yaml.safe_load(self.text) if self.text else {}

    def save(self, *args, **kwargs) -> None:
        if self.is_temporary:
            raise ValueError("Temporary notifications can not be saved")
        super().save(*args, **kwargs)

    @property
    def is_temporary(self) -> bool:
        return self.notification_id == self.TEMPORARY_NOTIFICATION_ID

    @property
    def is_generated(self) -> bool:
        return self.is_temporary

    # @classmethod
    # def get_all_types(cls) -> Set[int]:
    #     """returns a set with all supported notification types"""
    #     return {x[0] for x in NotificationType.choices}

    def parsed_text(self) -> dict:
        """Returns the notifications's text as dict."""
        return self._parsed_text

    def is_npc_attacking(self) -> bool:
        """Whether this notification is about a NPC attacking."""
        if self.notif_type in [
            NotificationType.ORBITAL_ATTACKED,
            NotificationType.STRUCTURE_UNDER_ATTACK,
        ]:
            parsed_text = self.parsed_text()
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
            if corporation_id:
                corporation = EveEntity(
                    category=EveEntity.CATEGORY_CORPORATION, id=corporation_id
                )
                return corporation.is_npc and not corporation.is_npc_starter_corporation
        return False

    def update_related_structures(self) -> bool:
        """Update related structure for this notification.

        Returns True if structures where updated, else False.
        """
        structures_qs = self.calc_related_structures()
        self.structures.clear()
        if structures_qs.exists():
            self.structures.add(*structures_qs)
            return True
        return False

    @classmethod
    def create_from_structure(
        cls, structure: Structure, notif_type: NotificationType, **kwargs
    ) -> "Notification":
        """Create new notification from given structure."""
        if "timestamp" not in kwargs:
            kwargs["timestamp"] = now()
        if "last_updated" not in kwargs:
            kwargs["last_updated"] = now()
        threshold = kwargs.pop("threshold") if "threshold" in kwargs else None
        if "text" not in kwargs:
            if notif_type in {
                NotificationType.STRUCTURE_FUEL_ALERT,
                NotificationType.STRUCTURE_REFUELED_EXTRA,
                NotificationType.STRUCTURE_JUMP_FUEL_ALERT,
            }:
                data = {
                    "solarsystemID": structure.eve_solar_system_id,
                    "structureID": structure.id,
                    "structureTypeID": structure.eve_type_id,
                    "threshold": threshold,
                }
            elif notif_type in {
                NotificationType.TOWER_RESOURCE_ALERT_MSG,
                NotificationType.TOWER_REFUELED_EXTRA,
            }:
                data = {
                    "moonID": structure.eve_moon_id,
                    "typeID": structure.eve_type_id,
                    "structureID": structure.id,
                }
            else:
                raise ValueError("text property not provided and can not be generated.")
            kwargs["text"] = yaml.dump(data)
        if "sender" not in kwargs:
            sender, _ = EveEntity.objects.get_or_create_esi(id=EveCorporationId.DED)
            kwargs["sender"] = sender
        kwargs["notification_id"] = cls.TEMPORARY_NOTIFICATION_ID
        kwargs["owner"] = structure.owner
        kwargs["notif_type"] = notif_type
        return cls(**kwargs)


class GeneratedNotification(NotificationBase):
    """A notification generated by the Structures app, not by Eve Online."""

    details = models.JSONField(default=dict, verbose_name=_("details"))
    last_updated = models.DateTimeField(auto_now=True, verbose_name=_("last_updated"))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("timestamp"))

    objects = GeneratedNotificationManager()

    class Meta:
        verbose_name = _("generated notification")
        verbose_name_plural = _("generated  notifications")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._parsed_text = self.details

    @property
    def notification_id(self) -> int:
        """Return the notification ID."""
        return self.pk

    @property
    def is_temporary(self) -> bool:
        return False

    @property
    def is_generated(self) -> bool:
        return True

    def is_npc_attacking(self) -> bool:
        return False


class BaseFuelAlertConfig(models.Model):
    """Configuration of structure fuel notifications."""

    channel_ping_type = models.CharField(
        max_length=2,
        choices=Webhook.PingType.choices,
        default=Webhook.PingType.HERE,
        verbose_name=_("channel pings"),
        help_text=_(
            "Option to ping every member of the channel. "
            "This setting can be overruled by the respective owner "
            "or webhook configuration"
        ),
    )
    color = models.IntegerField(
        choices=Webhook.Color.choices,
        default=Webhook.Color.WARNING,
        blank=True,
        null=True,
        verbose_name=_("color"),
        help_text=_("Context color of these notification on Discord"),
    )
    is_enabled = models.BooleanField(
        default=True,
        verbose_name=_("is_enabled"),
        help_text=_("Disabled configurations will not create any new alerts."),
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"#{self.pk}"

    def send_new_notifications(self, force: bool = False) -> None:
        """Send new fuel notifications based on this config."""
        raise NotImplementedError()

    @staticmethod
    def relevant_webhooks() -> models.QuerySet:
        """Webhooks relevant for processing fuel notifications based on this config."""
        raise NotImplementedError()


class FuelAlertConfig(BaseFuelAlertConfig):
    """Configuration of structure fuel notifications."""

    end = models.PositiveIntegerField(
        verbose_name=_("end"), help_text=_("End of alerts in hours before fuel expires")
    )
    repeat = models.PositiveIntegerField(
        verbose_name=_("repeat"),
        help_text=_(
            "Notifications will be repeated every x hours. Set to 0 for no repeats"
        ),
    )
    start = models.PositiveIntegerField(
        verbose_name=_("start"),
        help_text=_("Start of alerts in hours before fuel expires"),
    )

    class Meta:
        verbose_name = _("structure fuel alert config")
        verbose_name_plural = _("structure fuel alert configs")

    def clean(self) -> None:
        if self.start is None or self.end is None or self.repeat is None:  # Fixes #83
            return  # these will be caught by the form validation later
        if self.start <= self.end:
            raise ValidationError(
                _("Start must be before end, i.e. have a larger value.")
            )
        if self.repeat >= self.start - self.end:
            raise ValidationError(
                {"repeat": _("Repeat can not be larger that the interval size.")}
            )
        new = range(self.end, self.start)
        for config in FuelAlertConfig.objects.exclude(pk=self.pk):
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
            old_instance = FuelAlertConfig.objects.get(pk=self.pk)
        except FuelAlertConfig.DoesNotExist:
            old_instance = None
        super().save(*args, **kwargs)
        if old_instance and (
            old_instance.start != self.start
            or old_instance.end != self.end
            or old_instance.repeat != self.repeat
        ):
            self.structure_fuel_alerts.all().delete()

    def send_new_notifications(self, force: bool = False) -> None:
        """Send new fuel notifications based on this config."""
        structures = Structure.objects.filter(
            eve_type__eve_group__eve_category_id__in=[
                EveCategoryId.STARBASE,
                EveCategoryId.STRUCTURE,
            ],
            fuel_expires_at__isnull=False,
        )
        for structure in structures:
            if not structure.is_burning_fuel:
                continue
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
                notif, created = FuelAlert.objects.get_or_create(
                    structure=structure, config=self, hours=hours_last_alert
                )
                if created or force:
                    notif.send_generated_notification()

    @staticmethod
    def relevant_webhooks() -> models.QuerySet:
        """Webhooks relevant for processing fuel notifications based on this config."""
        return (
            Webhook.objects.filter(is_active=True)
            .filter(Q(owners__isnull=False) | Q(structures__isnull=False))
            .filter(
                Q(notification_types__contains=NotificationType.STRUCTURE_FUEL_ALERT)
                | Q(
                    notification_types__contains=NotificationType.TOWER_RESOURCE_ALERT_MSG
                )
            )
            .distinct()
        )


class JumpFuelAlertConfig(BaseFuelAlertConfig):
    """Configuration of jump fuel notifications."""

    threshold = models.PositiveIntegerField(
        verbose_name=_("threshold"),
        help_text=_(
            "Notifications will be sent once fuel level in units reaches this threshold"
        ),
    )

    class Meta:
        verbose_name = _("jump fuel alert config")
        verbose_name_plural = _("jump fuel alert configs")

    def save(self, *args, **kwargs) -> None:
        try:
            old_instance = JumpFuelAlertConfig.objects.get(pk=self.pk)
        except JumpFuelAlertConfig.DoesNotExist:
            old_instance = None
        super().save(*args, **kwargs)
        if old_instance and (old_instance.threshold != self.threshold):
            self.jump_fuel_alerts.all().delete()

    def send_new_notifications(self, force: bool = False) -> None:
        """Send new fuel notifications based on this config."""
        jump_gates = Structure.objects.filter(eve_type_id=EveTypeId.JUMP_GATE)
        for jump_gate in jump_gates:
            if not jump_gate.is_burning_fuel:
                continue
            fuel_quantity = jump_gate.jump_fuel_quantity()
            if fuel_quantity and fuel_quantity < self.threshold:
                notif, created = JumpFuelAlert.objects.get_or_create(
                    structure=jump_gate, config=self
                )
                if created or force:
                    notif.send_generated_notification()

    @staticmethod
    def relevant_webhooks() -> models.QuerySet:
        """Webhooks relevant for processing jump fuel notifications based on this config."""
        return Webhook.objects.filter(
            is_active=True,
            notification_types__contains=NotificationType.STRUCTURE_JUMP_FUEL_ALERT,
        ).filter(Q(owners__isnull=False) | Q(structures__isnull=False))


class BaseFuelAlert(models.Model):
    """Base class for fuel alerts."""

    class Meta:
        abstract = True

    def send_generated_notification(self):
        """Send a generated notification."""
        raise NotImplementedError()


class FuelAlert(BaseFuelAlert):
    """A generated notification alerting about fuel getting low in structures."""

    structure = models.ForeignKey(
        Structure,
        on_delete=models.CASCADE,
        related_name="structure_fuel_alerts",
        verbose_name=_("structure"),
    )
    config = models.ForeignKey(
        FuelAlertConfig,
        on_delete=models.CASCADE,
        related_name="structure_fuel_alerts",
        verbose_name=_("configuration"),
    )
    hours = models.PositiveIntegerField(
        db_index=True,
        verbose_name=_("hours"),
        help_text=_("number of hours before fuel expiration this alert was sent"),
    )

    class Meta:
        verbose_name = _("structure fuel alert")
        verbose_name_plural = _("structure fuel alerts")
        constraints = [
            models.UniqueConstraint(
                fields=["structure", "config", "hours"],
                name="functional_pk_fuelalert",
            )
        ]

    def __str__(self) -> str:
        return f"{self.structure}-{self.config}-{self.hours}"

    def send_generated_notification(self):
        notif_type = (
            NotificationType.TOWER_RESOURCE_ALERT_MSG
            if self.structure.is_starbase
            else NotificationType.STRUCTURE_FUEL_ALERT
        )
        notif = Notification.create_from_structure(
            structure=self.structure, notif_type=notif_type
        )
        notif.send_to_configured_webhooks(
            ping_type_override=self.config.channel_ping_type,
            use_color_override=True,
            color_override=self.config.color,
        )


class JumpFuelAlert(BaseFuelAlert):
    """A generated notification alerting about jump fuel getting low."""

    structure = models.ForeignKey(
        Structure,
        on_delete=models.CASCADE,
        related_name="jump_fuel_alerts",
        verbose_name=_("structure"),
    )
    config = models.ForeignKey(
        JumpFuelAlertConfig,
        on_delete=models.CASCADE,
        related_name="jump_fuel_alerts",
        verbose_name=_("configuration"),
    )

    class Meta:
        verbose_name = _("jump fuel alert")
        verbose_name_plural = _("jump fuel alerts")

    def __str__(self) -> str:
        return f"{self.structure}-{self.config}"

    def send_generated_notification(self) -> None:
        notif = Notification.create_from_structure(
            structure=self.structure,
            notif_type=NotificationType.STRUCTURE_JUMP_FUEL_ALERT,
            threshold=self.config.threshold,
        )
        notif.send_to_configured_webhooks(
            ping_type_override=self.config.channel_ping_type,
            use_color_override=True,
            color_override=self.config.color,
        )
