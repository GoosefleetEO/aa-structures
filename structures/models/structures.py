"""Structure related models."""

import datetime as dt
import math
import re
from typing import List, Optional

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Min, Sum
from django.utils.functional import cached_property
from django.utils.html import escape
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_noop
from eveuniverse.models import EveMoon, EvePlanet, EveSolarSystem, EveType

from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag
from app_utils.views import bootstrap_label_html

from .. import __title__
from ..app_settings import STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS
from ..constants import EveCategoryId, EveGroupId, EveTypeId
from ..core import starbases
from ..helpers.general import datetime_almost_equal, hours_until_deadline
from ..managers import StructureManager, StructureTagManager
from .eveuniverse import EveSpaceType

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class StructureTag(models.Model):
    """Tag for organizing structures."""

    # special tags
    NAME_SOV_TAG = gettext_noop("sov")
    NAME_HIGHSEC_TAG = gettext_noop("highsec")
    NAME_LOWSEC_TAG = gettext_noop("lowsec")
    NAME_NULLSEC_TAG = gettext_noop("nullsec")
    NAME_W_SPACE_TAG = gettext_noop("w_space")

    class Style(models.TextChoices):
        GREY = "default", _("grey")
        DARK_BLUE = "primary", _("dark blue")
        GREEN = "success", _("green")
        LIGHT_BLUE = "info", _("light blue")
        ORANGE = "warning", _("orange")
        RED = "danger", _("red")

    SPACE_TYPE_MAP = {
        EveSpaceType.HIGHSEC: {"name": NAME_HIGHSEC_TAG, "style": Style.GREEN},
        EveSpaceType.LOWSEC: {"name": NAME_LOWSEC_TAG, "style": Style.ORANGE},
        EveSpaceType.NULLSEC: {"name": NAME_NULLSEC_TAG, "style": Style.RED},
        EveSpaceType.W_SPACE: {"name": NAME_W_SPACE_TAG, "style": Style.LIGHT_BLUE},
    }

    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("name"),
        help_text=_("name of the tag - must be unique"),
    )
    description = models.TextField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("description"),
        help_text=_("description for this tag"),
    )
    style = models.CharField(
        max_length=16,
        choices=Style.choices,
        default="default",
        blank=True,
        verbose_name=_("style"),
        help_text=_("color style of tag"),
    )
    order = models.PositiveIntegerField(
        default=100,
        blank=True,
        validators=[MinValueValidator(100)],
        verbose_name=_("order"),
        help_text=_(
            "number defining the order tags are shown. "
            "custom tags can not have an order below 100"
        ),
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("is default"),
        help_text=_(
            "if true this custom tag will automatically be added to new structures"
        ),
    )
    is_user_managed = models.BooleanField(
        default=True,
        verbose_name=_("is user managed"),
        help_text=_(
            "if False this tag is created and managed by the system "
            "and can not be modified by users"
        ),
    )

    objects = StructureTagManager()

    class Meta:
        verbose_name = _("structure tag")
        verbose_name_plural = _("structure tags")
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name

    def __repr__(self):
        return "{}(name='{}')".format(self.__class__.__name__, self.name)

    @property
    def html(self) -> str:
        if self.is_user_managed:
            name = escape(self.name)
        else:
            name = _(self.name)
        return bootstrap_label_html(name, self.style)

    @classmethod
    def sorted(cls, tags: list, reverse: bool = False) -> list:
        """returns a sorted copy of the provided list of tags"""
        return sorted(tags, key=lambda x: x.name.lower(), reverse=reverse)


class Structure(models.Model):
    """A structure in Eve Online."""

    # Threshold in seconds when two fuel expiry dates will be judged as different
    FUEL_DATES_EQUAL_THRESHOLD_UPWELL = 1800
    FUEL_DATES_EQUAL_THRESHOLD_STARBASE = 7200  # high fluctuation due to estimating

    class State(models.IntegerChoices):
        """State of a structure"""

        # states Upwell structures
        ANCHOR_VULNERABLE = 1, _("anchor vulnerable")
        ANCHORING = 2, _("anchoring")
        ARMOR_REINFORCE = 3, _("armor reinforce")
        ARMOR_VULNERABLE = 4, _("armor vulnerable")
        DEPLOY_VULNERABLE = 5, _("deploy vulnerable")
        FITTING_INVULNERABLE = 6, _("fitting invulnerable")
        HULL_REINFORCE = 7, _("hull reinforce")
        HULL_VULNERABLE = 8, _("hull vulnerable")
        ONLINE_DEPRECATED = 9, _("online deprecated")
        ONLINING_VULNERABLE = 10, _("onlining vulnerable")
        SHIELD_VULNERABLE = 11, _("shield vulnerable")
        UNANCHORED = 12, _("unanchored")
        # starbases
        POS_OFFLINE = 21, _("offline")
        POS_ONLINE = 22, _("online")
        POS_ONLINING = 23, _("onlining")
        POS_REINFORCED = 24, _("reinforced")
        POS_UNANCHORING = 25, _("unanchoring ")
        # other
        NA = 0, _("N/A")
        UNKNOWN = 13, _("unknown")

        @classmethod
        def from_esi_name(cls, esi_state_name: str) -> "Structure.State":
            """returns matching state for esi state name of Upwell structures"""
            STATES_ESI_MAP = {
                "anchor_vulnerable": cls.ANCHOR_VULNERABLE,
                "anchoring": cls.ANCHORING,
                "armor_reinforce": cls.ARMOR_REINFORCE,
                "armor_vulnerable": cls.ARMOR_VULNERABLE,
                "deploy_vulnerable": cls.DEPLOY_VULNERABLE,
                "fitting_invulnerable": cls.FITTING_INVULNERABLE,
                "hull_reinforce": cls.HULL_REINFORCE,
                "hull_vulnerable": cls.HULL_VULNERABLE,
                "online_deprecated": cls.ONLINE_DEPRECATED,
                "onlining_vulnerable": cls.ONLINING_VULNERABLE,
                "shield_vulnerable": cls.SHIELD_VULNERABLE,
                "unanchored": cls.UNANCHORED,
                "offline": cls.POS_OFFLINE,
                "online": cls.POS_ONLINE,
                "onlining": cls.POS_ONLINING,
                "reinforced": cls.POS_REINFORCED,
                "unanchoring ": cls.POS_UNANCHORING,
            }
            return (
                STATES_ESI_MAP[esi_state_name]
                if esi_state_name in STATES_ESI_MAP
                else cls.UNKNOWN
            )

    class PowerMode(models.TextChoices):
        FULL_POWER = "FU", _("Full Power")
        LOW_POWER = "LO", _("Low Power")
        ABANDONED = "AB", _("Abandoned")
        LOW_ABANDONED = "LA", _("Abandoned?")
        UNKNOWN = "UN", _("Unknown")

    id = models.BigIntegerField(
        primary_key=True,
        verbose_name=_("id"),
        help_text=_("The Item ID of the structure"),
    )

    created_at = models.DateTimeField(
        default=now,
        verbose_name=_("created at"),
        help_text=_("date this structure was received from ESI for the first time"),
    )
    eve_moon = models.ForeignKey(
        EveMoon,
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True,
        related_name="+",
        verbose_name=_("moon"),
        help_text=_("Moon next to this structure - if any"),
    )
    eve_planet = models.ForeignKey(
        EvePlanet,
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True,
        related_name="+",
        verbose_name=_("planet"),
        help_text=_("Planet next to this structure - if any"),
    )
    eve_solar_system = models.ForeignKey(
        EveSolarSystem,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("solar system"),
        help_text=_("Solar System the structure is located"),
    )
    eve_type = models.ForeignKey(
        EveType,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("type"),
        help_text=_("Type of the structure"),
    )
    fuel_expires_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("fuel expires at"),
        help_text=_("Date on which the structure will run out of fuel"),
    )
    has_fitting = models.BooleanField(
        null=True,
        default=None,
        blank=True,
        db_index=True,
        verbose_name=_("has fitting"),
        help_text=_("bool indicating if the structure has a fitting"),
    )
    has_core = models.BooleanField(
        null=True,
        default=None,
        blank=True,
        db_index=True,
        verbose_name=_("has core"),
        help_text=_("bool indicating if the structure has a quantum core"),
    )
    last_online_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("last online at"),
        help_text=_("date this structure had any of it's services online"),
    )
    last_updated_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("last updated at"),
        help_text=_("date this structure was last updated from the EVE server"),
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_("name"),
        help_text=_("The full name of the structure"),
    )
    next_reinforce_hour = models.PositiveIntegerField(
        null=True,
        default=None,
        blank=True,
        validators=[MaxValueValidator(23)],
        verbose_name=_("next reinforce hour"),
        help_text=_(
            "The requested change to reinforce_hour that will take "
            "effect at the time shown by next_reinforce_apply"
        ),
    )
    next_reinforce_apply = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("next reinforce apply"),
        help_text=_(
            "The requested change to reinforce_hour that will take "
            "effect at the time shown by next_reinforce_apply"
        ),
    )
    owner = models.ForeignKey(
        "Owner",
        on_delete=models.CASCADE,
        related_name="structures",
        verbose_name=_("owner"),
        help_text=_("Corporation that owns the structure"),
    )
    reinforce_hour = models.PositiveIntegerField(
        validators=[MaxValueValidator(23)],
        null=True,
        default=None,
        blank=True,
        verbose_name=_("reinforce hour"),
        help_text=_(
            "The average hour of day that determines the time +/- some hours "
            "when the structure will randomly exit its reinforcement periods "
            "and become vulnerable to attack against its armor and/or hull. "
        ),
    )
    position_x = models.FloatField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("position x"),
        help_text=_("x position in the solar system"),
    )
    position_y = models.FloatField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("position y"),
        help_text=_("y position in the solar system"),
    )
    position_z = models.FloatField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("position z"),
        help_text=_("z position in the solar system"),
    )
    state = models.IntegerField(
        choices=State.choices,
        default=State.UNKNOWN,
        blank=True,
        verbose_name=_("state"),
        help_text=_("Current state of the structure"),
    )
    state_timer_end = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("state timer end"),
        help_text=_("Date at which the structure entered it's current state"),
    )
    state_timer_start = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("state timer start"),
        help_text=_("Date at which the structure will move to it's next state"),
    )
    tags = models.ManyToManyField(
        StructureTag,
        default=None,
        blank=True,
        related_name="structures",
        verbose_name=_("tags"),
        help_text=_("List of tags for this structure. "),
    )
    unanchors_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("unanchors at"),
        help_text=_("Date at which the structure will unanchor"),
    )
    webhooks = models.ManyToManyField(
        "Webhook",
        default=None,
        blank=True,
        related_name="structures",
        verbose_name=_("webhooks"),
        help_text=_(
            "Webhooks for sending notifications to. "
            "If any webhook is enabled, these will be used instead of the webhooks "
            "defined for the respective owner. "
            "If no webhook is enabled the owner's setting will be used. "
        ),
    )

    objects = StructureManager()

    class Meta:
        verbose_name = _("structure")
        verbose_name_plural = _("structures")

    def __str__(self) -> str:
        if self.is_upwell_structure:
            try:
                location_name = self.eve_solar_system.name
            except AttributeError:
                location_name = "?"
        else:
            location_name = self.location_name
        return f"{location_name} - {self.name}" if self.name else str(location_name)

    def __repr__(self) -> str:
        try:
            eve_solar_system_name = self.eve_solar_system.name
        except AttributeError:
            eve_solar_system_name = ""
        try:
            eve_planet_name = self.eve_planet.name
        except AttributeError:
            eve_planet_name = ""
        try:
            eve_moon_name = self.eve_moon.name
        except AttributeError:
            eve_moon_name = ""
        return (
            f"{self.__class__.__name__}(id={self.id}, "
            f"eve_solar_system='{eve_solar_system_name}', "
            f"eve_planet='{eve_planet_name}', "
            f"eve_moon='{eve_moon_name}', "
            f"name='{self.name}')"
        )

    def save(self, *args, **kwargs):
        is_new = self._state.adding is True
        super().save(*args, **kwargs)
        if is_new:
            for tag in StructureTag.objects.filter(is_default=True):
                self.tags.add(tag)
        # make sure related objects are saved whenever structure is saved
        self.update_generated_tags()

    @property
    def is_jump_gate(self) -> bool:
        return self.eve_type_id == EveTypeId.JUMP_GATE

    @property
    def is_poco(self) -> bool:
        return self.eve_type_id == EveTypeId.CUSTOMS_OFFICE

    @cached_property
    def is_starbase(self) -> bool:
        return starbases.is_starbase(self.eve_type)

    @cached_property
    def is_upwell_structure(self) -> bool:
        return self.eve_type.eve_group.eve_category_id == EveCategoryId.STRUCTURE

    @property
    def is_full_power(self) -> Optional[bool]:
        """return True if structure is full power, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        return power_mode == self.PowerMode.FULL_POWER

    @property
    def is_low_power(self) -> Optional[bool]:
        """return True if structure is low power, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        return power_mode == self.PowerMode.LOW_POWER

    @property
    def is_abandoned(self) -> Optional[bool]:
        """return True if structure is abandoned, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        return power_mode == self.PowerMode.ABANDONED

    @property
    def is_maybe_abandoned(self) -> Optional[bool]:
        """return True if structure is maybe abandoned, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        return power_mode == self.PowerMode.LOW_ABANDONED

    @property
    def power_mode(self) -> Optional["PowerMode"]:
        """returns the calculated power mode of this structure, e.g. low power
        returns None for non upwell structures
        """
        if not self.is_upwell_structure:
            return None
        if self.fuel_expires_at and self.fuel_expires_at > now():
            return self.PowerMode.FULL_POWER
        elif self.last_online_at:
            if self.last_online_at >= now() - dt.timedelta(days=7):
                return self.PowerMode.LOW_POWER
            else:
                return self.PowerMode.ABANDONED
        elif self.state in {self.State.ANCHORING, self.State.ANCHOR_VULNERABLE}:
            return self.PowerMode.LOW_POWER
        return self.PowerMode.LOW_ABANDONED

    @property
    def is_reinforced(self) -> bool:
        return self.state in [
            self.State.ARMOR_REINFORCE,
            self.State.HULL_REINFORCE,
            self.State.ANCHOR_VULNERABLE,
            self.State.HULL_VULNERABLE,
            self.State.POS_REINFORCED,
        ]

    @property
    def is_burning_fuel(self) -> bool:
        """True when this structure is currently burning fuel, else False."""
        if self.is_upwell_structure and self.is_full_power:
            return True
        if self.is_starbase and self.state in [
            self.State.POS_ONLINE,
            self.State.POS_REINFORCED,
            self.State.POS_UNANCHORING,
        ]:
            return True
        return False

    @property
    def has_position(self) -> bool:
        """Evaluate if this structure has a position."""
        return (
            self.position_x is not None
            and self.position_y is not None
            and self.position_z is not None
        )

    @cached_property
    def owner_has_sov(self) -> bool:
        return self.owner.has_sov(self.eve_solar_system)

    @cached_property
    def location_name(self) -> str:
        """Name of this structures's location."""
        try:
            return self.eve_moon.name
        except AttributeError:
            pass
        try:
            return self.eve_planet.name
        except AttributeError:
            pass
        try:
            return self.eve_solar_system.name
        except AttributeError:
            return "?"

    def distance_to_object(self, x: float, y: float, z: float) -> float:
        """Distance to object with given coordinates (within same solar system)."""
        if not self.has_position:
            raise ValueError(
                f"{self}: Can not calculate distance from a structure without a position"
            )
        return math.sqrt(
            pow(x - self.position_x, 2)  # type: ignore
            + pow(y - self.position_y, 2)  # type: ignore
            + pow(z - self.position_z, 2)  # type: ignore
        )

    @cached_property
    def structure_fuel_quantity(self) -> Optional[int]:
        """Current quantity of fuel blocks in units used as fuel."""
        return self.items.filter(
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
            eve_type__eve_group_id=EveGroupId.FUEL_BLOCK,
        ).aggregate(Sum("quantity"))["quantity__sum"]

    def jump_fuel_quantity(self) -> Optional[int]:
        """Current quantity of liquid ozone in units used as fuel."""
        return self.items.filter(
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
            eve_type_id=EveTypeId.LIQUID_OZONE,
        ).aggregate(Sum("quantity"))["quantity__sum"]

    def structure_fuel_usage(self) -> Optional[int]:
        """Needed fuel blocks per day."""
        if not self.fuel_expires_at:
            return None
        fuel_quantity = self.structure_fuel_quantity
        if not fuel_quantity:
            return None
        assets_last_updated_at = self.items.filter(
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
            eve_type__eve_group_id=EveGroupId.FUEL_BLOCK,
        ).aggregate(Min("last_updated_at"))["last_updated_at__min"]
        if not assets_last_updated_at:
            return None
        try:
            return math.ceil(
                fuel_quantity
                / hours_until_deadline(self.fuel_expires_at, assets_last_updated_at)
                * 24
            )
        except ZeroDivisionError:
            return None

    @property
    def hours_fuel_expires(self) -> Optional[float]:
        """Hours until fuel expires."""
        if self.fuel_expires_at:
            return hours_until_deadline(self.fuel_expires_at)
        return None

    def is_fuel_expiry_date_different(self, other: "Structure") -> bool:
        """True when fuel expiry date from other structure is different.

        Will compare using threshold setting.
        """
        change_threshold = (
            self.FUEL_DATES_EQUAL_THRESHOLD_UPWELL
            if self.is_upwell_structure
            else self.FUEL_DATES_EQUAL_THRESHOLD_STARBASE
        )
        return not other.fuel_expires_at or not datetime_almost_equal(
            other.fuel_expires_at, self.fuel_expires_at, change_threshold
        )

    def handle_fuel_notifications(self, old_instance: "Structure"):
        """Remove fuel notifications if fuel levels have changed
        and sent refueled notifications if structure has been refueled.
        """
        if self.fuel_expires_at and old_instance and self.pk == old_instance.pk:
            logger_tag = "%s: Fuel notifications" % self
            if self.fuel_expires_at != old_instance.fuel_expires_at:
                logger.info(
                    "%s: Fuel expiry dates changed: old|current|delta: %s|%s|%s",
                    logger_tag,
                    old_instance.fuel_expires_at.isoformat()
                    if old_instance.fuel_expires_at
                    else None,
                    self.fuel_expires_at.isoformat(),
                    int(
                        abs(
                            (
                                self.fuel_expires_at - old_instance.fuel_expires_at
                            ).total_seconds()
                        )
                    )
                    if old_instance.fuel_expires_at
                    else "-",
                )
            if (
                self.is_burning_fuel
                and old_instance.is_burning_fuel
                and self.is_fuel_expiry_date_different(old_instance)
            ):
                logger.info(
                    "%s: Structure fuel level has changed. "
                    "Therefore removing current fuel notifications.",
                    logger_tag,
                )
                self.structure_fuel_alerts.all().delete()
                if STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS and (
                    not old_instance.fuel_expires_at
                    or old_instance.fuel_expires_at < self.fuel_expires_at
                ):
                    logger.info("%s: Structure has been refueled.", logger_tag)
                    self._send_refueled_notification()

    def _send_refueled_notification(self):
        """Send a refueled notifications for this structure."""
        from .notifications import Notification, NotificationType

        notif_type = (
            NotificationType.TOWER_REFUELED_EXTRA
            if self.is_starbase
            else NotificationType.STRUCTURE_REFUELED_EXTRA
        )
        notif = Notification.create_from_structure(
            structure=self, notif_type=notif_type
        )
        notif.send_to_configured_webhooks()

    def reevaluate_jump_fuel_alerts(self):
        """Remove outdated fuel alerts based on potentially changed fuel levels."""
        jump_fuel_quantity = self.jump_fuel_quantity()
        if jump_fuel_quantity:
            self.jump_fuel_alerts.filter(
                config__threshold__lt=jump_fuel_quantity
            ).delete()

    def get_power_mode_display(self) -> str:
        return self.PowerMode(self.power_mode).label if self.power_mode else ""

    def update_generated_tags(self, recreate_tags=False):
        """updates all generated tags for this structure

        recreate_tags: when set true all tags will be re-created,
        otherwise just re-added if they are missing
        """
        method_name = (
            "update_or_create_for_space_type"
            if recreate_tags
            else "get_or_create_for_space_type"
        )

        space_type_tag, _ = getattr(StructureTag.objects, method_name)(
            self.eve_solar_system
        )

        self.tags.add(space_type_tag)
        if self.owner_has_sov:
            method_name = (
                "update_or_create_for_sov" if recreate_tags else "get_or_create_for_sov"
            )

            sov_tag, _ = getattr(StructureTag.objects, method_name)()
            self.tags.add(sov_tag)

    def update_items(self, structure_items: List["StructureItem"]):
        """Update items for this structure."""
        with transaction.atomic():
            self.items.all().delete()
            if structure_items:
                # remove items that have been transferred between structures
                item_ids = {item.id for item in structure_items}
                StructureItem.objects.filter(id__in=item_ids).delete()
                # create new items
                self.items.bulk_create(structure_items)

    @classmethod
    def extract_name_from_esi_response(cls, esi_name):
        """extracts the structure's name from the name in an ESI response"""
        matches = re.search(r"^\S+ - (.+)", esi_name)
        return matches.group(1) if matches else esi_name


class StructureItem(models.Model):
    """An item in a structure"""

    class LocationFlag(models.TextChoices):
        """Frequently used location flags.
        This are not all, so can not be used as choices.
        """

        AUTOFIT = "AutoFit"
        CARGO = "Cargo"
        CORP_DELIVERIES = "CorpDeliveries"
        FIGHTER_BAY = "FighterBay"
        OFFICE_FOLDER = "OfficeFolder"
        QUANTUM_CORE_ROOM = "QuantumCoreRoom"
        SECONDARY_STORAGE = "SecondaryStorage"
        STRUCTURE_FUEL = "StructureFuel"

    id = models.BigIntegerField(
        primary_key=True, verbose_name=_("id"), help_text=_("The Eve item ID")
    )
    structure = models.ForeignKey(
        Structure,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("structure"),
        help_text=_("Structure this item is located in"),
    )

    eve_type = models.ForeignKey(
        EveType,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("type"),
        help_text=_("type of the item"),
    )
    is_singleton = models.BooleanField(verbose_name=_("is singleton"))
    last_updated_at = models.DateTimeField(
        auto_now=True, verbose_name=_("last updated at")
    )
    location_flag = models.CharField(max_length=255, verbose_name=_("location flag"))
    quantity = models.IntegerField(verbose_name=_("quantity"))

    class Meta:
        verbose_name = _("structure item")
        verbose_name_plural = _("structure items")

    def __str__(self) -> str:
        return str(self.eve_type.name)

    def __repr__(self):
        return "{}(pk={}, structure=<{}>, eve_type=<{}>)".format(
            self.__class__.__name__, self.pk, self.structure, self.eve_type
        )

    @classmethod
    def from_esi_asset(cls, item: dict, structure: "Structure") -> "StructureItem":
        """Create new object from ESI asset item."""
        eve_type, _ = EveType.objects.get_or_create_esi(id=item["type_id"])
        return StructureItem(
            id=item["item_id"],
            structure=structure,
            eve_type=eve_type,
            is_singleton=item["is_singleton"],
            location_flag=item["location_flag"],
            quantity=item["quantity"],
        )


class StructureService(models.Model):
    """Service of a Structure."""

    class State(models.IntegerChoices):
        OFFLINE = 1, _("offline")
        ONLINE = 2, _("online")

        @classmethod
        def from_esi_name(cls, esi_state_name: str) -> "StructureService.State":
            """returns matching state for given ESI state name"""
            STATES_ESI_MAP = {"offline": cls.OFFLINE, "online": cls.ONLINE}
            return (
                STATES_ESI_MAP[esi_state_name]
                if esi_state_name in STATES_ESI_MAP
                else cls.OFFLINE
            )

    structure = models.ForeignKey(
        Structure,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name=_("structure"),
        help_text=_("Structure this service is installed to"),
    )
    name = models.CharField(
        max_length=100, verbose_name=_("name"), help_text=_("Name of the service")
    )

    state = models.IntegerField(
        choices=State.choices,
        verbose_name=_("state"),
        help_text=_("Current state of this service"),
    )

    class Meta:
        verbose_name = _("structure service")
        verbose_name_plural = _("structure services")
        unique_together = (("structure", "name"),)

    def __str__(self):
        return "{} - {}".format(str(self.structure), self.name)

    def __repr__(self):
        return "{}(structure_id={}, name='{}')".format(
            self.__class__.__name__, self.structure.id, self.name
        )


class PocoDetails(models.Model):
    """Additional information about a POCO."""

    class StandingLevel(models.IntegerChoices):
        NONE = -99, _("none")
        TERRIBLE = -10, _("terrible")
        BAD = -5, _("bad")
        NEUTRAL = 0, _("neutral")
        GOOD = 5, _("good")
        EXCELLENT = 10, _("excellent")

        @classmethod
        def from_esi(cls, value) -> "PocoDetails.StandingLevel":
            """Return match from ESI value or NONE"""
            my_map = {
                "bad": cls.BAD,
                "excellent": cls.EXCELLENT,
                "good": cls.GOOD,
                "neutral": cls.NEUTRAL,
                "terrible": cls.TERRIBLE,
            }
            try:
                return my_map[value]
            except KeyError:
                return cls.NONE

    alliance_tax_rate = models.FloatField(null=True, default=None)
    allow_access_with_standings = models.BooleanField()
    allow_alliance_access = models.BooleanField()
    bad_standing_tax_rate = models.FloatField(null=True, default=None)
    corporation_tax_rate = models.FloatField(null=True, default=None)
    excellent_standing_tax_rate = models.FloatField(null=True, default=None)
    good_standing_tax_rate = models.FloatField(null=True, default=None)
    neutral_standing_tax_rate = models.FloatField(null=True, default=None)
    reinforce_exit_end = models.PositiveIntegerField()
    reinforce_exit_start = models.PositiveIntegerField()
    standing_level = models.IntegerField(
        choices=StandingLevel.choices, default=StandingLevel.NONE
    )
    structure = models.OneToOneField(
        Structure, on_delete=models.CASCADE, related_name="poco_details"
    )
    terrible_standing_tax_rate = models.FloatField(null=True, default=None)

    def __str__(self):
        return f"{self.structure}"

    @property
    def reinforce_exit_end_str(self) -> str:
        return f"{self.reinforce_exit_end}:00"

    @property
    def reinforce_exit_start_str(self) -> str:
        return f"{self.reinforce_exit_start}:00"

    def tax_for_character(self, character: EveCharacter) -> Optional[float]:
        """Return the effective tax for this character or None if unknown."""
        owner_corporation = self.structure.owner.corporation
        if character.corporation_id == owner_corporation.corporation_id:
            return self.corporation_tax_rate
        if (
            owner_corporation.alliance
            and owner_corporation.alliance.alliance_id == character.alliance_id
        ):
            return self.alliance_tax_rate
        else:
            return None

    def has_character_access(self, character: EveCharacter) -> Optional[bool]:
        """Return Tru if this has access else False."""
        owner_corporation = self.structure.owner.corporation
        if character.corporation_id == owner_corporation.corporation_id:
            return True
        if (
            owner_corporation.alliance
            and owner_corporation.alliance.alliance_id == character.alliance_id
        ):
            return self.allow_alliance_access
        else:
            return None

    def standing_level_access_map(self) -> dict:
        """Return map of access per standing level with standing level names as key."""
        names_map = {
            self.StandingLevel.NONE: "NONE",
            self.StandingLevel.TERRIBLE: "TERRIBLE",
            self.StandingLevel.BAD: "BAD",
            self.StandingLevel.NEUTRAL: "NEUTRAL",
            self.StandingLevel.GOOD: "GOOD",
            self.StandingLevel.EXCELLENT: "EXCELLENT",
        }
        return {
            names_map[self.StandingLevel(level)]: (
                self.allow_access_with_standings and level >= self.standing_level
            )
            for level in self.StandingLevel.values
        }


class StarbaseDetail(models.Model):
    """Additional information about a starbase."""

    class Role(models.TextChoices):
        ALLIANCE_MEMBER = "AL", _("alliance member")
        CONFIG_STARBASE_EQUIPMENT_ROLE = "CE", _("config starbase equipment role")
        CORPORATION_MEMBER = "CO", _("corporation member")
        STARBASE_FUEL_TECHNICIAN_ROLE = "FT", _("starbase fuel technician role")

        @classmethod
        def from_esi(cls, name) -> "StarbaseDetail.Role":
            my_map = {
                "alliance_member": cls.ALLIANCE_MEMBER,
                "config_starbase_equipment_role": cls.CONFIG_STARBASE_EQUIPMENT_ROLE,
                "corporation_member": cls.CORPORATION_MEMBER,
                "starbase_fuel_technician_role": cls.STARBASE_FUEL_TECHNICIAN_ROLE,
            }
            return my_map[name]

    allow_alliance_members = models.BooleanField()
    allow_corporation_members = models.BooleanField()
    anchor_role = models.CharField(max_length=2, choices=Role.choices)
    attack_if_at_war = models.BooleanField()
    attack_if_other_security_status_dropping = models.BooleanField()
    attack_security_status_threshold = models.FloatField(default=None, null=True)
    attack_standing_threshold = models.FloatField(default=None, null=True)
    fuel_bay_take_role = models.CharField(max_length=2, choices=Role.choices)
    fuel_bay_view_role = models.CharField(max_length=2, choices=Role.choices)
    last_modified_at = models.DateTimeField(
        help_text="When data was modified on the server."
    )
    offline_role = models.CharField(max_length=2, choices=Role.choices)
    online_role = models.CharField(max_length=2, choices=Role.choices)
    structure = models.OneToOneField(
        Structure, on_delete=models.CASCADE, related_name="starbase_detail"
    )
    unanchor_role = models.CharField(max_length=2, choices=Role.choices)
    use_alliance_standings = models.BooleanField()

    def __str__(self) -> str:
        return str(self.structure)

    def calc_fuel_expires(self) -> Optional[dt.datetime]:
        """Estimate when fuel will expire for this starbase.

        Estimate will vary due to server caching of remaining fuel blocks.
        """
        if self.structure.state is Structure.State.POS_OFFLINE:
            return None
        fuel = self.fuels.filter(eve_type__eve_group_id=EveGroupId.FUEL_BLOCK).first()
        if not fuel:
            return None
        seconds = starbases.fuel_duration(
            starbase_type=self.structure.eve_type,
            fuel_quantity=fuel.quantity,
            has_sov=self.structure.owner.has_sov(self.structure.eve_solar_system),
        )
        return self.last_modified_at + dt.timedelta(seconds=seconds)


class StarbaseDetailFuel(models.Model):
    """Fuel for a starbase detail."""

    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE, related_name="+")
    detail = models.ForeignKey(
        StarbaseDetail, on_delete=models.CASCADE, related_name="fuels"
    )
    quantity = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["detail", "eve_type"], name="functional_pk_starbasedetailfuel"
            )
        ]

    def __str__(self) -> str:
        return f"{self.detail}-{self.eve_type}"
