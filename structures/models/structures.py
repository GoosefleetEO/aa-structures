"""Structure related models"""
import re
from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.html import escape
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_noop

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag
from app_utils.views import bootstrap_label_html

from .. import __title__
from ..managers import StructureManager, StructureTagManager
from .eveuniverse import EsiNameLocalization, EveSolarSystem

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class StructureTag(models.Model):
    """tag for organizing structures"""

    # special tags
    NAME_SOV_TAG = gettext_noop("sov")
    NAME_HIGHSEC_TAG = gettext_noop("highsec")
    NAME_LOWSEC_TAG = gettext_noop("lowsec")
    NAME_NULLSEC_TAG = gettext_noop("nullsec")
    NAME_W_SPACE_TAG = gettext_noop("w_space")

    class Style(models.TextChoices):
        GREY = "default", "grey"
        DARK_BLUE = "primary", "dark blue"
        GREEN = "success", "green"
        LIGHT_BLUE = "info", "light blue"
        ORANGE = "warning", "orange"
        RED = "danger", "red"
        # TODO: add localization

    SPACE_TYPE_MAP = {
        EveSolarSystem.TYPE_HIGHSEC: {"name": NAME_HIGHSEC_TAG, "style": Style.GREEN},
        EveSolarSystem.TYPE_LOWSEC: {"name": NAME_LOWSEC_TAG, "style": Style.ORANGE},
        EveSolarSystem.TYPE_NULLSEC: {"name": NAME_NULLSEC_TAG, "style": Style.RED},
        EveSolarSystem.TYPE_W_SPACE: {
            "name": NAME_W_SPACE_TAG,
            "style": Style.LIGHT_BLUE,
        },
    }

    name = models.CharField(
        max_length=255, unique=True, help_text="name of the tag - must be unique"
    )
    description = models.TextField(
        null=True, default=None, blank=True, help_text="description for this tag"
    )
    style = models.CharField(
        max_length=16,
        choices=Style.choices,
        default="default",
        blank=True,
        help_text="color style of tag",
    )
    order = models.PositiveIntegerField(
        default=100,
        blank=True,
        validators=[MinValueValidator(100)],
        help_text=(
            "number defining the order tags are shown. "
            "custom tags can not have an order below 100"
        ),
    )
    is_default = models.BooleanField(
        default=False,
        help_text=(
            "if true this custom tag will automatically be added " "to new structures"
        ),
    )
    is_user_managed = models.BooleanField(
        default=True,
        help_text=(
            "if False this tag is created and managed by the system "
            "and can not be modified by users"
        ),
    )

    objects = StructureTagManager()

    def __str__(self) -> str:
        return self.name

    def __repr__(self):
        return "{}(name='{}')".format(self.__class__.__name__, self.name)

    class Meta:
        ordering = ordering = ["order", "name"]

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
    """structure of a corporation"""

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
        primary_key=True, help_text="The Item ID of the structure"
    )
    owner = models.ForeignKey(
        "Owner",
        on_delete=models.CASCADE,
        related_name="structures",
        help_text="Corporation that owns the structure",
    )
    eve_type = models.ForeignKey(
        "EveType", on_delete=models.CASCADE, help_text="type of the structure"
    )
    name = models.CharField(max_length=255, help_text="The full name of the structure")
    eve_solar_system = models.ForeignKey("EveSolarSystem", on_delete=models.CASCADE)
    eve_planet = models.ForeignKey(
        "EvePlanet",
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True,
        help_text="Planet next to this structure - if any",
    )
    eve_moon = models.ForeignKey(
        "EveMoon",
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True,
        help_text="Moon next to this structure - if any",
    )
    position_x = models.FloatField(
        null=True, default=None, blank=True, help_text="x position in the solar system"
    )
    position_y = models.FloatField(
        null=True, default=None, blank=True, help_text="y position in the solar system"
    )
    position_z = models.FloatField(
        null=True, default=None, blank=True, help_text="z position in the solar system"
    )
    fuel_expires_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="Date on which the structure will run out of fuel",
    )
    next_reinforce_hour = models.PositiveIntegerField(
        null=True,
        default=None,
        blank=True,
        validators=[MaxValueValidator(23)],
        help_text=(
            "The requested change to reinforce_hour that will take "
            "effect at the time shown by next_reinforce_apply"
        ),
    )
    next_reinforce_apply = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=(
            "The requested change to reinforce_hour that will take "
            "effect at the time shown by next_reinforce_apply"
        ),
    )
    reinforce_hour = models.PositiveIntegerField(
        validators=[MaxValueValidator(23)],
        null=True,
        default=None,
        blank=True,
        help_text=(
            "The hour of day that determines the four hour window "
            "when the structure will randomly exit its reinforcement periods "
            "and become vulnerable to attack against its armor and/or hull. "
            "The structure will become vulnerable at a random time that "
            "is +/- 2 hours centered on the value of this property"
        ),
    )
    state = models.IntegerField(
        choices=State.choices,
        default=State.UNKNOWN,
        blank=True,
        help_text="Current state of the structure",
    )
    state_timer_start = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="Date at which the structure will move to it’s next state",
    )
    state_timer_end = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="Date at which the structure entered it’s current state",
    )
    unanchors_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="Date at which the structure will unanchor",
    )
    last_online_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="date this structure had any of it's services online",
    )
    tags = models.ManyToManyField(
        StructureTag,
        default=None,
        blank=True,
        help_text="list of tags for this structure",
    )
    last_updated_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text="date this structure was last updated from the EVE server",
    )
    created_at = models.DateTimeField(
        default=now,
        help_text="date this structure was received from ESI for the first time",
    )
    has_fitting = models.BooleanField(
        null=True,
        default=None,
        blank=True,
        db_index=True,
        help_text="bool indicating if the structure has a fitting",
    )
    has_core = models.BooleanField(
        null=True,
        default=None,
        blank=True,
        db_index=True,
        help_text="bool indicating if the structure has a quantum core",
    )

    objects = StructureManager()

    def __str__(self):
        return "{} - {}".format(self.eve_solar_system, self.name)

    def __repr__(self):
        return "{}(id={}, name='{}')".format(
            self.__class__.__name__, self.id, self.name
        )

    @property
    def is_full_power(self):
        """return True if structure is full power, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        else:
            return power_mode == self.PowerMode.FULL_POWER

    @property
    def is_low_power(self):
        """return True if structure is low power, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        else:
            return power_mode == self.PowerMode.LOW_POWER

    @property
    def is_abandoned(self):
        """return True if structure is abandoned, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        else:
            return power_mode == self.PowerMode.ABANDONED

    @property
    def is_maybe_abandoned(self):
        """return True if structure is maybe abandoned, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        else:
            return power_mode == self.PowerMode.LOW_ABANDONED

    @property
    def power_mode(self):
        """returns the calculated power mode of this structure, e.g. low power
        returns None for non upwell structures
        """
        if not self.eve_type.is_upwell_structure:
            return None

        if self.fuel_expires_at and self.fuel_expires_at > now():
            return self.PowerMode.FULL_POWER

        elif self.last_online_at:
            if self.last_online_at >= now() - timedelta(days=7):
                return self.PowerMode.LOW_POWER
            else:
                return self.PowerMode.ABANDONED

        elif self.state in {self.State.ANCHORING, self.State.ANCHOR_VULNERABLE}:
            return self.PowerMode.LOW_POWER

        else:
            return self.PowerMode.LOW_ABANDONED

    @property
    def is_reinforced(self):
        return self.state in [
            self.State.ARMOR_REINFORCE,
            self.State.HULL_REINFORCE,
            self.State.ANCHOR_VULNERABLE,
            self.State.HULL_VULNERABLE,
        ]

    @property
    def owner_has_sov(self):
        return self.eve_solar_system.corporation_has_sov(self.owner.corporation)

    def save(self, *args, **kwargs):
        """make sure related objects are saved whenever structure is saved"""
        super().save(*args, **kwargs)
        self.update_generated_tags()

    def get_power_mode_display(self):
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

    @classmethod
    def extract_name_from_esi_respose(cls, esi_name):
        """extracts the structure's name from the name in an ESI response"""
        matches = re.search(r"^\S+ - (.+)", esi_name)
        return matches.group(1) if matches else esi_name


class StructureService(EsiNameLocalization, models.Model):
    """service of a structure"""

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
        help_text="Structure this service is installed to",
    )
    name = models.CharField(max_length=100, help_text="Name of the service")
    state = models.IntegerField(
        choices=State.choices, help_text="Current state of this service"
    )

    class Meta:
        unique_together = (("structure", "name"),)

    def __str__(self):
        return "{} - {}".format(str(self.structure), self.name)

    def __repr__(self):
        return "{}(structure_id={}, name='{}')".format(
            self.__class__.__name__, self.structure.id, self.name
        )
