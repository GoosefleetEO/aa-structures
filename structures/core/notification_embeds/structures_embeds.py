"""Upwell structures embeds."""

# pylint: disable=missing-class-docstring

from collections import namedtuple

import dhooks_lite

from django.utils.translation import gettext as __
from eveuniverse.models import EveEntity, EveSolarSystem, EveType

from app_utils.datetime import ldap_time_2_datetime, ldap_timedelta_2_timedelta

from structures.models import Notification, Webhook
from structures.models.structures import Structure

from .helpers import (
    compile_damage_text,
    fuel_expires_target_date,
    gen_alliance_link,
    gen_corporation_link,
    gen_solar_system_text,
    target_datetime_formatted,
    timeuntil,
)
from .main import NotificationBaseEmbed


class NotificationStructureEmbed(NotificationBaseEmbed):
    """Base class for most structure related notification embeds."""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        try:
            structure = Structure.objects.select_related_defaults().get(
                id=self._parsed_text["structureID"]
            )
        except Structure.DoesNotExist:
            structure = None
            structure_name = __("(unknown)")
            structure_type, _ = EveType.objects.get_or_create_esi(
                id=self._parsed_text["structureTypeID"]
            )
            structure_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                id=self._parsed_text["solarsystemID"]
            )
            owner_link = "(unknown)"
            location = ""
        else:
            structure_name = structure.name
            structure_type = structure.eve_type
            structure_solar_system = structure.eve_solar_system
            owner_link = gen_corporation_link(str(structure.owner))
            location = f" at {structure.eve_moon} " if structure.eve_moon else ""

        self._structure = structure
        self._description = __(
            "The %(structure_type)s %(structure_name)s%(location)s in %(solar_system)s "
            "belonging to %(owner_link)s "
        ) % {
            "structure_type": structure_type.name,
            "structure_name": Webhook.text_bold(structure_name),
            "location": location,
            "solar_system": gen_solar_system_text(structure_solar_system),
            "owner_link": owner_link,
        }
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationStructureOnline(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Structure online")
        self._description += __("is now online.")
        self._color = Webhook.Color.SUCCESS


class NotificationStructureFuelAlert(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        if self._structure and self._structure.fuel_expires_at:
            hours_left = timeuntil(self._structure.fuel_expires_at)
        else:
            hours_left = "?"
        self._title = __("Structure fuel alert")
        self._description += __("is running out of fuel in %s.") % Webhook.text_bold(
            hours_left
        )

        self._color = Webhook.Color.WARNING


class NotificationStructureJumpFuelAlert(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Jump gate low on Liquid Ozone")
        threshold_str = f"{self._parsed_text['threshold']:,}"
        quantity_str = f"{self._structure.jump_fuel_quantity():,}"
        self._description += __(
            "is below %(threshold)s units on Liquid Ozone.\n"
            "Remaining units: %(remaining)s."
            % {
                "threshold": f"{Webhook.text_bold(threshold_str)}",
                "remaining": f"{Webhook.text_bold(quantity_str)}",
            }
        )
        self._color = Webhook.Color.WARNING


class NotificationStructureRefueledExtra(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        target_date = fuel_expires_target_date(self._structure)
        self._title = __("Structure refueled")
        self._description += (
            __("has been refueled. Fuel will last until %s.") % target_date
        )
        self._color = Webhook.Color.INFO


class NotificationStructureServicesOffline(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Structure services off-line")
        self._description += __("has all services off-lined.")
        if self._structure and self._structure.services.count() > 0:
            qs = self._structure.services.all().order_by("name")
            services_list = "\n".join([x.name for x in qs])
            self._description += f"\n*{services_list}*"
        self._color = Webhook.Color.DANGER


class NotificationStructureWentLowPower(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Structure low power")
        self._description += __("went to low power mode.")
        self._color = Webhook.Color.WARNING


class NotificationStructureWentHighPower(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Structure full power")
        self._description += __("went to full power mode.")
        self._color = Webhook.Color.SUCCESS


class NotificationStructureUnanchoring(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Structure un-anchoring")
        unanchored_at = notification.timestamp + ldap_timedelta_2_timedelta(
            self._parsed_text["timeLeft"]
        )
        self._description += __(
            "has started un-anchoring. It will be fully un-anchored at: %s"
        ) % target_datetime_formatted(unanchored_at)
        self._color = Webhook.Color.INFO


class NotificationStructureUnderAttack(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Structure under attack")
        self._description += __("is under attack by %s.\n%s") % (
            self._get_attacker_link(),
            compile_damage_text(self._parsed_text, "Percentage"),
        )
        self._color = Webhook.Color.DANGER

    def _get_attacker_link(self) -> str:
        """Returns the attacker link from a parsed_text for Upwell structures only."""
        if self._parsed_text.get("allianceName"):
            return gen_alliance_link(self._parsed_text["allianceName"])

        if self._parsed_text.get("corpName"):
            return gen_corporation_link(self._parsed_text["corpName"])

        return "(unknown)"


class NotificationStructureLostShield(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Structure lost shield")
        timer_ends_at = notification.timestamp + ldap_timedelta_2_timedelta(
            self._parsed_text["timeLeft"]
        )
        self._description += __(
            "has lost its shields. Armor timer end at: %s"
        ) % target_datetime_formatted(timer_ends_at)
        self._color = Webhook.Color.DANGER


class NotificationStructureLostArmor(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Structure lost armor")
        timer_ends_at = notification.timestamp + ldap_timedelta_2_timedelta(
            self._parsed_text["timeLeft"]
        )
        self._description += __(
            "has lost its armor. Hull timer end at: %s"
        ) % target_datetime_formatted(timer_ends_at)
        self._color = Webhook.Color.DANGER


class NotificationStructureDestroyed(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Structure destroyed")
        self._description += __("has been destroyed.")
        self._color = Webhook.Color.DANGER


class NotificationStructureOwnershipTransferred(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        structure_type = self.structure_type()
        self._description = __(
            "The %(structure_type)s %(structure_name)s in %(solar_system)s "
        ) % {
            "structure_type": structure_type.name,
            "structure_name": Webhook.text_bold(self._parsed_text["structureName"]),
            "solar_system": gen_solar_system_text(self.solar_system()),
        }
        from_corporation, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["oldOwnerCorpID"]
        )
        to_corporation, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["newOwnerCorpID"]
        )
        character, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["charID"]
        )
        self._description += __(
            "has been transferred from %(from_corporation)s "
            "to %(to_corporation)s by %(character)s."
        ) % {
            "from_corporation": gen_corporation_link(from_corporation.name),
            "to_corporation": gen_corporation_link(to_corporation.name),
            "character": character.name,
        }
        self._title = __("Ownership transferred")
        self._color = Webhook.Color.INFO
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationStructureAnchoring(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        structure_type = self.structure_type()
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=self._parsed_text["solarsystemID"]
        )
        owner_link = gen_corporation_link(
            self._parsed_text.get("ownerCorpName", "(unknown)")
        )
        self._description = __(
            "A %(structure_type)s belonging to %(owner_link)s "
            "has started anchoring in %(solar_system)s. "
        ) % {
            "structure_type": structure_type.name,
            "owner_link": owner_link,
            "solar_system": gen_solar_system_text(solar_system),
        }
        self._title = __("Structure anchoring")
        self._color = Webhook.Color.INFO
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationStructureReinforceChange(NotificationBaseEmbed):
    StructureInfo = namedtuple(
        "StructureInfo", ["name", "eve_type", "eve_solar_system", "owner_link"]
    )

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        all_structure_info = []
        for structure_info in self._parsed_text["allStructureInfo"]:
            try:
                structure = Structure.objects.select_related_defaults().get(
                    id=structure_info[0]
                )
            except Structure.DoesNotExist:
                all_structure_info.append(
                    self.StructureInfo(
                        name=structure_info[1],
                        eve_type=EveType.objects.get_or_create_esi(
                            id=structure_info[2]
                        ),
                        eve_solar_system=None,
                        owner_link="(unknown)",
                    )
                )
            else:
                all_structure_info.append(
                    self.StructureInfo(
                        name=structure.name,
                        eve_type=structure.eve_type,
                        eve_solar_system=structure.eve_solar_system,
                        owner_link=gen_corporation_link(str(structure.owner)),
                    )
                )

        self._title = __("Structure reinforcement time changed")
        change_effective = ldap_time_2_datetime(self._parsed_text["timestamp"])
        self._description = __(
            "Reinforcement hour has been changed to %s "
            "for the following structures:\n"
        ) % Webhook.text_bold(self._parsed_text["hour"])
        for structure_info in all_structure_info:
            self._description += __(
                "- %(structure_type)s %(structure_name)s in %(solar_system)s "
                "belonging to %(owner_link)s"
            ) % {
                "structure_type": structure_info.eve_type.name,
                "structure_name": Webhook.text_bold(structure_info.name),
                "solar_system": gen_solar_system_text(structure_info.eve_solar_system),
                "owner_link": structure_info.owner_link,
            }

        self._description += __(
            "\n\nChange becomes effective at %s."
        ) % target_datetime_formatted(change_effective)
        self._color = Webhook.Color.INFO
