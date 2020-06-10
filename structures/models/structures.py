"""Structure related models"""
from datetime import timedelta
import re
import logging

from django.db import models
from django.core.validators import MinValueValidator
from django.core.validators import MaxValueValidator
from django.utils.html import escape
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_noop

from .. import __title__
from .eveuniverse import EsiNameLocalization
from .eveuniverse import EveSolarSystem
from ..managers import StructureManager
from ..managers import StructureTagManager
from ..utils import LoggerAddTag, create_bs_label_html


logger = LoggerAddTag(logging.getLogger(__name__), __title__)


class StructureTag(models.Model):
    """tag for organizing structures"""

    # special tags
    NAME_SOV_TAG = gettext_noop("sov")
    NAME_HIGHSEC_TAG = gettext_noop("highsec")
    NAME_LOWSEC_TAG = gettext_noop("lowsec")
    NAME_NULLSEC_TAG = gettext_noop("nullsec")
    NAME_W_SPACE_TAG = gettext_noop("w_space")

    # styles
    STYLE_GREY = "default"
    STYLE_DARK_BLUE = "primary"
    STYLE_GREEN = "success"
    STYLE_LIGHT_BLUE = "info"
    STYLE_ORANGE = "warning"
    STYLE_RED = "danger"
    STYLE_CHOICES = [
        (STYLE_GREY, "grey"),
        (STYLE_DARK_BLUE, "dark blue"),
        (STYLE_GREEN, "green"),
        (STYLE_LIGHT_BLUE, "light blue"),
        (STYLE_ORANGE, "orange"),
        (STYLE_RED, "red"),
    ]

    SPACE_TYPE_MAP = {
        EveSolarSystem.TYPE_HIGHSEC: {"name": NAME_HIGHSEC_TAG, "style": STYLE_GREEN},
        EveSolarSystem.TYPE_LOWSEC: {"name": NAME_LOWSEC_TAG, "style": STYLE_ORANGE},
        EveSolarSystem.TYPE_NULLSEC: {"name": NAME_NULLSEC_TAG, "style": STYLE_RED},
        EveSolarSystem.TYPE_W_SPACE: {
            "name": NAME_W_SPACE_TAG,
            "style": STYLE_LIGHT_BLUE,
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
        choices=STYLE_CHOICES,
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
        return create_bs_label_html(name, self.style)

    @classmethod
    def sorted(cls, tags: list, reverse: bool = False) -> list:
        """returns a sorted copy of the provided list of tags"""
        return sorted(tags, key=lambda x: x.name.lower(), reverse=reverse)


class Structure(models.Model):
    """structure of a corporation"""

    STATE_NA = 0
    STATE_ANCHOR_VULNERABLE = 1
    STATE_ANCHORING = 2
    STATE_ARMOR_REINFORCE = 3
    STATE_ARMOR_VULNERABLE = 4
    STATE_DEPLOY_VULNERABLE = 5
    STATE_FITTING_INVULNERABLE = 6
    STATE_HULL_REINFORCE = 7
    STATE_HULL_VULNERABLE = 8
    STATE_ONLINE_DEPRECATED = 9
    STATE_ONLINING_VULNERABLE = 10
    STATE_SHIELD_VULNERABLE = 11
    STATE_UNANCHORED = 12
    STATE_UNKNOWN = 13

    STATE_POS_OFFLINE = 21
    STATE_POS_ONLINE = 22
    STATE_POS_ONLINING = 23
    STATE_POS_REINFORCED = 24
    STATE_POS_UNANCHORING = 25

    STATE_CHOICES = [
        # states Upwell structures
        (STATE_ANCHOR_VULNERABLE, _("anchor vulnerable")),
        (STATE_ANCHORING, _("anchoring")),
        (STATE_ARMOR_REINFORCE, _("armor reinforce")),
        (STATE_ARMOR_VULNERABLE, _("armor vulnerable")),
        (STATE_DEPLOY_VULNERABLE, _("deploy vulnerable")),
        (STATE_FITTING_INVULNERABLE, _("fitting invulnerable")),
        (STATE_HULL_REINFORCE, _("hull reinforce")),
        (STATE_HULL_VULNERABLE, _("hull vulnerable")),
        (STATE_ONLINE_DEPRECATED, _("online deprecated")),
        (STATE_ONLINING_VULNERABLE, _("onlining vulnerable")),
        (STATE_SHIELD_VULNERABLE, _("shield vulnerable")),
        (STATE_UNANCHORED, _("unanchored")),
        # starbases
        (STATE_POS_OFFLINE, _("offline")),
        (STATE_POS_ONLINE, _("online")),
        (STATE_POS_ONLINING, _("onlining")),
        (STATE_POS_REINFORCED, _("reinforced")),
        (STATE_POS_UNANCHORING, _("unanchoring ")),
        # other
        (STATE_NA, _("N/A")),
        (STATE_UNKNOWN, _("unknown")),
    ]
    _STATES_ESI_MAP = {
        "anchor_vulnerable": STATE_ANCHOR_VULNERABLE,
        "anchoring": STATE_ANCHORING,
        "armor_reinforce": STATE_ARMOR_REINFORCE,
        "armor_vulnerable": STATE_ARMOR_VULNERABLE,
        "deploy_vulnerable": STATE_DEPLOY_VULNERABLE,
        "fitting_invulnerable": STATE_FITTING_INVULNERABLE,
        "hull_reinforce": STATE_HULL_REINFORCE,
        "hull_vulnerable": STATE_HULL_VULNERABLE,
        "online_deprecated": STATE_ONLINE_DEPRECATED,
        "onlining_vulnerable": STATE_ONLINING_VULNERABLE,
        "shield_vulnerable": STATE_SHIELD_VULNERABLE,
        "unanchored": STATE_UNANCHORED,
        "offline": STATE_POS_OFFLINE,
        "online": STATE_POS_ONLINE,
        "onlining": STATE_POS_ONLINING,
        "reinforced": STATE_POS_REINFORCED,
        "unanchoring ": STATE_POS_UNANCHORING,
    }

    # power modes
    MODE_FULL_POWER = "FU"
    MODE_LOW_POWER = "LO"
    MODE_ABANDONED = "AB"
    MODE_LOW_ABANDONED = "LA"
    MODE_UNKNOWN = "UN"
    MODE_CHOICES = (
        (MODE_FULL_POWER, _("Full Power")),
        (MODE_LOW_POWER, _("Low Power")),
        (MODE_ABANDONED, _("Abandoned")),
        (MODE_LOW_ABANDONED, _("Abandoned?")),
        (MODE_UNKNOWN, _("Unknown")),
    )

    id = models.BigIntegerField(
        primary_key=True, help_text="The Item ID of the structure"
    )
    owner = models.ForeignKey(
        "Owner",
        on_delete=models.CASCADE,
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
    next_reinforce_weekday = models.PositiveIntegerField(
        null=True,
        default=None,
        blank=True,
        validators=[MaxValueValidator(6)],
        help_text=(
            "The date and time when the structure’s newly requested "
            "reinforcement times (e.g. next_reinforce_hour and "
            "next_reinforce_day) will take effect"
        ),
    )
    next_reinforce_apply = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=(
            "The requested change to reinforce_weekday that will take "
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
    reinforce_weekday = models.PositiveIntegerField(
        null=True,
        default=None,
        blank=True,
        validators=[MaxValueValidator(6)],
        help_text="(no longer used)",
    )
    state = models.IntegerField(
        choices=STATE_CHOICES,
        default=STATE_UNKNOWN,
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

    objects = StructureManager()

    @property
    def is_full_power(self):
        """return True if structure is full power, False if not.
        
        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        else:
            return power_mode == self.MODE_FULL_POWER

    @property
    def is_low_power(self):
        """return True if structure is low power, False if not.
        
        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        else:
            return power_mode == self.MODE_LOW_POWER

    @property
    def is_abandoned(self):
        """return True if structure is abandoned, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        else:
            return power_mode == self.MODE_ABANDONED

    @property
    def is_maybe_abandoned(self):
        """return True if structure is maybe abandoned, False if not.

        Returns None if state can not be determined
        """
        power_mode = self.power_mode
        if not power_mode:
            return None
        else:
            return power_mode == self.MODE_LOW_ABANDONED

    @property
    def power_mode(self):
        """returns the calculated power mode of this structure, e.g. low power
        returns None for non upwell structures
        """
        if not self.eve_type.is_upwell_structure:
            return None

        if self.fuel_expires_at and self.fuel_expires_at > now():
            return self.MODE_FULL_POWER

        elif self.last_online_at:
            if self.last_online_at >= now() - timedelta(days=7):
                return self.MODE_LOW_POWER
            else:
                return self.MODE_ABANDONED

        elif self.state in (self.STATE_ANCHORING, self.STATE_ANCHOR_VULNERABLE):
            return self.MODE_LOW_POWER

        else:
            return self.MODE_LOW_ABANDONED

    def get_power_mode_display(self):
        power_mode = self.power_mode
        for key, value in self.MODE_CHOICES:
            if key == power_mode:
                return value

        return ""

    @property
    def is_reinforced(self):
        return self.state in [
            self.STATE_ARMOR_REINFORCE,
            self.STATE_HULL_REINFORCE,
            self.STATE_ANCHOR_VULNERABLE,
            self.STATE_HULL_VULNERABLE,
        ]

    @property
    def owner_has_sov(self):
        return self.eve_solar_system.corporation_has_sov(self.owner.corporation)

    def __str__(self):
        return "{} - {}".format(self.eve_solar_system, self.name)

    def __repr__(self):
        return "{}(id={}, name='{}')".format(
            self.__class__.__name__, self.id, self.name
        )

    @classmethod
    def get_matching_state_for_esi_state(cls, esi_state_name) -> int:
        """returns matching state for esi state name of Upwell structures"""
        return (
            cls._STATES_ESI_MAP[esi_state_name]
            if esi_state_name in cls._STATES_ESI_MAP
            else cls.STATE_UNKNOWN
        )

    @classmethod
    def extract_name_from_esi_respose(cls, esi_name):
        """extracts the structure's name from the name in an ESI response"""
        matches = re.search(r"^\S+ - (.+)", esi_name)
        return matches.group(1) if matches else esi_name

    def save(self, *args, **kwargs):
        """make sure related objects are saved whenever structure is saved"""
        super().save(*args, **kwargs)
        self.update_generated_tags()

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


class StructureService(EsiNameLocalization, models.Model):
    """service of a structure"""

    STATE_OFFLINE = 1
    STATE_ONLINE = 2

    STATE_CHOICES = [
        (STATE_OFFLINE, _("offline")),
        (STATE_ONLINE, _("online")),
    ]

    _STATES_ESI_MAP = {
        "offline": STATE_OFFLINE,
        "online": STATE_ONLINE,
    }

    structure = models.ForeignKey(
        Structure,
        on_delete=models.CASCADE,
        help_text="Structure this service is installed to",
    )
    name = models.CharField(max_length=100, help_text="Name of the service")
    state = models.IntegerField(
        choices=STATE_CHOICES, help_text="Current state of this service"
    )

    class Meta:
        unique_together = (("structure", "name"),)

    def __str__(self):
        return "{} - {}".format(str(self.structure), self.name)

    def __repr__(self):
        return "{}(structure_id={}, name='{}')".format(
            self.__class__.__name__, self.structure.id, self.name
        )

    @classmethod
    def get_matching_state_for_esi_state(cls, esi_state_name) -> int:
        """returns matching state for given state name"""
        return (
            cls._STATES_ESI_MAP[esi_state_name]
            if esi_state_name in cls._STATES_ESI_MAP
            else cls.STATE_OFFLINE
        )
