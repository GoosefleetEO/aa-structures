"""Moonmining embeds."""

# pylint: disable=missing-class-docstring


import dhooks_lite

from django.utils.translation import gettext as _
from eveuniverse.models import EveEntity, EveType

from app_utils.datetime import ldap_time_2_datetime

from structures.app_settings import STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
from structures.helpers import get_or_create_esi_obj
from structures.models import Notification, Webhook

from .helpers import (
    gen_corporation_link,
    gen_solar_system_text,
    target_datetime_formatted,
)
from .main import NotificationBaseEmbed


class NotificationMoonminingEmbed(NotificationBaseEmbed):
    """Base class for all moon mining related notification embeds."""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._moon = self._notification.eve_moon()
        self._solar_system_link = gen_solar_system_text(
            self._notification.eve_solar_system()
        )
        self._structure_name = self._parsed_text["structureName"]
        self._owner_link = gen_corporation_link(str(notification.owner))
        structure_type = self._notification.eve_structure_type()
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )
        self.ore_text = (
            _("Estimated ore composition: %s") % self._ore_composition_text()
            if STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
            else ""
        )

    def _ore_composition_text(self) -> str:
        if "oreVolumeByType" not in self._parsed_text:
            return ""

        ore_list = []
        for ore_type_id, volume in self._parsed_text["oreVolumeByType"].items():
            ore_type = get_or_create_esi_obj(EveType, id=ore_type_id)
            if ore_type:
                ore_list.append(
                    {"id": ore_type_id, "name": ore_type.name, "volume": volume}
                )

        ore_list_2 = sorted(ore_list, key=lambda x: x["name"])
        return "\n- " + "\n- ".join(
            [f"{ore['name']}: {ore['volume']:,.0f} m³" for ore in ore_list_2]
        )


class NotificationMoonminningExtractionStarted(NotificationMoonminingEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        started_by = get_or_create_esi_obj(EveEntity, id=self._parsed_text["startedBy"])
        ready_time = ldap_time_2_datetime(self._parsed_text["readyTime"])
        auto_time = ldap_time_2_datetime(self._parsed_text["autoTime"])
        self._title = _("Moon mining extraction started")
        self._description = _(
            "A moon mining extraction has been started "
            "for %(structure_name)s at %(moon)s in %(solar_system)s "
            "belonging to %(owner_link)s. "
            "Extraction was started by %(character)s.\n"
            "The chunk will be ready on location at %(ready_time)s, "
            "and will fracture automatically on %(auto_time)s.\n"
            "\n%(ore_text)s"
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "character": started_by,
            "ready_time": target_datetime_formatted(ready_time),
            "auto_time": target_datetime_formatted(auto_time),
            "ore_text": self.ore_text,
        }
        self._color = Webhook.Color.INFO


class NotificationMoonminningExtractionFinished(NotificationMoonminingEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        auto_time = ldap_time_2_datetime(self._parsed_text["autoTime"])
        self._title = _("Extraction finished")
        self._description = _(
            "The extraction for %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
            "is finished and the chunk is ready "
            "to be shot at.\n"
            "The chunk will automatically fracture on %(auto_time)s.\n"
            "\n%(ore_text)s"
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "auto_time": target_datetime_formatted(auto_time),
            "ore_text": self.ore_text,
        }
        self._color = Webhook.Color.INFO


class NotificationMoonminningAutomaticFracture(NotificationMoonminingEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = _("Automatic Fracture")
        self._description = _(
            "The moon drill fitted to %(structure_name)s at %(moon)s"
            " in %(solar_system)s belonging to %(owner_link)s "
            "has automatically been fired "
            "and the moon products are ready to be harvested.\n"
            "\n%(ore_text)s"
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "ore_text": self.ore_text,
        }
        self._color = Webhook.Color.SUCCESS


class NotificationMoonminningExtractionCanceled(NotificationMoonminingEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        if self._parsed_text["cancelledBy"]:
            cancelled_by = get_or_create_esi_obj(
                EveEntity, id=self._parsed_text["cancelledBy"]
            )
        else:
            cancelled_by = _("(unknown)")
        self._title = _("Extraction cancelled")
        self._description = _(
            "An ongoing extraction for %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
            "has been cancelled by %(character)s."
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "character": cancelled_by,
        }
        self._color = Webhook.Color.WARNING


class NotificationMoonminningLaserFired(NotificationMoonminingEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        fired_by = EveEntity.objects.get_or_create_esi(id=self._parsed_text["firedBy"])[
            0
        ]
        self._title = _("Moon drill fired")
        self._description = _(
            "The moon drill fitted to %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
            "has been fired by %(character)s "
            "and the moon products are ready to be harvested.\n"
            "\n%(ore_text)s"
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "character": fired_by,
            "ore_text": self.ore_text,
        }
        self._color = Webhook.Color.SUCCESS
