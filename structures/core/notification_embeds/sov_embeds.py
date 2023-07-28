"""Sovereignty embeds."""

# pylint: disable=missing-class-docstring

import dhooks_lite

from django.utils.translation import gettext as __
from eveuniverse.models import EveEntity, EveMoon, EveSolarSystem, EveType

from app_utils.datetime import ldap_time_2_datetime

from structures.constants import EveTypeId
from structures.core import sovereignty
from structures.models import Notification, Webhook

from .helpers import (
    gen_alliance_link,
    gen_corporation_link,
    gen_eve_entity_link,
    gen_solar_system_text,
    target_datetime_formatted,
)
from .main import NotificationBaseEmbed


class NotificationSovEmbed(NotificationBaseEmbed):
    """Base class for all sovereignty related notification embeds."""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=self._parsed_text["solarSystemID"]
        )
        self._solar_system_link = gen_solar_system_text(self._solar_system)
        if "structureTypeID" in self._parsed_text:
            structure_type_id = self._parsed_text["structureTypeID"]
        elif "campaignEventType" in self._parsed_text:
            structure_type_id = sovereignty.event_type_to_type_id(
                self._parsed_text["campaignEventType"]
            )
        else:
            structure_type_id = EveTypeId.TCU
        structure_type, _ = EveType.objects.get_or_create_esi(id=structure_type_id)
        self._structure_type_name = structure_type.name
        try:
            self._sov_owner_link = gen_alliance_link(notification.sender.name)
        except AttributeError:
            self._sov_owner_link = "(unknown)"
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationSovEntosisCaptureStarted(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("%(structure_type)s in %(solar_system)s is being captured") % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system.name,
        }
        self._description = __(
            "A capsuleer has started to influence the %(type)s "
            "in %(solar_system)s belonging to %(owner)s "
            "with an Entosis Link."
        ) % {
            "type": self._structure_type_name,
            "solar_system": self._solar_system_link,
            "owner": self._sov_owner_link,
        }
        self._color = Webhook.Color.WARNING


class NotificationSovCommandNodeEventStarted(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __(
            "Command nodes for %(structure_type)s in %(solar_system)s "
            "have begun to decloak"
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system.name,
        }
        self._description = __(
            "Command nodes for %(structure_type)s in %(solar_system)s "
            "belonging to %(owner)s can now be found throughout "
            "the %(constellation)s constellation"
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system_link,
            "owner": self._sov_owner_link,
            "constellation": self._solar_system.eve_constellation.name,
        }
        self._color = Webhook.Color.WARNING


class NotificationSovAllClaimAcquiredMsg(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        alliance, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["allianceID"]
        )
        corporation, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["corpID"]
        )
        self._title = (
            __("DED Sovereignty claim acknowledgment: %s") % self._solar_system.name
        )
        self._description = __(
            "DED now officially acknowledges that your "
            "member corporation %(corporation)s has claimed "
            "sovereignty on behalf of %(alliance)s in %(solar_system)s."
        ) % {
            "corporation": gen_corporation_link(corporation.name),
            "alliance": gen_alliance_link(alliance.name),
            "solar_system": self._solar_system_link,
        }
        self._color = Webhook.Color.SUCCESS


class NotificationSovAllClaimLostMsg(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        alliance, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["allianceID"]
        )
        corporation, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["corpID"]
        )
        self._title = __("Lost sovereignty in: %s") % self._solar_system.name
        self._description = __(
            "DED acknowledges that member corporation %(corporation)s has lost its "
            "claim to sovereignty on behalf of %(alliance)s in %(solar_system)s."
        ) % {
            "corporation": gen_corporation_link(corporation.name),
            "alliance": gen_alliance_link(alliance.name),
            "solar_system": self._solar_system_link,
        }
        self._color = Webhook.Color.SUCCESS


class NotificationSovStructureReinforced(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        timer_starts = ldap_time_2_datetime(self._parsed_text["decloakTime"])
        self._title = __(
            "%(structure_type)s in %(solar_system)s has entered reinforced mode"
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system.name,
        }
        self._description = __(
            "The %(structure_type)s in %(solar_system)s belonging "
            "to %(owner)s has been reinforced by "
            "hostile forces and command nodes "
            "will begin decloaking at %(date)s"
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system_link,
            "owner": self._sov_owner_link,
            "date": target_datetime_formatted(timer_starts),
        }
        self._color = Webhook.Color.DANGER


class NotificationSovStructureDestroyed(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __(
            "%(structure_type)s in %(solar_system)s has been destroyed"
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system.name,
        }
        self._description = __(
            "The command nodes for %(structure_type)s "
            "in %(solar_system)s belonging to %(owner)s have been "
            "destroyed by hostile forces."
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system_link,
            "owner": self._sov_owner_link,
        }
        self._color = Webhook.Color.DANGER


class NotificationSovAllAnchoringMsg(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        corporation, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text.get("corpID")
        )
        corp_link = gen_eve_entity_link(corporation)
        alliance_id = self._parsed_text.get("allianceID")
        if alliance_id:
            alliance, _ = EveEntity.objects.get_or_create_esi(id=alliance_id)
            structure_owner = f"{corp_link} ({alliance.name})"
        else:
            structure_owner = corp_link
        eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=self._parsed_text["solarSystemID"]
        )
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=self._parsed_text["typeID"]
        )
        moon_id = self._parsed_text.get("moonID")
        if moon_id:
            eve_moon, _ = EveMoon.objects.get_or_create_esi(id=moon_id)
            location_text = __(" near **%s**") % eve_moon.name
        else:
            location_text = ""
        self._title = __("%(structure_type)s anchored in %(solar_system)s") % {
            "structure_type": structure_type.eve_group.name,
            "solar_system": eve_solar_system.name,
        }
        self._description = __(
            "A %(structure_type)s from %(structure_owner)s has anchored "
            "in %(solar_system)s%(location_text)s."
        ) % {
            "structure_type": Webhook.text_bold(structure_type.name),
            "structure_owner": structure_owner,
            "solar_system": gen_solar_system_text(eve_solar_system),
            "location_text": location_text,
        }
        self._color = Webhook.Color.WARNING
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )
