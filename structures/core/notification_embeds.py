"""Generating notification embeds for Structures."""

# pylint: disable=missing-class-docstring

import datetime as dt
from collections import namedtuple
from typing import Optional

import dhooks_lite

from django.conf import settings
from django.db import models
from django.template import Context, Template
from django.utils.html import strip_tags
from django.utils.timezone import now
from django.utils.translation import gettext as __
from django.utils.translation import gettext_lazy
from eveuniverse.models import EveMoon, EvePlanet, EveSolarSystem, EveType

from allianceauth.eveonline.evelinks import dotlan, evewho
from app_utils.datetime import (
    DATETIME_FORMAT,
    ldap_time_2_datetime,
    ldap_timedelta_2_timedelta,
)
from app_utils.urls import reverse_absolute, static_file_absolute_url

from structures import __title__
from structures.app_settings import STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
from structures.constants import EveTypeId
from structures.models.notifications import (
    EveEntity,
    GeneratedNotification,
    Notification,
    NotificationBase,
    NotificationType,
    Webhook,
)
from structures.models.structures import Structure

from . import sovereignty, starbases


class BillType(models.IntegerChoices):
    """A bill type for infrastructure hub bills."""

    UNKNOWN = 0, gettext_lazy("Unknown Bill")
    INFRASTRUCTURE_HUB = 7, gettext_lazy("Infrastructure Hub Bill")

    @classmethod
    def to_enum(cls, bill_id: int):
        """Create a new enum from a bill type ID."""
        try:
            return cls(bill_id)
        except ValueError:
            return cls.UNKNOWN


def timeuntil(to_date: dt.datetime, from_date: Optional[dt.datetime] = None) -> str:
    """Render timeuntil template tag for given datetime to string."""
    if not from_date:
        from_date = now()
    template = Template("{{ to_date|timeuntil:from_date }}")
    context = Context({"to_date": to_date, "from_date": from_date})
    return template.render(context)


def target_datetime_formatted(target_datetime: dt.datetime) -> str:
    """Formatted Discord string for a target datetime."""
    return (
        f"{Webhook.text_bold(target_datetime.strftime(DATETIME_FORMAT))} "
        f"({timeuntil(target_datetime)})"
    )


class NotificationBaseEmbed:
    """Base class for all notification embeds.

    You must subclass this class to create an embed for a notification type.
    At least title and description must be defined in the subclass.
    """

    ICON_DEFAULT_SIZE = 64

    def __init__(self, notification: Notification) -> None:
        if not isinstance(notification, NotificationBase):
            raise TypeError("notification must be of type Notification")
        self._notification = notification
        self._parsed_text = notification.parsed_text()
        self._title = ""
        self._description = ""
        self._color = None
        self._thumbnail = None
        self._ping_type = None

    def __str__(self) -> str:
        return str(self.notification)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(notification={self.notification})"

    @property
    def notification(self) -> Notification:
        """Return notification object this embed is created from."""
        return self._notification

    @property
    def ping_type(self) -> Optional[Webhook.PingType]:
        """Return Ping Type of the related notification."""
        return self._ping_type

    def generate_embed(self) -> dhooks_lite.Embed:
        """Returns generated Discord embed for this object.

        Will use custom color for embeds if self.notification has the \
            property "color_override" defined

        Will use custom ping type if self.notification has the \
            property "ping_type_override" defined

        """
        corporation = self.notification.owner.corporation
        if self.notification.is_alliance_level and corporation.alliance:
            author_name = corporation.alliance.alliance_name
            author_url = corporation.alliance.logo_url(size=self.ICON_DEFAULT_SIZE)
        else:
            author_name = corporation.corporation_name
            author_url = corporation.logo_url(size=self.ICON_DEFAULT_SIZE)
        app_url = reverse_absolute("structures:index")
        author = dhooks_lite.Author(name=author_name, icon_url=author_url, url=app_url)
        if self.notification._color_override:
            self._color = self.notification._color_override
        if self.notification._ping_type_override:
            self._ping_type = self.notification._ping_type_override
        elif self._color == Webhook.Color.DANGER:
            self._ping_type = Webhook.PingType.EVERYONE
        elif self._color == Webhook.Color.WARNING:
            self._ping_type = Webhook.PingType.HERE
        else:
            self._ping_type = Webhook.PingType.NONE
        if self.notification.is_generated:
            footer_text = __title__
            footer_icon_url = static_file_absolute_url(
                "structures/img/structures_logo.png"
            )
        else:
            footer_text = "Eve Online"
            footer_icon_url = static_file_absolute_url(
                "structures/img/eve_symbol_128.png"
            )
        if settings.DEBUG:
            my_text = (
                self.notification.notification_id
                if not self.notification.is_generated
                else "GENERATED"
            )
            footer_text += f" #{my_text}"
        footer = dhooks_lite.Footer(text=footer_text, icon_url=footer_icon_url)
        return dhooks_lite.Embed(
            author=author,
            color=self._color,
            description=self._description,
            footer=footer,
            timestamp=self.notification.timestamp,
            title=self._title,
            thumbnail=self._thumbnail,
        )

    @staticmethod
    def create(notification: "NotificationBase") -> "NotificationBaseEmbed":
        """Creates a new instance of the respective subclass for given Notification."""
        if not isinstance(notification, NotificationBase):
            raise TypeError("notification must be of type NotificationBase")

        NT = NotificationType
        notif_type_2_class = {
            # character
            NT.CORP_APP_NEW_MSG: NotificationCorpAppNewMsg,
            NT.CORP_APP_INVITED_MSG: NotificationCorpAppInvitedMsg,
            NT.CORP_APP_REJECT_CUSTOM_MSG: NotificationCorpAppRejectCustomMsg,
            NT.CHAR_APP_WITHDRAW_MSG: NotificationCharAppWithdrawMsg,
            NT.CHAR_APP_ACCEPT_MSG: NotificationCharAppAcceptMsg,
            NT.CHAR_LEFT_CORP_MSG: NotificationCharLeftCorpMsg,
            # moonmining
            NT.MOONMINING_EXTRACTION_STARTED: NotificationMoonminningExtractionStarted,
            NT.MOONMINING_EXTRACTION_FINISHED: NotificationMoonminningExtractionFinished,
            NT.MOONMINING_AUTOMATIC_FRACTURE: NotificationMoonminningAutomaticFracture,
            NT.MOONMINING_EXTRACTION_CANCELLED: NotificationMoonminningExtractionCanceled,
            NT.MOONMINING_LASER_FIRED: NotificationMoonminningLaserFired,
            # upwell structures
            NT.STRUCTURE_ONLINE: NotificationStructureOnline,
            NT.STRUCTURE_FUEL_ALERT: NotificationStructureFuelAlert,
            NT.STRUCTURE_JUMP_FUEL_ALERT: NotificationStructureJumpFuelAlert,
            NT.STRUCTURE_REFUELED_EXTRA: NotificationStructureRefueledExtra,
            NT.STRUCTURE_SERVICES_OFFLINE: NotificationStructureServicesOffline,
            NT.STRUCTURE_WENT_LOW_POWER: NotificationStructureWentLowPower,
            NT.STRUCTURE_WENT_HIGH_POWER: NotificationStructureWentHighPower,
            NT.STRUCTURE_UNANCHORING: NotificationStructureUnanchoring,
            NT.STRUCTURE_UNDER_ATTACK: NotificationStructureUnderAttack,
            NT.STRUCTURE_LOST_SHIELD: NotificationStructureLostShield,
            NT.STRUCTURE_LOST_ARMOR: NotificationStructureLostArmor,
            NT.STRUCTURE_DESTROYED: NotificationStructureDestroyed,
            NT.OWNERSHIP_TRANSFERRED: NotificationStructureOwnershipTransferred,
            NT.STRUCTURE_ANCHORING: NotificationStructureAnchoring,
            NT.STRUCTURE_REINFORCE_CHANGED: NotificationStructureReinforceChange,
            # Orbitals
            NT.ORBITAL_ATTACKED: NotificationOrbitalAttacked,
            NT.ORBITAL_REINFORCED: NotificationOrbitalReinforced,
            # Towers
            NT.TOWER_ALERT_MSG: NotificationTowerAlertMsg,
            NT.TOWER_RESOURCE_ALERT_MSG: NotificationTowerResourceAlertMsg,
            NT.TOWER_REFUELED_EXTRA: NotificationTowerRefueledExtra,
            NT.TOWER_REINFORCED_EXTRA: NotificationTowerReinforcedExtra,
            # Sov
            NT.SOV_ENTOSIS_CAPTURE_STARTED: NotificationSovEntosisCaptureStarted,
            NT.SOV_COMMAND_NODE_EVENT_STARTED: NotificationSovCommandNodeEventStarted,
            NT.SOV_ALL_CLAIM_ACQUIRED_MSG: NotificationSovAllClaimAcquiredMsg,
            NT.SOV_ALL_CLAIM_LOST_MSG: NotificationSovAllClaimLostMsg,
            NT.SOV_STRUCTURE_REINFORCED: NotificationSovStructureReinforced,
            NT.SOV_STRUCTURE_DESTROYED: NotificationSovStructureDestroyed,
            NT.SOV_ALL_ANCHORING_MSG: NotificationSovAllAnchoringMsg,
            # War
            NT.WAR_ALLY_JOINED_WAR_AGGRESSOR_MSG: NotificationAllyJoinedWarMsg,
            NT.WAR_ALLY_JOINED_WAR_ALLY_MSG: NotificationAllyJoinedWarMsg,
            NT.WAR_ALLY_JOINED_WAR_DEFENDER_MSG: NotificationAllyJoinedWarMsg,
            NT.WAR_CORP_WAR_SURRENDER_MSG: NotificationCorpWarSurrenderMsg,
            NT.WAR_WAR_ADOPTED: NotificationWarAdopted,
            NT.WAR_WAR_DECLARED: NotificationWarDeclared,
            NT.WAR_WAR_INHERITED: NotificationWarInherited,
            NT.WAR_WAR_RETRACTED_BY_CONCORD: NotificationWarRetractedByConcord,
            NT.WAR_CORPORATION_BECAME_ELIGIBLE: NotificationWarCorporationBecameEligible,
            NT.WAR_CORPORATION_NO_LONGER_ELIGIBLE: NotificationWarCorporationNoLongerEligible,
            NT.WAR_WAR_SURRENDER_OFFER_MSG: NotificationWarSurrenderOfferMsg,
            # Billing
            NT.BILLING_BILL_OUT_OF_MONEY_MSG: NotificationBillingBillOutOfMoneyMsg,
            NT.BILLING_I_HUB_BILL_ABOUT_TO_EXPIRE: NotificationBillingIHubBillAboutToExpire,
            NT.BILLING_I_HUB_DESTROYED_BY_BILL_FAILURE: NotificationBillingIHubDestroyedByBillFailure,
        }
        try:
            return notif_type_2_class[notification.notif_type](notification)
        except KeyError:
            raise NotImplementedError(repr(notification.notif_type)) from None

    def _compile_damage_text(self, field_postfix: str, factor: int = 1) -> str:
        """Compile damage text for Structures and POSes"""
        damage_labels = [
            ("shield", __("shield")),
            ("armor", __("armor")),
            ("hull", __("hull")),
        ]
        damage_parts = []
        for prop in damage_labels:
            field_name = f"{prop[0]}{field_postfix}"
            if field_name in self._parsed_text:
                label = prop[1]
                value = self._parsed_text[field_name] * factor
                damage_parts.append(f"{label}: {value:.1f}%")
        damage_text = " | ".join(damage_parts)
        return damage_text

    @staticmethod
    def _gen_solar_system_text(solar_system: EveSolarSystem) -> str:
        solar_system_link = Webhook.create_link(
            solar_system.name, dotlan.solar_system_url(solar_system.name)
        )
        region_name = solar_system.eve_constellation.eve_region.name
        text = f"{solar_system_link} ({region_name})"
        return text

    @staticmethod
    def _gen_alliance_link(alliance_name: str) -> str:
        return Webhook.create_link(alliance_name, dotlan.alliance_url(alliance_name))

    @staticmethod
    def _gen_eve_entity_external_url(eve_entity: EveEntity) -> str:
        if eve_entity.category == EveEntity.CATEGORY_ALLIANCE:
            return dotlan.alliance_url(eve_entity.name)

        if eve_entity.category == EveEntity.CATEGORY_CORPORATION:
            return dotlan.corporation_url(eve_entity.name)

        if eve_entity.category == EveEntity.CATEGORY_CHARACTER:
            return evewho.character_url(eve_entity.id)

        return ""

    @classmethod
    def _gen_eve_entity_link(cls, eve_entity: EveEntity) -> str:
        return Webhook.create_link(
            eve_entity.name, cls._gen_eve_entity_external_url(eve_entity)
        )

    @classmethod
    def _gen_eve_entity_link_from_id(cls, id: int) -> str:
        if not id:
            return ""
        entity, _ = EveEntity.objects.get_or_create_esi(id=id)
        return cls._gen_eve_entity_link(entity)

    @staticmethod
    def _gen_corporation_link(corporation_name: str) -> str:
        return Webhook.create_link(
            corporation_name, dotlan.corporation_url(corporation_name)
        )

    def _get_aggressor_link(self) -> str:
        """Returns the aggressor link from a parsed_text for POS and POCOs only."""
        if self._parsed_text.get("aggressorAllianceID"):
            key = "aggressorAllianceID"
        elif self._parsed_text.get("aggressorCorpID"):
            key = "aggressorCorpID"
        elif self._parsed_text.get("aggressorID"):
            key = "aggressorID"
        else:
            return "(Unknown aggressor)"
        entity, _ = EveEntity.objects.get_or_create_esi(id=self._parsed_text[key])
        return Webhook.create_link(entity.name, entity.profile_url)


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
            owner_link = self._gen_corporation_link(str(structure.owner))
            location = f" at {structure.eve_moon} " if structure.eve_moon else ""

        self._structure = structure
        self._description = __(
            "The %(structure_type)s %(structure_name)s%(location)s in %(solar_system)s "
            "belonging to %(owner_link)s "
        ) % {
            "structure_type": structure_type.name,
            "structure_name": Webhook.text_bold(structure_name),
            "location": location,
            "solar_system": self._gen_solar_system_text(structure_solar_system),
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
        if self._structure and self._structure.fuel_expires_at:
            target_date = target_datetime_formatted(self._structure.fuel_expires_at)
        else:
            target_date = "?"
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
            self._compile_damage_text("Percentage"),
        )
        self._color = Webhook.Color.DANGER

    def _get_attacker_link(self) -> str:
        """Returns the attacker link from a parsed_text for Upwell structures only."""
        if self._parsed_text.get("allianceName"):
            return self._gen_alliance_link(self._parsed_text["allianceName"])

        if self._parsed_text.get("corpName"):
            return self._gen_corporation_link(self._parsed_text["corpName"])

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
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=self._parsed_text["structureTypeID"]
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=self._parsed_text["solarSystemID"]
        )
        self._description = __(
            "The %(structure_type)s %(structure_name)s in %(solar_system)s "
        ) % {
            "structure_type": structure_type.name,
            "structure_name": Webhook.text_bold(self._parsed_text["structureName"]),
            "solar_system": self._gen_solar_system_text(solar_system),
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
            "from_corporation": self._gen_corporation_link(from_corporation.name),
            "to_corporation": self._gen_corporation_link(to_corporation.name),
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
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=self._parsed_text["structureTypeID"]
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=self._parsed_text["solarsystemID"]
        )
        owner_link = self._gen_corporation_link(
            self._parsed_text.get("ownerCorpName", "(unknown)")
        )
        self._description = __(
            "A %(structure_type)s belonging to %(owner_link)s "
            "has started anchoring in %(solar_system)s. "
        ) % {
            "structure_type": structure_type.name,
            "owner_link": owner_link,
            "solar_system": self._gen_solar_system_text(solar_system),
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
                        owner_link=self._gen_corporation_link(str(structure.owner)),
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
                "solar_system": self._gen_solar_system_text(
                    structure_info.eve_solar_system
                ),
                "owner_link": structure_info.owner_link,
            }

        self._description += __(
            "\n\nChange becomes effective at %s."
        ) % target_datetime_formatted(change_effective)
        self._color = Webhook.Color.INFO


class NotificationMoonminingEmbed(NotificationBaseEmbed):
    """Base class for all moon mining related notification embeds."""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._moon, _ = EveMoon.objects.get_or_create_esi(
            id=self._parsed_text["moonID"]
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=self._parsed_text["solarSystemID"]
        )
        self._solar_system_link = self._gen_solar_system_text(solar_system)
        self._structure_name = self._parsed_text["structureName"]
        self._owner_link = self._gen_corporation_link(str(notification.owner))
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=self._parsed_text["structureTypeID"]
        )
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )
        self.ore_text = (
            __("\nEstimated ore composition: %s") % self._ore_composition_text()
            if STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
            else ""
        )

    def _ore_composition_text(self) -> str:
        if "oreVolumeByType" not in self._parsed_text:
            return ""

        ore_list = []
        for ore_type_id, volume in self._parsed_text["oreVolumeByType"].items():
            ore_type, _ = EveType.objects.get_or_create_esi(id=ore_type_id)
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
        started_by, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["startedBy"]
        )
        ready_time = ldap_time_2_datetime(self._parsed_text["readyTime"])
        auto_time = ldap_time_2_datetime(self._parsed_text["autoTime"])
        self._title = __("Moon mining extraction started")
        self._description = __(
            "A moon mining extraction has been started "
            "for %(structure_name)s at %(moon)s in %(solar_system)s "
            "belonging to %(owner_link)s. "
            "Extraction was started by %(character)s.\n"
            "The chunk will be ready on location at %(ready_time)s, "
            "and will fracture automatically on %(auto_time)s.\n"
            "%(ore_text)s"
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
        self._title = __("Extraction finished")
        self._description = __(
            "The extraction for %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
            "is finished and the chunk is ready "
            "to be shot at.\n"
            "The chunk will automatically fracture on %(auto_time)s.\n"
            "%(ore_text)s"
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
        self._title = __("Automatic Fracture")
        self._description = __(
            "The moon drill fitted to %(structure_name)s at %(moon)s"
            " in %(solar_system)s belonging to %(owner_link)s "
            "has automatically been fired "
            "and the moon products are ready to be harvested.\n"
            "%(ore_text)s"
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
            cancelled_by, _ = EveEntity.objects.get_or_create_esi(
                id=self._parsed_text["cancelledBy"]
            )
        else:
            cancelled_by = __("(unknown)")
        self._title = __("Extraction cancelled")
        self._description = __(
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
        fired_by, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["firedBy"]
        )
        self._title = __("Moon drill fired")
        self._description = __(
            "The moon drill fitted to %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
            "has been fired by %(character)s "
            "and the moon products are ready to be harvested.\n"
            "%(ore_text)s"
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "character": fired_by,
            "ore_text": self.ore_text,
        }
        self._color = Webhook.Color.SUCCESS


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
        self._solar_system_link = self._gen_solar_system_text(solar_system)
        self._owner_link = self._gen_corporation_link(str(notification.owner))
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
            "solar_system": self._gen_solar_system_text(
                self.eve_moon.eve_planet.eve_solar_system
            ),
            "owner_link": self._gen_corporation_link(str(notification.owner)),
        }


class NotificationTowerAlertMsg(NotificationTowerEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        aggressor_link = self._get_aggressor_link()
        damage_text = self._compile_damage_text("Value", 100)
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
        if self._structure and self._structure.fuel_expires_at:
            target_date = target_datetime_formatted(self._structure.fuel_expires_at)
        else:
            target_date = "?"
        self._title = __("Starbase refueled")
        self._description += (
            __("has been refueled. Fuel will last until %s.") % target_date
        )
        self._color = Webhook.Color.INFO


class NotificationSovEmbed(NotificationBaseEmbed):
    """Base class for all sovereignty related notification embeds."""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=self._parsed_text["solarSystemID"]
        )
        self._solar_system_link = self._gen_solar_system_text(self._solar_system)
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
            self._sov_owner_link = self._gen_alliance_link(notification.sender.name)
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
            "corporation": self._gen_corporation_link(corporation.name),
            "alliance": self._gen_alliance_link(alliance.name),
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
            "corporation": self._gen_corporation_link(corporation.name),
            "alliance": self._gen_alliance_link(alliance.name),
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
        corp_link = self._gen_eve_entity_link(corporation)
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
            "solar_system": self._gen_solar_system_text(eve_solar_system),
            "location_text": location_text,
        }
        self._color = Webhook.Color.WARNING
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationCorpCharEmbed(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._character, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["charID"]
        )
        self._corporation, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["corpID"]
        )
        self._character_link = self._gen_eve_entity_link(self._character)
        self._corporation_link = self._gen_corporation_link(self._corporation.name)
        self._application_text = self._parsed_text.get("applicationText", "")
        self._thumbnail = dhooks_lite.Thumbnail(
            self._character.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationCorpAppNewMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("New application from %(character_name)s") % {
            "character_name": self._character.name,
        }
        self._description = __(
            "New application from %(character_name)s to join %(corporation_name)s:\n"
            "> %(application_text)s"
            % {
                "character_name": self._character_link,
                "corporation_name": self._corporation_link,
                "application_text": self._application_text,
            }
        )
        self._color = Webhook.Color.INFO


class NotificationCorpAppInvitedMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("%(character_name)s has been invited") % {
            "character_name": self._character.name
        }
        inviting_character = self._gen_eve_entity_link_from_id(
            self._parsed_text.get("invokingCharID")
        )
        self._description = __(
            "%(character_name)s has been invited to join %(corporation_name)s "
            "by %(inviting_character)s.\n"
            "Application:\n"
            "> %(application_text)s"
        ) % {
            "character_name": self._character_link,
            "corporation_name": self._corporation_link,
            "inviting_character": inviting_character,
            "application_text": self._application_text,
        }

        self._color = Webhook.Color.INFO


class NotificationCorpAppRejectCustomMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Rejected application from %(character_name)s") % {
            "character_name": self._character.name
        }
        self._description = __(
            "Application from %(character_name)s to join %(corporation_name)s:\n"
            "> %(application_text)s\n"
            "Has been rejected:\n"
            "> %(customMessage)s"
        ) % {
            "character_name": self._character_link,
            "corporation_name": self._corporation_link,
            "application_text": self._application_text,
            "customMessage": self._parsed_text.get("customMessage", ""),
        }

        self._color = Webhook.Color.INFO


class NotificationCharAppWithdrawMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("%(character_name)s withdrew his/her application") % {
            "character_name": self._character.name,
        }
        self._description = __(
            "%(character_name)s withdrew his/her application to join "
            "%(corporation_name)s:\n"
            "> %(application_text)s"
        ) % {
            "character_name": self._character_link,
            "corporation_name": self._corporation_link,
            "application_text": self._application_text,
        }

        self._color = Webhook.Color.INFO


class NotificationCharAppAcceptMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("%(character_name)s joins %(corporation_name)s") % {
            "character_name": self._character.name,
            "corporation_name": self._corporation.name,
        }
        self._description = __(
            "%(character_name)s is now a member of %(corporation_name)s."
        ) % {
            "character_name": self._character_link,
            "corporation_name": self._corporation_link,
        }
        self._color = Webhook.Color.SUCCESS


class NotificationCharLeftCorpMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("%(character_name)s has left %(corporation_name)s") % {
            "character_name": self._character.name,
            "corporation_name": self._corporation.name,
        }
        self._description = __(
            "%(character_name)s is no longer a member of %(corporation_name)s."
        ) % {
            "character_name": self._character_link,
            "corporation_name": self._corporation_link,
        }
        self._color = Webhook.Color.INFO


class NotificationAllyJoinedWarMsg(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("Ally Has Joined a War")
        aggressor, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["aggressorID"]
        )
        ally, _ = EveEntity.objects.get_or_create_esi(id=self._parsed_text["allyID"])
        defender, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["defenderID"]
        )
        start_time = ldap_time_2_datetime(self._parsed_text["startTime"])
        self._description = __(
            "%(ally)s has joined %(defender)s in a war against %(aggressor)s. "
            "Their participation in the war will start at %(start_time)s."
        ) % {
            "aggressor": self._gen_eve_entity_link(aggressor),
            "ally": self._gen_eve_entity_link(ally),
            "defender": self._gen_eve_entity_link(defender),
            "start_time": target_datetime_formatted(start_time),
        }
        self._thumbnail = dhooks_lite.Thumbnail(
            ally.icon_url(size=self.ICON_DEFAULT_SIZE)
        )
        self._color = Webhook.Color.WARNING


class NotificationWarEmbed(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._declared_by, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["declaredByID"]
        )
        self._against, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["againstID"]
        )
        self._thumbnail = dhooks_lite.Thumbnail(
            self._declared_by.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationCorpWarSurrenderMsg(NotificationWarEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("One party has surrendered")
        self._description = __(
            "The war between %(against)s and %(declared_by)s is coming to an end "
            "as one party has surrendered. "
            "The war will be declared as being over after approximately 24 hours."
        ) % {
            "declared_by": self._gen_eve_entity_link(self._declared_by),
            "against": self._gen_eve_entity_link(self._against),
        }
        self._color = Webhook.Color.WARNING


class NotificationWarAdopted(NotificationWarEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        alliance, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["allianceID"]
        )
        self._title = __("War update: %(against)s has left %(alliance)s") % {
            "against": self._against.name,
            "alliance": alliance.name,
        }
        self._description = __(
            "There has been a development in the war between %(declared_by)s "
            "and %(alliance)s.\n"
            "%(against)s is no longer a member of %(alliance)s, "
            "and therefore a new war between %(declared_by)s and %(against)s has begun."
        ) % {
            "declared_by": self._gen_eve_entity_link(self._declared_by),
            "against": self._gen_eve_entity_link(self._against),
            "alliance": self._gen_eve_entity_link(alliance),
        }
        self._color = Webhook.Color.WARNING


class NotificationWarDeclared(NotificationWarEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("%(declared_by)s Declares War Against %(against)s") % {
            "declared_by": self._declared_by.name,
            "against": self._against.name,
        }
        self._description = __(
            "%(declared_by)s has declared war on %(against)s with %(war_hq)s "
            "as the designated war headquarters.\n"
            "Within %(delay_hours)s hours fighting can legally occur "
            "between those involved."
        ) % {
            "declared_by": self._gen_eve_entity_link(self._declared_by),
            "against": self._gen_eve_entity_link(self._against),
            "war_hq": Webhook.text_bold(strip_tags(self._parsed_text["warHQ"])),
            "delay_hours": Webhook.text_bold(self._parsed_text["delayHours"]),
        }
        self._color = Webhook.Color.DANGER


class NotificationWarInherited(NotificationWarEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        alliance, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["allianceID"]
        )
        opponent, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["opponentID"]
        )
        quitter, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["quitterID"]
        )
        self._title = __("%(alliance)s inherits war against %(opponent)s") % {
            "alliance": alliance.name,
            "opponent": opponent.name,
        }
        self._description = __(
            "%(alliance)s has inherited the war between %(declared_by)s and "
            "%(against)s from newly joined %(quitter)s. "
            "Within **24** hours fighting can legally occur with %(alliance)s."
        ) % {
            "declared_by": self._gen_eve_entity_link(self._declared_by),
            "against": self._gen_eve_entity_link(self._against),
            "alliance": self._gen_eve_entity_link(alliance),
            "quitter": self._gen_eve_entity_link(quitter),
        }
        self._color = Webhook.Color.DANGER


class NotificationWarRetractedByConcord(NotificationWarEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __("CONCORD invalidates war")
        war_ends = ldap_time_2_datetime(self._parsed_text["endDate"])
        self._description = __(
            "The war between %(declared_by)s and %(against)s "
            "has been retracted by CONCORD.\n"
            "After %(end_date)s CONCORD will again respond to any hostilities "
            "between those involved with full force."
        ) % {
            "declared_by": self._gen_eve_entity_link(self._declared_by),
            "against": self._gen_eve_entity_link(self._against),
            "end_date": target_datetime_formatted(war_ends),
        }
        self._color = Webhook.Color.WARNING


class NotificationWarCorporationBecameEligible(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __(
            "Corporation or alliance is now eligible for formal war declarations"
        )
        self._description = __(
            "Your corporation or alliance is **now eligible** to participate in "
            "formal war declarations. This could be because your corporation "
            "and/or one of the corporations in your alliance owns a structure "
            "deployed in space."
        )
        self._color = Webhook.Color.WARNING


class NotificationWarCorporationNoLongerEligible(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = __(
            "Corporation or alliance is no longer eligible for formal war declarations"
        )
        self._description = __(
            "Your corporation or alliance is **no longer eligible** to participate "
            "in formal war declarations.\n"
            "Neither your corporation nor any of the corporations "
            "in your alliance own a structure deployed in space at this time. "
            "If your corporation or alliance is currently involved in a formal war, "
            "that war will end in 24 hours."
        )
        self._color = Webhook.Color.INFO


class NotificationWarSurrenderOfferMsg(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        isk_value = self._parsed_text.get("iskValue", 0)
        owner_1, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text.get("ownerID1")
        )
        owner_1_link = self._gen_eve_entity_link(owner_1)
        owner_2_link = self._gen_eve_entity_link_from_id(
            self._parsed_text.get("ownerID2")
        )
        self._title = __("%s has offered a surrender") % (owner_1,)
        self._description = __(
            "%s has offered to end the war with %s in the exchange for %s ISK. "
            "If accepted, the war will end in 24 hours and your organizations will "
            "be unable to declare new wars against each other for the next 2 weeks."
        ) % (owner_1_link, owner_2_link, f"{isk_value:,.2f}")
        self._color = Webhook.Color.INFO


class NotificationBillingBillOutOfMoneyMsg(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        bill_type_id = self._parsed_text["billTypeID"]
        bill_type_str = BillType.to_enum(bill_type_id).label
        due_date = ldap_time_2_datetime(self._parsed_text["dueDate"])
        self._title = __("Insufficient Funds for Bill")
        self._description = __(
            "The selected corporation wallet division for automatic payments "
            "does not have enough current funds available to pay the %(bill_type)s "
            "due to be paid by %(due_date)s. "
            "Transfer additional funds to the selected wallet "
            "division in order to meet your pending automatic bills."
        ) % {
            "bill_type": bill_type_str,
            "due_date": target_datetime_formatted(due_date),
        }
        self._color = Webhook.Color.WARNING


class NotificationBillingIHubBillAboutToExpire(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=self._parsed_text["solarSystemID"]
        )
        solar_system_link = self._gen_solar_system_text(solar_system)
        due_date = ldap_time_2_datetime(self._parsed_text.get("dueDate"))
        self._title = __("IHub Bill About to Expire")
        self._description = __(
            "Maintenance bill for Infrastructure Hub in %(solar_system)s "
            "expires at %(due_date)s, "
            "if not paid in time this Infrastructure Hub will self-destruct."
        ) % {
            "solar_system": solar_system_link,
            "due_date": target_datetime_formatted(due_date),
        }
        self._color = Webhook.Color.DANGER
        structure_type, _ = EveType.objects.get_or_create_esi(id=EveTypeId.IHUB)
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationBillingIHubDestroyedByBillFailure(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        structure_type, _ = EveType.objects.get_or_create_esi(
            id=self._parsed_text["structureTypeID"]
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=self._parsed_text["solarSystemID"]
        )
        solar_system_link = self._gen_solar_system_text(solar_system)
        self._title = (
            __("%s has self-destructed due to unpaid maintenance bills")
            % structure_type.name
        )
        self._description = __(
            "%(structure_type)s in %(solar_system)s has self-destructed, "
            "as the standard maintenance bills where not paid."
        ) % {"structure_type": structure_type.name, "solar_system": solar_system_link}
        self._color = Webhook.Color.DANGER
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


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
            "solar_system": self._gen_solar_system_text(
                self._structure.eve_solar_system
            ),
            "owner_link": self._gen_corporation_link(str(notification.owner)),
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
