import datetime as dt
from collections import namedtuple

import dhooks_lite

from django.conf import settings
from django.template import Context, Template
from django.utils.html import strip_tags
from django.utils.translation import gettext

from allianceauth.eveonline.evelinks import dotlan, evewho
from app_utils.datetime import (
    DATETIME_FORMAT,
    ldap_time_2_datetime,
    ldap_timedelta_2_timedelta,
)
from app_utils.urls import reverse_absolute, static_file_absolute_url

from .. import __title__
from ..app_settings import STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
from ..constants import EveTypeId
from ..models.eveuniverse import EveMoon, EvePlanet, EveSolarSystem, EveType
from ..models.notifications import EveEntity, Notification, NotificationType, Webhook
from ..models.structures import Structure


def timeuntil(target_datetime: dt.datetime) -> str:
    """Render timeuntil template tag for given datetime to string."""
    template = Template("{{ my_datetime|timeuntil }}")
    context = Context({"my_datetime": target_datetime})
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
        if not isinstance(notification, Notification):
            raise TypeError("notification must be of type Notification")
        self._notification = notification
        self._parsed_text = notification.get_parsed_text()
        self._title = None
        self._description = ""
        self._color = None
        self._thumbnail = None
        self._ping_type = None

    def __str__(self) -> str:
        return str(self.notification)

    def __repr__(self) -> str:
        return "%s(notification=%r)" % (self.__class__.__name__, self.notification)

    @property
    def notification(self) -> Notification:
        return self._notification

    @property
    def ping_type(self) -> Webhook.PingType:
        return self._ping_type

    def generate_embed(self) -> dhooks_lite.Embed:
        """Returns generated Discord embed for this object.

        Will use custom color for embeds if self.notification has the \
            property "color_override" defined

        Will use custom ping type if self.notification has the \
            property "ping_type_override" defined

        """
        if self._title is None:
            raise ValueError(f"title not defined for {type(self)}")
        if self._description is None:
            raise ValueError(f"description not defined for {type(self)}")
        corporation = self.notification.owner.corporation
        if self.notification.is_alliance_level and corporation.alliance:
            author_name = corporation.alliance.alliance_name
            author_url = corporation.alliance.logo_url(size=self.ICON_DEFAULT_SIZE)
        else:
            author_name = corporation.corporation_name
            author_url = corporation.logo_url(size=self.ICON_DEFAULT_SIZE)
        app_url = reverse_absolute("structures:index")
        author = dhooks_lite.Author(name=author_name, icon_url=author_url, url=app_url)
        if hasattr(self.notification, "color_override"):
            self._color = self.notification.color_override
        if hasattr(self.notification, "ping_type_override"):
            self._ping_type = self.notification.ping_type_override
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
            footer_text += " #{}".format(
                self.notification.notification_id
                if not self.notification.is_generated
                else "GENERATED"
            )
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
    def create(notification: Notification) -> "NotificationBaseEmbed":
        """Creates a new instance of the respective subclass for given Notification."""
        if not isinstance(notification, Notification):
            raise TypeError("notification must be of type Notification")
        notif_type = notification.notif_type

        # character
        if notif_type == NotificationType.CORP_APP_NEW_MSG:
            return NotificationCorpAppNewMsg(notification)
        elif notif_type == NotificationType.CORP_APP_INVITED_MSG:
            return NotificationCorpAppInvitedMsg(notification)
        elif notif_type == NotificationType.CORP_APP_REJECT_CUSTOM_MSG:
            return NotificationCorpAppRejectCustomMsg(notification)
        elif notif_type == NotificationType.CHAR_APP_WITHDRAW_MSG:
            return NotificationCharAppWithdrawMsg(notification)
        elif notif_type == NotificationType.CHAR_APP_ACCEPT_MSG:
            return NotificationCharAppAcceptMsg(notification)
        elif notif_type == NotificationType.CHAR_LEFT_CORP_MSG:
            return NotificationCharLeftCorpMsg(notification)

        # moonmining
        elif notif_type == NotificationType.MOONMINING_EXTRACTION_STARTED:
            return NotificationMoonminningExtractionStarted(notification)
        elif notif_type == NotificationType.MOONMINING_EXTRACTION_FINISHED:
            return NotificationMoonminningExtractionFinished(notification)
        elif notif_type == NotificationType.MOONMINING_AUTOMATIC_FRACTURE:
            return NotificationMoonminningAutomaticFracture(notification)
        elif notif_type == NotificationType.MOONMINING_EXTRACTION_CANCELLED:
            return NotificationMoonminningExtractionCanceled(notification)
        elif notif_type == NotificationType.MOONMINING_LASER_FIRED:
            return NotificationMoonminningLaserFired(notification)

        # upwell structures
        elif notif_type == NotificationType.STRUCTURE_ONLINE:
            return NotificationStructureOnline(notification)
        elif notif_type == NotificationType.STRUCTURE_FUEL_ALERT:
            return NotificationStructureFuelAlert(notification)
        elif notif_type == NotificationType.STRUCTURE_JUMP_FUEL_ALERT:
            return NotificationStructureJumpFuelAlert(notification)
        elif notif_type == NotificationType.STRUCTURE_REFUELED_EXTRA:
            return NotificationStructureRefuledExtra(notification)
        elif notif_type == NotificationType.STRUCTURE_SERVICES_OFFLINE:
            return NotificationStructureServicesOffline(notification)
        elif notif_type == NotificationType.STRUCTURE_WENT_LOW_POWER:
            return NotificationStructureWentLowPower(notification)
        elif notif_type == NotificationType.STRUCTURE_WENT_HIGH_POWER:
            return NotificationStructureWentHighPower(notification)
        elif notif_type == NotificationType.STRUCTURE_UNANCHORING:
            return NotificationStructureUnanchoring(notification)
        elif notif_type == NotificationType.STRUCTURE_UNDER_ATTACK:
            return NotificationStructureUnderAttack(notification)
        elif notif_type == NotificationType.STRUCTURE_LOST_SHIELD:
            return NotificationStructureLostShield(notification)
        elif notif_type == NotificationType.STRUCTURE_LOST_ARMOR:
            return NotificationStructureLostArmor(notification)
        elif notif_type == NotificationType.STRUCTURE_DESTROYED:
            return NotificationStructureDestroyed(notification)
        elif notif_type == NotificationType.OWNERSHIP_TRANSFERRED:
            return NotificationStructureOwnershipTransferred(notification)
        elif notif_type == NotificationType.STRUCTURE_ANCHORING:
            return NotificationStructureAnchoring(notification)
        elif notif_type == NotificationType.STRUCTURE_REINFORCE_CHANGED:
            return NotificationStructureReinforceChange(notification)

        # Orbitals
        elif notif_type == NotificationType.ORBITAL_ATTACKED:
            return NotificationOrbitalAttacked(notification)
        elif notif_type == NotificationType.ORBITAL_REINFORCED:
            return NotificationOrbitalReinforced(notification)

        # Towers
        elif notif_type == NotificationType.TOWER_ALERT_MSG:
            return NotificationTowerAlertMsg(notification)
        elif notif_type == NotificationType.TOWER_RESOURCE_ALERT_MSG:
            return NotificationTowerResourceAlertMsg(notification)
        elif notif_type == NotificationType.TOWER_REFUELED_EXTRA:
            return NotificationTowerRefueledExtra(notification)

        # Sov
        elif notif_type == NotificationType.SOV_ENTOSIS_CAPTURE_STARTED:
            return NotificationSovEntosisCaptureStarted(notification)
        elif notif_type == NotificationType.SOV_COMMAND_NODE_EVENT_STARTED:
            return NotificationSovCommandNodeEventStarted(notification)
        elif notif_type == NotificationType.SOV_ALL_CLAIM_ACQUIRED_MSG:
            return NotificationSovAllClaimAcquiredMsg(notification)
        elif notif_type == NotificationType.SOV_ALL_CLAIM_LOST_MSG:
            return NotificationSovAllClaimLostMsg(notification)
        elif notif_type == NotificationType.SOV_STRUCTURE_REINFORCED:
            return NotificationSovStructureReinforced(notification)
        elif notif_type == NotificationType.SOV_STRUCTURE_DESTROYED:
            return NotificationSovStructureDestroyed(notification)

        # War
        elif notif_type in [
            NotificationType.WAR_ALLY_JOINED_WAR_AGGRESSOR_MSG,
            NotificationType.WAR_ALLY_JOINED_WAR_AllY_MSG,
            NotificationType.WAR_ALLY_JOINED_WAR_DEFENDER_MSG,
        ]:
            return NotificationAllyJoinedWarMsg(notification)
        elif notif_type == NotificationType.WAR_CORP_WAR_SURRENDER_MSG:
            return NotificationCorpWarSurrenderMsg(notification)
        elif notif_type == NotificationType.WAR_WAR_ADOPTED:
            return NotificationWarAdopted(notification)
        elif notif_type == NotificationType.WAR_WAR_DECLARED:
            return NotificationWarDeclared(notification)
        elif notif_type == NotificationType.WAR_WAR_INHERITED:
            return NotificationWarInherited(notification)
        elif notif_type == NotificationType.WAR_WAR_RETRACTED_BY_CONCORD:
            return NotificationWarRetractedByConcord(notification)
        elif notif_type == NotificationType.WAR_CORPORATION_BECAME_ELIGIBLE:
            return NotificationWarCorporationBecameEligible(notification)
        elif notif_type == NotificationType.WAR_CORPORATION_NO_LONGER_ELIGIBLE:
            return NotificationWarCorporationNoLongerEligible(notification)

        # NOT IMPLEMENTED
        else:
            raise NotImplementedError(repr(notif_type))

    @staticmethod
    def _gen_solar_system_text(solar_system: EveSolarSystem) -> str:
        text = "{} ({})".format(
            Webhook.create_link(
                solar_system.name_localized, dotlan.solar_system_url(solar_system.name)
            ),
            solar_system.eve_constellation.eve_region.name_localized,
        )
        return text

    @staticmethod
    def _gen_alliance_link(alliance_name: str) -> str:
        return Webhook.create_link(alliance_name, dotlan.alliance_url(alliance_name))

    @staticmethod
    def _gen_eveentity_external_url(eve_entity: EveEntity) -> str:
        if eve_entity.category == EveEntity.Category.ALLIANCE:
            return dotlan.alliance_url(eve_entity.name)
        elif eve_entity.category == EveEntity.Category.CORPORATION:
            return dotlan.corporation_url(eve_entity.name)
        elif eve_entity.category == EveEntity.Category.CHARACTER:
            return evewho.character_url(eve_entity.id)

    @classmethod
    def _gen_eveentity_link(cls, eve_entity: EveEntity) -> str:
        return Webhook.create_link(
            eve_entity.name, cls._gen_eveentity_external_url(eve_entity)
        )

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

        entity, _ = EveEntity.objects.get_or_create_esi(self._parsed_text[key])
        return Webhook.create_link(entity.name, entity.profile_url())


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
            structure_name = gettext("(unknown)")
            structure_type, _ = EveType.objects.get_or_create_esi(
                self._parsed_text["structureTypeID"]
            )
            structure_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                self._parsed_text["solarsystemID"]
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
        self._description = gettext(
            "The %(structure_type)s %(structure_name)s%(location)s in %(solar_system)s "
            "belonging to %(owner_link)s "
        ) % {
            "structure_type": structure_type.name_localized,
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
        self._title = gettext("Structure online")
        self._description += gettext("is now online.")
        self._color = Webhook.Color.SUCCESS


class NotificationStructureFuelAlert(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        if self._structure and self._structure.fuel_expires_at:
            hours_left = timeuntil(self._structure.fuel_expires_at)
        else:
            hours_left = "?"
        self._title = gettext("Structure fuel alert")
        self._description += gettext(
            "is running out of fuel in %s." % Webhook.text_bold(hours_left)
        )
        self._color = Webhook.Color.WARNING


class NotificationStructureJumpFuelAlert(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Jump gate low on Liquid Ozone")
        threshold_str = f"{self._parsed_text['threshold']:,}"
        quantity_str = f"{self._structure.jump_fuel_quantity():,}"
        self._description += gettext(
            "is below %(threshold)s units on Liquid Ozone.\n"
            "Remaining units: %(remaining)s."
            % {
                "threshold": f"{Webhook.text_bold(threshold_str)}",
                "remaining": f"{Webhook.text_bold(quantity_str)}",
            }
        )
        self._color = Webhook.Color.WARNING


class NotificationStructureRefuledExtra(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        if self._structure and self._structure.fuel_expires_at:
            target_date = target_datetime_formatted(self._structure.fuel_expires_at)
        else:
            target_date = "?"
        self._title = gettext("Structure refueled")
        self._description += gettext(
            "has been refueled. Fuel will last until %s." % target_date
        )
        self._color = Webhook.Color.INFO


class NotificationStructureServicesOffline(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure services off-line")
        self._description += gettext("has all services off-lined.")
        if self._structure and self._structure.services.count() > 0:
            qs = self._structure.services.all().order_by("name")
            services_list = "\n".join([x.name for x in qs])
            self._description += "\n*{}*".format(services_list)
        self._color = Webhook.Color.DANGER


class NotificationStructureWentLowPower(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure low power")
        self._description += gettext("went to low power mode.")
        self._color = Webhook.Color.WARNING


class NotificationStructureWentHighPower(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure full power")
        self._description += gettext("went to full power mode.")
        self._color = Webhook.Color.SUCCESS


class NotificationStructureUnanchoring(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure un-anchoring")
        unanchored_at = notification.timestamp + ldap_timedelta_2_timedelta(
            self._parsed_text["timeLeft"]
        )
        self._description += gettext(
            "has started un-anchoring. It will be fully un-anchored at: %s"
        ) % target_datetime_formatted(unanchored_at)
        self._color = Webhook.Color.INFO


class NotificationStructureUnderAttack(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure under attack")
        self._description += (
            gettext("is under attack by %s") % self._get_attacker_link()
        )
        self._color = Webhook.Color.DANGER

    def _get_attacker_link(self) -> str:
        """Returns the attacker link from a parsed_text for Upwell structures only."""
        if self._parsed_text.get("allianceName"):
            return self._gen_alliance_link(self._parsed_text["allianceName"])
        elif self._parsed_text.get("corpName"):
            return self._gen_corporation_link(self._parsed_text["corpName"])
        return "(unknown)"


class NotificationStructureLostShield(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure lost shield")
        timer_ends_at = notification.timestamp + ldap_timedelta_2_timedelta(
            self._parsed_text["timeLeft"]
        )
        self._description += gettext(
            "has lost its shields. Armor timer end at: %s"
        ) % target_datetime_formatted(timer_ends_at)
        self._color = Webhook.Color.DANGER


class NotificationStructureLostArmor(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure lost armor")
        timer_ends_at = notification.timestamp + ldap_timedelta_2_timedelta(
            self._parsed_text["timeLeft"]
        )
        self._description += gettext(
            "has lost its armor. Hull timer end at: %s"
        ) % target_datetime_formatted(timer_ends_at)
        self._color = Webhook.Color.DANGER


class NotificationStructureDestroyed(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure destroyed")
        self._description += gettext("has been destroyed.")
        self._color = Webhook.Color.DANGER


class NotificationStructureOwnershipTransferred(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        structure_type, _ = EveType.objects.get_or_create_esi(
            self._parsed_text["structureTypeID"]
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            self._parsed_text["solarSystemID"]
        )
        self._description = gettext(
            "The %(structure_type)s %(structure_name)s " "in %(solar_system)s "
        ) % {
            "structure_type": structure_type.name,
            "structure_name": Webhook.text_bold(self._parsed_text["structureName"]),
            "solar_system": self._gen_solar_system_text(solar_system),
        }
        from_corporation, _ = EveEntity.objects.get_or_create_esi(
            self._parsed_text["oldOwnerCorpID"]
        )
        to_corporation, _ = EveEntity.objects.get_or_create_esi(
            self._parsed_text["newOwnerCorpID"]
        )
        character, _ = EveEntity.objects.get_or_create_esi(self._parsed_text["charID"])
        self._description += gettext(
            "has been transferred from %(from_corporation)s "
            "to %(to_corporation)s by %(character)s."
        ) % {
            "from_corporation": self._gen_corporation_link(from_corporation.name),
            "to_corporation": self._gen_corporation_link(to_corporation.name),
            "character": character.name,
        }
        self._title = gettext("Ownership transferred")
        self._color = Webhook.Color.INFO
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationStructureAnchoring(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        structure_type, _ = EveType.objects.get_or_create_esi(
            self._parsed_text["structureTypeID"]
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            self._parsed_text["solarsystemID"]
        )
        owner_link = self._gen_corporation_link(
            self._parsed_text.get("ownerCorpName", "(unknown)")
        )
        self._description = gettext(
            "A %(structure_type)s belonging to %(owner_link)s "
            "has started anchoring in %(solar_system)s. "
        ) % {
            "structure_type": structure_type.name_localized,
            "owner_link": owner_link,
            "solar_system": self._gen_solar_system_text(solar_system),
        }
        self._title = gettext("Structure anchoring")
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
        all_structure_info = list()
        for structure_info in self._parsed_text["allStructureInfo"]:
            try:
                structure = Structure.objects.select_related_defaults().get(
                    id=structure_info[0]
                )
            except Structure.DoesNotExist:
                all_structure_info.append(
                    self.StructureInfo(
                        name=structure_info[1],
                        eve_type=EveType.objects.get_or_create_esi(structure_info[2]),
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

        self._title = gettext("Structure reinforcement time changed")
        change_effective = ldap_time_2_datetime(self._parsed_text["timestamp"])
        self._description = gettext(
            "Reinforcement hour has been changed to %s "
            "for the following structures:\n"
        ) % Webhook.text_bold(self._parsed_text["hour"])
        for structure_info in all_structure_info:
            self._description += gettext(
                "- %(structure_type)s %(structure_name)s in %(solar_system)s "
                "belonging to %(owner_link)s"
            ) % {
                "structure_type": structure_info.eve_type.name_localized,
                "structure_name": Webhook.text_bold(structure_info.name),
                "solar_system": self._gen_solar_system_text(
                    structure_info.eve_solar_system
                ),
                "owner_link": structure_info.owner_link,
            }

        self._description += gettext(
            "\n\nChange becomes effective at %s."
        ) % target_datetime_formatted(change_effective)
        self._color = Webhook.Color.INFO


class NotificationMoonminingEmbed(NotificationBaseEmbed):
    """Base class for all moon mining related notification embeds."""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._moon, _ = EveMoon.objects.get_or_create_esi(self._parsed_text["moonID"])
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            self._parsed_text["solarSystemID"]
        )
        self._solar_system_link = self._gen_solar_system_text(solar_system)
        self._structure_name = self._parsed_text["structureName"]
        self._owner_link = self._gen_corporation_link(str(notification.owner))
        structure_type, _ = EveType.objects.get_or_create_esi(
            self._parsed_text["structureTypeID"]
        )
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )

    def _ore_composition_text(self) -> str:
        if "oreVolumeByType" not in self._parsed_text:
            return ""

        ore_list = list()
        for ore_type_id, volume in self._parsed_text["oreVolumeByType"].items():
            ore_type, _ = EveType.objects.get_or_create_esi(ore_type_id)
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
            self._parsed_text["startedBy"]
        )
        ready_time = ldap_time_2_datetime(self._parsed_text["readyTime"])
        auto_time = ldap_time_2_datetime(self._parsed_text["autoTime"])
        self._title = gettext("Moon mining extraction started")
        self._description = gettext(
            "A moon mining extraction has been started "
            "for %(structure_name)s at %(moon)s in %(solar_system)s "
            "belonging to %(owner_link)s. "
            "Extraction was started by %(character)s.\n"
            "The chunk will be ready on location at %(ready_time)s, "
            "and will autofracture on %(auto_time)s.\n"
            "%(ore_text)s"
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "character": started_by,
            "ready_time": target_datetime_formatted(ready_time),
            "auto_time": target_datetime_formatted(auto_time),
            "ore_text": gettext(
                "\nEstimated ore composition: %s" % self._ore_composition_text()
            )
            if STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
            else "",
        }
        self._color = Webhook.Color.INFO


class NotificationMoonminningExtractionFinished(NotificationMoonminingEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        auto_time = ldap_time_2_datetime(self._parsed_text["autoTime"])
        self._title = gettext("Extraction finished")
        self._description = gettext(
            "The extraction for %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
            "is finished and the chunk is ready "
            "to be shot at.\n"
            "The chunk will automatically fracture on %(auto_time)s.\n"
            "%(ore_text)s"
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "auto_time": target_datetime_formatted(auto_time),
            "ore_text": gettext("\nOre composition: %s" % self._ore_composition_text())
            if STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
            else "",
        }
        self._color = Webhook.Color.INFO


class NotificationMoonminningAutomaticFracture(NotificationMoonminingEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Automatic Fracture")
        self._description = gettext(
            "The moondrill fitted to %(structure_name)s at %(moon)s"
            " in %(solar_system)s belonging to %(owner_link)s "
            "has automatically been fired "
            "and the moon products are ready to be harvested.\n"
            "%(ore_text)s"
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "ore_text": gettext("\nOre composition: %s" % self._ore_composition_text())
            if STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
            else "",
        }
        self._color = Webhook.Color.SUCCESS


class NotificationMoonminningExtractionCanceled(NotificationMoonminingEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        if self._parsed_text["cancelledBy"]:
            cancelled_by, _ = EveEntity.objects.get_or_create_esi(
                self._parsed_text["cancelledBy"]
            )
        else:
            cancelled_by = gettext("(unknown)")
        self._title = gettext("Extraction cancelled")
        self._description = gettext(
            "An ongoing extraction for %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
            "has been cancelled by %(character)s."
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "character": cancelled_by,
        }
        self._color = Webhook.Color.WARNING


class NotificationMoonminningLaserFired(NotificationMoonminingEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        fired_by, _ = EveEntity.objects.get_or_create_esi(self._parsed_text["firedBy"])
        self._title = gettext("Moondrill fired")
        self._description = gettext(
            "The moondrill fitted to %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
            "has been fired by %(character)s "
            "and the moon products are ready to be harvested.\n"
            "%(ore_text)s"
        ) % {
            "structure_name": Webhook.text_bold(self._structure_name),
            "moon": self._moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "character": fired_by,
            "ore_text": gettext("\nOre composition: %s" % self._ore_composition_text())
            if STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
            else "",
        }
        self._color = Webhook.Color.SUCCESS


class NotificationOrbitalEmbed(NotificationBaseEmbed):
    """Base class for all orbital (aka POCO) related notification embeds."""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._planet, _ = EvePlanet.objects.get_or_create_esi(
            self._parsed_text["planetID"]
        )
        self._structure_type, _ = EveType.objects.get_or_create_esi(
            EveTypeId.CUSTOMS_OFFICE
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            self._parsed_text["solarSystemID"]
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
        self._title = gettext("Orbital under attack")
        self._description = gettext(
            "The %(structure_type)s at %(planet)s in %(solar_system)s "
            "belonging to %(owner_link)s "
            "is under attack by %(aggressor)s."
        ) % {
            "structure_type": self._structure_type.name_localized,
            "planet": self._planet.name_localized,
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
        self._title = gettext("Orbital reinforced")
        self._description = gettext(
            "The %(structure_type)s at %(planet)s in %(solar_system)s "
            "belonging to %(owner_link)s "
            "has been reinforced by %(aggressor)s "
            "and will come out at: %(date)s."
        ) % {
            "structure_type": self._structure_type.name_localized,
            "planet": self._planet.name_localized,
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
            self._parsed_text["moonID"]
        )
        structure_type, _ = EveType.objects.get_or_create_esi(
            self._parsed_text["typeID"]
        )
        self._structure = Structure.objects.filter(eve_moon=self.eve_moon).first()
        if self._structure:
            structure_name = self._structure.name
        else:
            structure_name = structure_type.name_localized

        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )
        self._description = gettext(
            "The starbase %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
        ) % {
            "structure_name": Webhook.text_bold(structure_name),
            "moon": self.eve_moon.name_localized,
            "solar_system": self._gen_solar_system_text(self.eve_moon.eve_solar_system),
            "owner_link": self._gen_corporation_link(str(notification.owner)),
        }


class NotificationTowerAlertMsg(NotificationTowerEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        aggressor_link = self._get_aggressor_link()
        damage_labels = [
            ("shield", gettext("shield")),
            ("armor", gettext("armor")),
            ("hull", gettext("hull")),
        ]
        damage_parts = list()
        for prop in damage_labels:
            prop_yaml = prop[0] + "Value"
            if prop_yaml in self._parsed_text:
                damage_parts.append(
                    "{}: {:.0f}%".format(prop[1], self._parsed_text[prop_yaml] * 100)
                )
        damage_text = " | ".join(damage_parts)
        self._title = gettext("Starbase under attack")
        self._description += gettext(
            "is under attack by %(aggressor)s.\n%(damage_text)s"
        ) % {"aggressor": aggressor_link, "damage_text": damage_text}
        self._color = Webhook.Color.WARNING


class NotificationTowerResourceAlertMsg(NotificationTowerEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        if self._structure and self._structure.fuel_expires_at:
            hours_left = timeuntil(self._structure.fuel_expires_at)
        else:
            hours_left = "?"
        self._title = gettext("Starbase fuel alert")
        self._description += gettext(
            "is running out of fuel in %s."
        ) % Webhook.text_bold(hours_left)
        self._color = Webhook.Color.WARNING


class NotificationTowerRefueledExtra(NotificationTowerEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        if self._structure and self._structure.fuel_expires_at:
            target_date = target_datetime_formatted(self._structure.fuel_expires_at)
        else:
            target_date = "?"
        self._title = gettext("Starbase refueled")
        self._description += gettext(
            "has been refueled. Fuel will last until %s." % target_date
        )
        self._color = Webhook.Color.INFO


class NotificationSovEmbed(NotificationBaseEmbed):
    """Base class for all sovereignty related notification embeds."""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            self._parsed_text["solarSystemID"]
        )
        self._solar_system_link = self._gen_solar_system_text(self._solar_system)
        if "structureTypeID" in self._parsed_text:
            structure_type_id = self._parsed_text["structureTypeID"]
        elif "campaignEventType" in self._parsed_text:
            structure_type_id = Notification.type_id_from_event_type(
                self._parsed_text["campaignEventType"]
            )
        else:
            structure_type_id = EveTypeId.TCU
        structure_type, _ = EveType.objects.get_or_create_esi(structure_type_id)
        self._structure_type_name = structure_type.name_localized
        self._sov_owner_link = self._gen_alliance_link(notification.sender.name)
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationSovEntosisCaptureStarted(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext(
            "%(structure_type)s in %(solar_system)s is being captured"
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system.name_localized,
        }
        self._description = gettext(
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
        self._title = gettext(
            "Command nodes for %(structure_type)s in %(solar_system)s "
            "have begun to decloak"
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system.name_localized,
        }
        self._description = gettext(
            "Command nodes for %(structure_type)s in %(solar_system)s "
            "belonging to %(owner)s can now be found throughout "
            "the %(constellation)s constellation"
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system_link,
            "owner": self._sov_owner_link,
            "constellation": self._solar_system.eve_constellation.name_localized,
        }
        self._color = Webhook.Color.WARNING


class NotificationSovAllClaimAcquiredMsg(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        alliance, _ = EveEntity.objects.get_or_create_esi(
            self._parsed_text["allianceID"]
        )
        corporation, _ = EveEntity.objects.get_or_create_esi(
            self._parsed_text["corpID"]
        )
        self._title = (
            gettext("DED Sovereignty claim acknowledgment: %s")
            % self._solar_system.name_localized
        )
        self._description = gettext(
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
            self._parsed_text["allianceID"]
        )
        corporation, _ = EveEntity.objects.get_or_create_esi(
            self._parsed_text["corpID"]
        )
        self._title = (
            gettext("Lost sovereignty in: %s") % self._solar_system.name_localized
        )
        self._description = gettext(
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
        self._title = gettext(
            "%(structure_type)s in %(solar_system)s " "has entered reinforced mode"
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system.name_localized,
        }
        self._description = gettext(
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
        self._title = gettext(
            "%(structure_type)s in %(solar_system)s has been destroyed"
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system.name_localized,
        }
        self._description = gettext(
            "The command nodes for %(structure_type)s "
            "in %(solar_system)s belonging to %(owner)s have been "
            "destroyed by hostile forces."
        ) % {
            "structure_type": Webhook.text_bold(self._structure_type_name),
            "solar_system": self._solar_system_link,
            "owner": self._sov_owner_link,
        }
        self._color = Webhook.Color.DANGER


class NotificationCorpCharEmbed(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._character, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["charID"]
        )
        self._corporation, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["corpID"]
        )
        self._character_link = self._gen_eveentity_link(self._character)
        self._corporation_link = self._gen_corporation_link(self._corporation.name)
        self._application_text = self._parsed_text.get("applicationText", "")
        self._thumbnail = dhooks_lite.Thumbnail(
            self._character.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationCorpAppNewMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = "New application from %(character_name)s" % {
            "character_name": self._character.name,
        }
        self._description = (
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
        self._title = "%(character_name)s has been invited" % {
            "character_name": self._character.name
        }
        inviting_character, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["invokingCharID"]
        )
        inviting_character = self._gen_eveentity_link(inviting_character)

        self._description = (
            "%(character_name)s has been invited to join %(corporation_name)s "
            "by %(inviting_character)s.\n"
            "Application:\n"
            "> %(application_text)s"
            % {
                "character_name": self._character_link,
                "corporation_name": self._corporation_link,
                "inviting_character": inviting_character,
                "application_text": self._application_text,
            }
        )
        self._color = Webhook.Color.INFO


class NotificationCorpAppRejectCustomMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = "Rejected application from %(character_name)s" % {
            "character_name": self._character.name
        }
        self._description = (
            "Application from %(character_name)s to join %(corporation_name)s:\n"
            "> %(application_text)s\n"
            "Has been rejected:\n"
            "> %(customMessage)s"
            % {
                "character_name": self._character_link,
                "corporation_name": self._corporation_link,
                "application_text": self._application_text,
                "customMessage": self._parsed_text.get("customMessage", ""),
            }
        )
        self._color = Webhook.Color.INFO


class NotificationCharAppWithdrawMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = "%(character_name)s withdrew his/her application" % {
            "character_name": self._character.name,
        }
        self._description = (
            "%(character_name)s withdrew his/her application to join "
            "%(corporation_name)s:\n"
            "> %(application_text)s"
            % {
                "character_name": self._character_link,
                "corporation_name": self._corporation_link,
                "application_text": self._application_text,
            }
        )
        self._color = Webhook.Color.INFO


class NotificationCharAppAcceptMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = "%(character_name)s joins %(corporation_name)s" % {
            "character_name": self._character.name,
            "corporation_name": self._corporation.name,
        }
        self._description = (
            "%(character_name)s is now a member of %(corporation_name)s."
            % {
                "character_name": self._character_link,
                "corporation_name": self._corporation_link,
            }
        )
        self._color = Webhook.Color.SUCCESS


class NotificationCharLeftCorpMsg(NotificationCorpCharEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = "%(character_name)s has left %(corporation_name)s" % {
            "character_name": self._character.name,
            "corporation_name": self._corporation.name,
        }
        self._description = (
            "%(character_name)s is no longer a member of %(corporation_name)s."
            % {
                "character_name": self._character_link,
                "corporation_name": self._corporation_link,
            }
        )
        self._color = Webhook.Color.INFO


class NotificationAllyJoinedWarMsg(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = "Ally Has Joined a War"
        aggressor, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["aggressorID"]
        )
        ally, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["allyID"]
        )
        defender, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["defenderID"]
        )
        start_time = ldap_time_2_datetime(self._parsed_text["startTime"])
        self._description = (
            "%(ally)s has joined %(defender)s in a war against %(aggressor)s. "
            "Their participation in the war will start at %(start_time)s."
        ) % {
            "aggressor": self._gen_eveentity_link(aggressor),
            "ally": self._gen_eveentity_link(ally),
            "defender": self._gen_eveentity_link(defender),
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
            eve_entity_id=self._parsed_text["declaredByID"]
        )
        self._against, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["againstID"]
        )
        self._thumbnail = dhooks_lite.Thumbnail(
            self._declared_by.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationCorpWarSurrenderMsg(NotificationWarEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = "One party has surrendered"
        self._description = (
            "The war between %(against)s and %(declared_by)s is coming to an end "
            "as one party has surrendered. "
            "The war will be declared as being over after approximately 24 hours."
        ) % {
            "declared_by": self._gen_eveentity_link(self._declared_by),
            "against": self._gen_eveentity_link(self._against),
        }
        self._color = Webhook.Color.WARNING


class NotificationWarAdopted(NotificationWarEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        alliance, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["allianceID"]
        )
        self._title = "War update: %(against)s has left %(alliance)s" % {
            "against": self._against.name,
            "alliance": alliance.name,
        }
        self._description = (
            "There has been a development in the war between %(declared_by)s "
            "and %(alliance)s.\n"
            "%(against)s is no longer a member of %(alliance)s, "
            "and therefore a new war between %(declared_by)s and %(against)s has begun."
        ) % {
            "declared_by": self._gen_eveentity_link(self._declared_by),
            "against": self._gen_eveentity_link(self._against),
            "alliance": self._gen_eveentity_link(alliance),
        }
        self._color = Webhook.Color.WARNING


class NotificationWarDeclared(NotificationWarEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = "%(declared_by)s Declares War Against %(against)s" % {
            "declared_by": self._declared_by.name,
            "against": self._against.name,
        }
        self._description = (
            "%(declared_by)s has declared war on %(against)s with %(war_hq)s "
            "as the designated war headquarters.\n"
            "Within %(delay_hours)s hours fighting can legally occur "
            "between those involved."
        ) % {
            "declared_by": self._gen_eveentity_link(self._declared_by),
            "against": self._gen_eveentity_link(self._against),
            "war_hq": Webhook.text_bold(strip_tags(self._parsed_text["warHQ"])),
            "delay_hours": Webhook.text_bold(self._parsed_text["delayHours"]),
        }
        self._color = Webhook.Color.DANGER


class NotificationWarInherited(NotificationWarEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        alliance, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["allianceID"]
        )
        opponent, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["opponentID"]
        )
        quitter, _ = EveEntity.objects.get_or_create_esi(
            eve_entity_id=self._parsed_text["quitterID"]
        )
        self._title = "%(alliance)s inherits war against %(opponent)s" % {
            "alliance": alliance.name,
            "opponent": opponent.name,
        }
        self._description = (
            "%(alliance)s has inherited the war between %(declared_by)s and "
            "%(against)s from newly joined %(quitter)s. "
            "Within **24** hours fighting can legally occur with %(alliance)s."
        ) % {
            "declared_by": self._gen_eveentity_link(self._declared_by),
            "against": self._gen_eveentity_link(self._against),
            "alliance": self._gen_eveentity_link(alliance),
            "quitter": self._gen_eveentity_link(quitter),
        }
        self._color = Webhook.Color.DANGER


class NotificationWarRetractedByConcord(NotificationWarEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = "CONCORD invalidates war"
        war_ends = ldap_time_2_datetime(self._parsed_text["endDate"])
        self._description = (
            "The war between %(declared_by)s and %(against)s "
            "has been retracted by CONCORD.\n"
            "After %(end_date)s CONCORD will again respond to any hostilities "
            "between those involved with full force."
        ) % {
            "declared_by": self._gen_eveentity_link(self._declared_by),
            "against": self._gen_eveentity_link(self._against),
            "end_date": target_datetime_formatted(war_ends),
        }
        self._color = Webhook.Color.WARNING


class NotificationWarCorporationBecameEligible(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = (
            "Corporation or alliance is now eligable for formal war declarations"
        )
        self._description = (
            "Your corporation or alliance is **now eligible** to participate in "
            "formal war declarations. This could be because your corporation "
            "and/or one of the corporations in your alliance owns a structure "
            "deployed in space."
        )
        self._color = Webhook.Color.WARNING


class NotificationWarCorporationNoLongerEligible(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = (
            "Corporation or alliance is no longer eligible for formal war declarations"
        )
        self._description = (
            "Your corporation or alliance is **no longer eligible** to participate "
            "in formal war declarations.\n"
            "Neither your corporation nor any of the corporations "
            "in your alliance own a structure deployed in space at this time. "
            "If your corporation or alliance is currently involved in a formal war, "
            "that war will end in 24 hours."
        )
        self._color = Webhook.Color.INFO
