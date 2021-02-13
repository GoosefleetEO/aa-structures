import datetime as dt

import dhooks_lite
from django.utils.translation import gettext

from allianceauth.eveonline.evelinks import dotlan

from ..app_settings import (
    STRUCTURES_DEVELOPER_MODE,
    STRUCTURES_NOTIFICATION_SHOW_MOON_ORE,
)
from ..helpers.eveonline import ldap_datetime_2_dt, ldap_timedelta_2_timedelta
from ..models.eveuniverse import EveType, EveSolarSystem, EveMoon, EvePlanet
from ..models.notifications import EveEntity, Notification, NotificationType, Webhook
from ..models.structures import Structure
from ..utils import DATETIME_FORMAT


class NotificationEmbed:
    """Base class for all notification embeds"""

    # embed colors
    COLOR_INFO = 0x5BC0DE
    COLOR_SUCCESS = 0x5CB85C
    COLOR_WARNING = 0xF0AD4E
    COLOR_DANGER = 0xD9534F

    def __init__(self, notification: Notification) -> None:
        if not isinstance(notification, Notification):
            raise TypeError("notification must be of type Notification")
        self._notification = notification
        self._parsed_text = notification.get_parsed_text()
        self._title = "[UNDEFINED]"
        self._description = "[UNDEFINED]"
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
        """returns generated Discord embed for this object"""
        if type(self) is NotificationEmbed:
            raise RuntimeError("Method must not be called for base class")
        if self._color == self.COLOR_DANGER:
            self._ping_type = Webhook.PingType.EVERYONE
        elif self._color == self.COLOR_WARNING:
            self._ping_type = Webhook.PingType.HERE
        else:
            self._ping_type = Webhook.PingType.NONE
        if STRUCTURES_DEVELOPER_MODE:
            footer = dhooks_lite.Footer(self.notification.notification_id)
        else:
            footer = None
        return dhooks_lite.Embed(
            title=self._title,
            description=self._description,
            color=self._color,
            thumbnail=self._thumbnail,
            footer=footer,
        )

    @staticmethod
    def create(notification: Notification) -> "NotificationEmbed":
        """creates a new instance of the respective subclass for given Notification"""
        if not isinstance(notification, Notification):
            raise TypeError("notification must be of type Notification")
        notification_type = notification.notification_type
        # moonmining
        if notification_type == NotificationType.MOONS_EXTRACTION_STARTED:
            return NotificationMoonminningExtractionStarted(notification)
        elif notification_type == NotificationType.MOONS_EXTRACTION_FINISHED:
            return NotificationMoonminningExtractionFinished(notification)
        elif notification_type == NotificationType.MOONS_AUTOMATIC_FRACTURE:
            return NotificationMoonminningAutomaticFracture(notification)
        elif notification_type == NotificationType.MOONS_EXTRACTION_CANCELED:
            return NotificationMoonminningExtractionCanceled(notification)
        elif notification_type == NotificationType.MOONS_LASER_FIRED:
            return NotificationMoonminningLaserFired(notification)

        # upwell structures
        elif notification_type == NotificationType.STRUCTURE_ONLINE:
            return NotificationStructureOnline(notification)
        elif notification_type == NotificationType.STRUCTURE_FUEL_ALERT:
            return NotificationStructureFuelAlert(notification)
        elif notification_type == NotificationType.STRUCTURE_SERVICES_OFFLINE:
            return NotificationStructureServicesOffline(notification)
        elif notification_type == NotificationType.STRUCTURE_WENT_LOW_POWER:
            return NotificationStructureWentLowPower(notification)
        elif notification_type == NotificationType.STRUCTURE_WENT_HIGH_POWER:
            return NotificationStructureWentHighPower(notification)
        elif notification_type == NotificationType.STRUCTURE_UNANCHORING:
            return NotificationStructureUnanchoring(notification)
        elif notification_type == NotificationType.STRUCTURE_UNDER_ATTACK:
            return NotificationStructureUnderAttack(notification)
        elif notification_type == NotificationType.STRUCTURE_LOST_SHIELD:
            return NotificationStructureLostShield(notification)
        elif notification_type == NotificationType.STRUCTURE_LOST_ARMOR:
            return NotificationStructureLostArmor(notification)
        elif notification_type == NotificationType.STRUCTURE_DESTROYED:
            return NotificationStructureDestroyed(notification)
        elif notification_type == NotificationType.OWNERSHIP_TRANSFERRED:
            return NotificationStructureOwnershipTransferred(notification)
        elif notification_type == NotificationType.STRUCTURE_ANCHORING:
            return NotificationStructureAnchoring(notification)

        # Orbitals
        elif notification_type == NotificationType.ORBITAL_ATTACKED:
            return NotificationOrbitalAttacked(notification)
        elif notification_type == NotificationType.ORBITAL_REINFORCED:
            return NotificationOrbitalReinforced(notification)

        # Towers
        elif notification_type == NotificationType.TOWER_ALERT_MSG:
            return NotificationTowerAlertMsg(notification)
        elif notification_type == NotificationType.TOWER_RESOURCE_ALERT_MSG:
            return NotificationTowerResourceAlertMsg(notification)

        # Sov
        elif notification_type == NotificationType.SOV_ENTOSIS_CAPTURE_STARTED:
            return NotificationSovEntosisCaptureStarted(notification)
        elif notification_type == NotificationType.SOV_COMMAND_NODE_EVENT_STARTED:
            return NotificationSovCommandNodeEventStarted(notification)
        elif notification_type == NotificationType.SOV_ALL_CLAIM_ACQUIRED_MSG:
            return NotificationSovAllClaimAcquiredMsg(notification)
        elif notification_type == NotificationType.SOV_STRUCTURE_REINFORCED:
            return NotificationSovStructureReinforced(notification)
        elif notification_type == NotificationType.SOV_STRUCTURE_DESTROYED:
            return NotificationSovStructureDestroyed(notification)

        # NOT IMPLEMENTED
        else:
            raise NotImplementedError(f"type: {notification_type}")

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
    def _gen_corporation_link(corporation_name: str) -> str:
        return Webhook.create_link(
            corporation_name, dotlan.corporation_url(corporation_name)
        )

    def _get_attacker_link(self) -> str:
        """returns the attacker link from a parsed_text
        For Upwell structures only
        """
        if self._parsed_text.get("allianceName"):
            return self._gen_alliance_link(self._parsed_text["allianceName"])
        elif self._parsed_text.get("corpName"):
            return self._gen_corporation_link(self._parsed_text["corpName"])
        return "(unknown)"

    def _get_aggressor_link(self) -> str:
        """returns the aggressor link from a parsed_text
        for POS and POCOs only
        """
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


class NotificationStructureEmbed(NotificationEmbed):
    """Base class for most structure related notification embeds"""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        try:
            structure = Structure.objects.select_related().get(
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
        else:
            structure_name = structure.name
            structure_type = structure.eve_type
            structure_solar_system = structure.eve_solar_system
            owner_link = self._gen_corporation_link(str(structure.owner))

        self._structure = structure
        self._description = gettext(
            "The %(structure_type)s %(structure_name)s in %(solar_system)s "
            "belonging to %(owner_link)s "
        ) % {
            "structure_type": structure_type.name_localized,
            "structure_name": "**%s**" % structure_name,
            "solar_system": self._gen_solar_system_text(structure_solar_system),
            "owner_link": owner_link,
        }
        self._thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())


class NotificationStructureOnline(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure online")
        self._description += gettext("is now online.")
        self._color = self.COLOR_SUCCESS


class NotificationStructureFuelAlert(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure fuel alert")
        self._description += gettext("has less then 24hrs fuel left.")
        self._color = self.COLOR_WARNING


class NotificationStructureServicesOffline(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure services off-line")
        self._description += gettext("has all services off-lined.")
        if self._structure and self._structure.structureservice_set.count() > 0:
            qs = self._structure.structureservice_set.all().order_by("name")
            services_list = "\n".join([x.name for x in qs])
            self._description += "\n*{}*".format(services_list)
        self._color = self.COLOR_DANGER


class NotificationStructureWentLowPower(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure low power")
        self._description += gettext("went to low power mode.")
        self._color = self.COLOR_WARNING


class NotificationStructureWentHighPower(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure full power")
        self._description += gettext("went to full power mode.")
        self._color = self.COLOR_SUCCESS


class NotificationStructureUnanchoring(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure un-anchoring")
        unanchored_at = notification.timestamp + ldap_timedelta_2_timedelta(
            self._parsed_text["timeLeft"]
        )
        self._description += gettext(
            "has started un-anchoring. " "It will be fully un-anchored at: %s"
        ) % unanchored_at.strftime(DATETIME_FORMAT)
        self._color = self.COLOR_INFO


class NotificationStructureUnderAttack(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure under attack")
        self._description += (
            gettext("is under attack by %s") % self._get_attacker_link()
        )
        self._color = self.COLOR_DANGER


class NotificationStructureLostShield(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure lost shield")
        timer_ends_at = notification.timestamp + ldap_timedelta_2_timedelta(
            self._parsed_text["timeLeft"]
        )
        self._description += gettext(
            "has lost its shields. Armor timer end at: %s"
        ) % timer_ends_at.strftime(DATETIME_FORMAT)
        self._color = self.COLOR_DANGER


class NotificationStructureLostArmor(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure lost armor")
        timer_ends_at = notification.timestamp + ldap_timedelta_2_timedelta(
            self._parsed_text["timeLeft"]
        )
        self._description += gettext(
            "has lost its armor. Hull timer end at: %s"
        ) % timer_ends_at.strftime(DATETIME_FORMAT)
        self._color = self.COLOR_DANGER


class NotificationStructureDestroyed(NotificationStructureEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext("Structure destroyed")
        self._description += gettext("has been destroyed.")
        self._color = self.COLOR_DANGER


class NotificationStructureOwnershipTransferred(NotificationEmbed):
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
            "structure_name": "**%s**" % self._parsed_text["structureName"],
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
        self._color = self.COLOR_INFO
        self._thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())


class NotificationStructureAnchoring(NotificationEmbed):
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
        if not solar_system.is_null_sec:
            unanchored_at = notification.timestamp + dt.timedelta(hours=24)
            self._description += "The anchoring timer ends at: {}".format(
                unanchored_at.strftime(DATETIME_FORMAT)
            )
        self._title = gettext("Structure anchoring")
        self._color = self.COLOR_INFO
        self._thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())


class NotificationMoonminingEmbed(NotificationEmbed):
    """Base class for all moon mining related notification embeds"""

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
        self._thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())

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
        ready_time = ldap_datetime_2_dt(self._parsed_text["readyTime"])
        auto_time = ldap_datetime_2_dt(self._parsed_text["autoTime"])
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
            "structure_name": "**%s**" % self._structure_name,
            "moon": self._moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "character": started_by,
            "ready_time": ready_time.strftime(DATETIME_FORMAT),
            "auto_time": auto_time.strftime(DATETIME_FORMAT),
            "ore_text": gettext(
                "\nEstimated ore composition: %s" % self._ore_composition_text()
            )
            if STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
            else "",
        }
        self._color = self.COLOR_INFO


class NotificationMoonminningExtractionFinished(NotificationMoonminingEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        auto_time = ldap_datetime_2_dt(self._parsed_text["autoTime"])
        self._title = gettext("Extraction finished")
        self._description = gettext(
            "The extraction for %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
            "is finished and the chunk is ready "
            "to be shot at.\n"
            "The chunk will automatically fracture on %(auto_time)s.\n"
            "%(ore_text)s"
        ) % {
            "structure_name": "**%s**" % self._structure_name,
            "moon": self._moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "auto_time": auto_time.strftime(DATETIME_FORMAT),
            "ore_text": gettext("\nOre composition: %s" % self._ore_composition_text())
            if STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
            else "",
        }
        self._color = self.COLOR_INFO


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
            "structure_name": "**%s**" % self._structure_name,
            "moon": self._moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "ore_text": gettext("\nOre composition: %s" % self._ore_composition_text())
            if STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
            else "",
        }
        self._color = self.COLOR_SUCCESS


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
            "structure_name": "**%s**" % self._structure_name,
            "moon": self._moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "character": cancelled_by,
        }
        self._color = self.COLOR_WARNING


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
            "structure_name": "**%s**" % self._structure_name,
            "moon": self._moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "character": fired_by,
            "ore_text": gettext("\nOre composition: %s" % self._ore_composition_text())
            if STRUCTURES_NOTIFICATION_SHOW_MOON_ORE
            else "",
        }
        self._color = self.COLOR_SUCCESS


class NotificationOrbitalEmbed(NotificationEmbed):
    """Base class for all orbital (aka POCO) related notification embeds"""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._planet, _ = EvePlanet.objects.get_or_create_esi(
            self._parsed_text["planetID"]
        )
        self._structure_type, _ = EveType.objects.get_or_create_esi(
            EveType.EVE_TYPE_ID_POCO
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            self._parsed_text["solarSystemID"]
        )
        self._solar_system_link = self._gen_solar_system_text(solar_system)
        self._owner_link = self._gen_corporation_link(str(notification.owner))
        self._aggressor_link = self._get_aggressor_link()
        self._thumbnail = dhooks_lite.Thumbnail(self._structure_type.icon_url())


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
        self._color = self.COLOR_WARNING


class NotificationOrbitalReinforced(NotificationOrbitalEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        reinforce_exit_time = ldap_datetime_2_dt(self._parsed_text["reinforceExitTime"])
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
            "date": reinforce_exit_time.strftime(DATETIME_FORMAT),
        }
        self._color = self.COLOR_DANGER


class NotificationTowerEmbed(NotificationEmbed):
    """Base class for all tower (aka POS) related notification embeds"""

    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self.eve_moon, _ = EveMoon.objects.get_or_create_esi(
            self._parsed_text["moonID"]
        )
        structure_type, _ = EveType.objects.get_or_create_esi(
            self._parsed_text["typeID"]
        )
        self._solar_system_link = self._gen_solar_system_text(
            self.eve_moon.eve_solar_system
        )
        self._owner_link = self._gen_corporation_link(str(notification.owner))
        qs_structures = Structure.objects.filter(eve_moon=self.eve_moon)
        if qs_structures.exists():
            self._structure_name = qs_structures.first().name
        else:
            self._structure_name = structure_type.name_localized

        self._thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())


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
        self._description = gettext(
            "The starbase %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s "
            "is under attack by %(aggressor)s.\n"
            "%(damage_text)s"
        ) % {
            "structure_name": "**%s**" % self._structure_name,
            "moon": self.eve_moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "aggressor": aggressor_link,
            "damage_text": damage_text,
        }
        self._color = self.COLOR_WARNING


class NotificationTowerResourceAlertMsg(NotificationTowerEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        quantity = self._parsed_text["wants"][0]["quantity"]
        self._title = gettext("Starbase low on fuel")
        self._description = gettext(
            "The starbase %(structure_name)s at %(moon)s "
            "in %(solar_system)s belonging to %(owner_link)s is low on fuel. "
            "It has %(quantity)d fuel blocks left."
        ) % {
            "structure_name": "**%s**" % self._structure_name,
            "moon": self.eve_moon.name_localized,
            "solar_system": self._solar_system_link,
            "owner_link": self._owner_link,
            "quantity": quantity,
        }
        self._color = self.COLOR_WARNING


class NotificationSovEmbed(NotificationEmbed):
    """Base class for all sovereignty related notification embeds"""

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
            structure_type_id = EveType.EVE_TYPE_ID_TCU
        structure_type, _ = EveType.objects.get_or_create_esi(structure_type_id)
        self._structure_type_name = structure_type.name_localized
        self._sov_owner_link = self._gen_alliance_link(notification.sender.name)
        self._thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())


class NotificationSovEntosisCaptureStarted(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext(
            "%(structure_type)s in %(solar_system)s is being captured"
        ) % {
            "structure_type": "**%s**" % self._structure_type_name,
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
        self._color = self.COLOR_WARNING


class NotificationSovCommandNodeEventStarted(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext(
            "Command nodes for %(structure_type)s in %(solar_system)s "
            "have begun to decloak"
        ) % {
            "structure_type": "**%s**" % self._structure_type_name,
            "solar_system": self._solar_system.name_localized,
        }
        self._description = gettext(
            "Command nodes for %(structure_type)s in %(solar_system)s "
            "belonging to %(owner)s can now be found throughout "
            "the %(constellation)s constellation"
        ) % {
            "structure_type": "**%s**" % self._structure_type_name,
            "solar_system": self._solar_system_link,
            "owner": self._sov_owner_link,
            "constellation": self._solar_system.eve_constellation.name_localized,
        }
        self._color = self.COLOR_WARNING


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
        self._color = self.COLOR_SUCCESS


class NotificationSovStructureReinforced(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        timer_starts = ldap_datetime_2_dt(self._parsed_text["decloakTime"])
        self._title = gettext(
            "%(structure_type)s in %(solar_system)s " "has entered reinforced mode"
        ) % {
            "structure_type": "**%s**" % self._structure_type_name,
            "solar_system": self._solar_system.name_localized,
        }
        self._description = gettext(
            "The %(structure_type)s in %(solar_system)s belonging "
            "to %(owner)s has been reinforced by "
            "hostile forces and command nodes "
            "will begin decloaking at %(date)s"
        ) % {
            "structure_type": "**%s**" % self._structure_type_name,
            "solar_system": self._solar_system_link,
            "owner": self._sov_owner_link,
            "date": timer_starts.strftime(DATETIME_FORMAT),
        }
        self._color = self.COLOR_DANGER


class NotificationSovStructureDestroyed(NotificationSovEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._title = gettext(
            "%(structure_type)s in %(solar_system)s has been destroyed"
        ) % {
            "structure_type": "**%s**" % self._structure_type_name,
            "solar_system": self._solar_system.name_localized,
        }
        self._description = gettext(
            "The command nodes for %(structure_type)s "
            "in %(solar_system)s belonging to %(owner)s have been "
            "destroyed by hostile forces."
        ) % {
            "structure_type": "**%s**" % self._structure_type_name,
            "solar_system": self._solar_system_link,
            "owner": self._sov_owner_link,
        }
        self._color = self.COLOR_DANGER
