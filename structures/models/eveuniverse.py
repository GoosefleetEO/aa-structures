"""Eve Universe models"""

from enum import Enum

from django.db import models
from eveuniverse.models import EveSolarSystem

from ..managers import EveSovereigntyMapManager


class EveSovereigntyMap(models.Model):
    """Shows which alliance / corporation / faction owns a system

    Note: This model does not hold FKs to respective objects like
    EveSolarSystem to avoid having load all those object from ESI
    """

    solar_system_id = models.PositiveIntegerField(primary_key=True)
    alliance_id = models.PositiveIntegerField(
        blank=True,
        null=True,
        db_index=True,
        help_text="alliance who holds sov for this system",
    )
    corporation_id = models.PositiveIntegerField(
        blank=True,
        null=True,
        db_index=True,
        help_text="corporation who holds sov for this system",
    )
    faction_id = models.PositiveIntegerField(
        blank=True,
        null=True,
        db_index=True,
        help_text="faction who holds sov for this system",
    )
    last_updated = models.DateTimeField(
        default=None,
        null=True,
        blank=True,
        help_text="When this object was last updated from ESI",
        db_index=True,
    )

    objects = EveSovereigntyMapManager()

    def __str__(self):
        return str(self.solar_system_id)

    def __repr__(self):
        return "{}(solar_system_id='{}')".format(
            self.__class__.__name__, self.solar_system_id
        )


class EveSpaceType(str, Enum):
    UNKNOWN = "unknown"
    HIGHSEC = "highsec"
    LOWSEC = "lowsec"
    NULLSEC = "nullsec"
    W_SPACE = "w-space"

    @classmethod
    def from_solar_system(cls, eve_solar_system: EveSolarSystem) -> "EveSpaceType":
        """returns the space type"""
        if eve_solar_system.is_null_sec:
            return cls.NULLSEC
        elif eve_solar_system.is_low_sec:
            return cls.LOWSEC
        elif eve_solar_system.is_high_sec:
            return cls.HIGHSEC
        elif eve_solar_system.is_w_space:
            return cls.W_SPACE
        return cls.UNKNOWN
