"""Starbase embeds."""

# pylint: disable=missing-class-docstring

import datetime as dt

import dhooks_lite

from django.utils.translation import gettext as __
from eveuniverse.models import EveMoon, EveSolarSystem, EveType

from structures.core import starbases
from structures.models import GeneratedNotification, Notification, Structure, Webhook

from .helpers import (
    compile_damage_text,
    fuel_expires_target_date,
    gen_corporation_link,
    gen_solar_system_text,
    get_aggressor_link,
    target_datetime_formatted,
    timeuntil,
)
from .main import NotificationBaseEmbed


class NotificationTowerEmbed(NotificationBaseEmbed):
    """Base class for all tower (aka POS) related notification embeds."""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self.eve_moon, _ = EveMoon.objects.get_or_create_esi(
            id=self._parsed_text["moonID"]
        )
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=self._parsed_text["typeID"]
        )
        self._structure = Structure.objects.filter(eve_moon=self.eve_moon).first()
        if self._structure:
            structure_name = self._structure.name
        else:
            structure_name = structure_type.name

        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )
        self._description = __(
            "The starbase %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
        ) % {
            "structure_name": Webhook.text_bold(structure_name),
            "moon": self.eve_moon.name,
            "solar_system": gen_solar_system_text(
                self.eve_moon.eve_planet.eve_solar_system
            ),
            "owner_link": gen_corporation_link(str(notification.owner)),
        }


class NotificationTowerAlertMsg(NotificationTowerEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        aggressor_link = get_aggressor_link(self._parsed_text)
        damage_text = compile_damage_text(self._parsed_text, "Value", 100)
        self._title = __("Starbase under attack")
        self._description += __(
            "is under attack by %(aggressor)s.\n%(damage_text)s"
        ) % {"aggressor": aggressor_link, "damage_text": damage_text}
        self._color = Webhook.Color.WARNING


class NotificationTowerResourceAlertMsg(NotificationTowerEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        if "wants" in self._parsed_text and self._parsed_text["wants"]:
            fuel_quantity = self._parsed_text["wants"][0]["quantity"]
            starbase_type, _ = EveType.objects.get_or_create_esi(
                id=self._parsed_text["typeID"]
            )
            solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                id=self._parsed_text["solarSystemID"]
            )
            seconds = starbases.fuel_duration(
                starbase_type=starbase_type,
                fuel_quantity=fuel_quantity,
                has_sov=notification.owner.has_sov(solar_system),
            )
            from_date = self.notification.timestamp
            to_date = from_date + dt.timedelta(seconds=seconds)
            hours_left = timeuntil(to_date, from_date)
        elif self._structure and self._structure.fuel_expires_at:
            hours_left = timeuntil(self._structure.fuel_expires_at)
        else:
            hours_left = "?"
        self._title = __("Starbase fuel alert")
        self._description += __("is running out of fuel in %s.") % Webhook.text_bold(
            hours_left
        )
        self._color = Webhook.Color.WARNING


class NotificationTowerRefueledExtra(NotificationTowerEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        target_date = fuel_expires_target_date(self._structure)
        self._title = __("Starbase refueled")
        self._description += (
            __("has been refueled. Fuel will last until %s.") % target_date
        )
        self._color = Webhook.Color.INFO


class GeneratedNotificationBaseEmbed(NotificationBaseEmbed):
    """Base class for generated notification embeds."""

    def __init__(self, notification: GeneratedNotification) -> None:
        super().__init__(notification)
        if not isinstance(notification, GeneratedNotification):
            raise TypeError(
                "Can only create embeds from GeneratedNotification objects."
            )
        self._structure = notification.structures.first()
        self._thumbnail = dhooks_lite.Thumbnail(
            self._structure.eve_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class GeneratedNotificationTowerEmbed(GeneratedNotificationBaseEmbed):
    """Base class for all tower (aka POS) related generated notification embeds."""

    def __init__(self, notification: GeneratedNotification) -> None:
        super().__init__(notification)
        self._description = __(
            "The starbase %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
        ) % {
            "structure_name": Webhook.text_bold(self._structure.name),
            "moon": self._structure.eve_moon.name,
            "solar_system": gen_solar_system_text(self._structure.eve_solar_system),
            "owner_link": gen_corporation_link(str(notification.owner)),
        }


class NotificationTowerReinforcedExtra(GeneratedNotificationTowerEmbed):
    def __init__(self, notification: GeneratedNotification) -> None:
        super().__init__(notification)
        self._title = __("Starbase reinforced")
        try:
            reinforced_until = target_datetime_formatted(
                dt.datetime.fromisoformat(notification.details["reinforced_until"])
            )
        except (KeyError, ValueError):
            reinforced_until = "(unknown)"
        self._description += (
            __("has been reinforced and will come out at: %s.") % reinforced_until
        )

        self._color = Webhook.Color.DANGER
