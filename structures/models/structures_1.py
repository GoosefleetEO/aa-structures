"""Structure related models for Structures."""

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

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag
from app_utils.views import bootstrap_label_html

from structures import __title__
from structures.app_settings import STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS
from structures.constants import EveCategoryId, EveGroupId, EveTypeId
from structures.core import starbases
from structures.helpers import datetime_almost_equal, hours_until_deadline
from structures.managers import StructureManager, StructureTagManager

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
        """A boostrap like style."""

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
        help_text=_("Name of the tag, which must be unique"),
    )
    description = models.TextField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("description"),
        help_text=_("Description for this tag"),
    )
    style = models.CharField(
        max_length=16,
        choices=Style.choices,
        default="default",
        blank=True,
        verbose_name=_("style"),
        help_text=_("Color style of tag"),
    )
    order = models.PositiveIntegerField(
        default=100,
        blank=True,
        validators=[MinValueValidator(100)],
        verbose_name=_("order"),
        help_text=_(
            "Number defining the order tags are shown. "
            "custom tags can not have an order below 100"
        ),
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("is default"),
        help_text=_(
            "When enabled this custom tag will automatically be added to new structures"
        ),
    )
    is_user_managed = models.BooleanField(
        default=True,
        verbose_name=_("is user managed"),
        help_text=_(
            "When disabled this tag is created and managed by the system "
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
        return f"{self.__class__.__name__}(name='{self.name}')"

    @property
    def html(self) -> str:
        """Return HTML for this tag."""
        if self.is_user_managed:
            name = escape(self.name)
        else:
            name = _(self.name)
        return bootstrap_label_html(name, self.style)

    @classmethod
    def sorted(cls, tags: list, reverse: bool = False) -> list:
        """returns a sorted copy of the provided list of tags"""
        return sorted(tags, key=lambda x: x.name.lower(), reverse=reverse)


class Structure(models.Model):  # pylint: disable = too-many-public-methods
    """A structure in Eve Online."""

    FUEL_DATES_EQUAL_THRESHOLD_UPWELL = 1800
    """Threshold in seconds when two fuel expiry dates will be judged as different."""

    FUEL_DATES_EQUAL_THRESHOLD_STARBASE = 7200
    """high fluctuation due to estimating."""

    class State(models.IntegerChoices):
        """A state of a structure."""

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
            states_esi_map = {
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
                states_esi_map[esi_state_name]
                if esi_state_name in states_esi_map
                else cls.UNKNOWN
            )

    class PowerMode(models.TextChoices):
        """A power mode of a structure."""

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
        help_text=_("Date this structure was received from ESI for the first time"),
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
        help_text="Whether the structure has a fitting",
    )
    has_core = models.BooleanField(
        null=True,
        default=None,
        blank=True,
        db_index=True,
        verbose_name=_("has core"),
        help_text="Whether the structure has a quantum core",
    )
    last_online_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("last online at"),
        help_text=_("Date this structure had any of it's services online"),
    )
    last_updated_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("last updated at"),
        help_text=_("Date this structure was last updated from the EVE server"),
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
        help_text=_("X coordinate of position in the solar system"),
    )
    position_y = models.FloatField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("position y"),
        help_text=_("Y coordinate of position in the solar system"),
    )
    position_z = models.FloatField(
        null=True,
        default=None,
        blank=True,
        verbose_name=_("position z"),
        help_text=_("Z coordinate of position in the solar system"),
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
        """Return True if this structure is a jump gate, else False."""
        return self.eve_type_id == EveTypeId.JUMP_GATE

    @property
    def is_poco(self) -> bool:
        """Return True if this structure is a customs office, else False."""
        return self.eve_type_id == EveTypeId.CUSTOMS_OFFICE

    @cached_property
    def is_starbase(self) -> bool:
        """Return True if this structure is a starbase, else False."""
        return starbases.is_starbase(self.eve_type)

    @cached_property
    def is_upwell_structure(self) -> bool:
        """Return True if this structure is an upwell structure, else False."""
        return self.eve_type.eve_group.eve_category_id == EveCategoryId.STRUCTURE

    @property
    def is_full_power(self) -> Optional[bool]:
        """Return True if structure is full power, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None

        return power_mode == self.PowerMode.FULL_POWER

    @property
    def is_low_power(self) -> Optional[bool]:
        """Return True if structure is low power, False if not.

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

        if self.last_online_at:
            if self.last_online_at >= now() - dt.timedelta(days=7):
                return self.PowerMode.LOW_POWER
            return self.PowerMode.ABANDONED

        if self.state in {self.State.ANCHORING, self.State.ANCHOR_VULNERABLE}:
            return self.PowerMode.LOW_POWER

        return self.PowerMode.LOW_ABANDONED

    @property
    def is_reinforced(self) -> bool:
        """Return True if this structure is reinforced, else False."""
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
        """Return True if the owner of this structure has sov in this solar system,
        else False.
        """
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
            logger_tag = f"{self}: Fuel notifications"
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
        """Return this structure's power mode as label for display.
        Or return an empty string for structures that have no power mode.
        """
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
        help_text="Type of the item",
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
        return (
            f"{self.__class__.__name__}("
            f"pk={self.pk}, structure=<{self.structure}>, eve_type=<{self.eve_type}>"
            ")"
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
