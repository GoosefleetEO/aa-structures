"""Models related to Structure."""

import datetime as dt
from typing import Optional

from django.db import models
from django.utils.translation import gettext_lazy as _
from eveuniverse.models import EveType

from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from .. import __title__
from ..constants import EveGroupId
from ..core import starbases
from .structures_1 import Structure

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class StructureService(models.Model):
    """Service of a Structure."""

    class State(models.IntegerChoices):
        """A state of a structure service."""

        OFFLINE = 1, _("offline")
        ONLINE = 2, _("online")

        @classmethod
        def from_esi_name(cls, esi_state_name: str) -> "StructureService.State":
            """Return matching state for given ESI state name."""
            states_esi_map = {"offline": cls.OFFLINE, "online": cls.ONLINE}
            return (
                states_esi_map[esi_state_name]
                if esi_state_name in states_esi_map
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
        return f"{self.structure} - {self.name}"

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"structure_id={self.structure.id}, name='{self.name}')"
        )


class PocoDetails(models.Model):
    """Additional information about a POCO."""

    class StandingLevel(models.IntegerChoices):
        """A standing level in Eve Online."""

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
        """Return reinforce exit end as string."""
        return f"{self.reinforce_exit_end}:00"

    @property
    def reinforce_exit_start_str(self) -> str:
        """Return reinforce exit start as string."""
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
        """A role for a starbase."""

        ALLIANCE_MEMBER = "AL", _("alliance member")
        CONFIG_STARBASE_EQUIPMENT_ROLE = "CE", _("config starbase equipment role")
        CORPORATION_MEMBER = "CO", _("corporation member")
        STARBASE_FUEL_TECHNICIAN_ROLE = "FT", _("starbase fuel technician role")

        @classmethod
        def from_esi(cls, name: str) -> "StarbaseDetail.Role":
            """Create role from ESI name."""
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
