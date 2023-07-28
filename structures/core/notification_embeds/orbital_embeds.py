import dhooks_lite

from django.utils.translation import gettext as __
from eveuniverse.models import EvePlanet, EveSolarSystem, EveType

from app_utils.datetime import ldap_time_2_datetime

from structures.constants import EveTypeId
from structures.models import Notification, Webhook

from .helpers import (
    gen_corporation_link,
    gen_solar_system_text,
    target_datetime_formatted,
)
from .main import NotificationBaseEmbed


class NotificationOrbitalEmbed(NotificationBaseEmbed):
    """Base class for all orbital (aka POCO) related notification embeds."""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._planet, _ = EvePlanet.objects.get_or_create_esi(
            id=self._parsed_text["planetID"]
        )
        self._structure_type, _ = EveType.objects.get_or_create_esi(
            id=EveTypeId.CUSTOMS_OFFICE
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=self._parsed_text["solarSystemID"]
        )
        self._solar_system_link = gen_solar_system_text(solar_system)
        self._owner_link = gen_corporation_link(str(notification.owner))
        self._aggressor_link = self._get_aggressor_link()
        self._thumbnail = dhooks_lite.Thumbnail(
            self._structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationOrbitalAttacked(NotificationOrbitalEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Orbital under attack")
        self._description = __(
            "The %(structure_type)s at %(planet)s in %(solar_system)s "
            "belonging to %(owner_link)s "
            "is under attack by %(aggressor)s."
        ) % {
            "structure_type": self._structure_type.name,
            "planet": self._planet.name,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "aggressor": self._aggressor_link,
        }
        self._color = Webhook.Color.WARNING


class NotificationOrbitalReinforced(NotificationOrbitalEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        reinforce_exit_time = ldap_time_2_datetime(
            self._parsed_text["reinforceExitTime"]
        )
        self._title = __("Orbital reinforced")
        self._description = __(
            "The %(structure_type)s at %(planet)s in %(solar_system)s "
            "belonging to %(owner_link)s "
            "has been reinforced by %(aggressor)s "
            "and will come out at: %(date)s."
        ) % {
            "structure_type": self._structure_type.name,
            "planet": self._planet.name,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "aggressor": self._aggressor_link,
            "date": target_datetime_formatted(reinforce_exit_time),
        }
        self._color = Webhook.Color.DANGER
