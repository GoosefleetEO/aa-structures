"""Billing embeds."""

# pylint: disable=missing-class-docstring

from typing import Optional

import dhooks_lite

from django.conf import settings
from django.utils.translation import gettext as __
from eveuniverse.models import EveEntity, EveMoon, EveSolarSystem, EveType

from app_utils.urls import reverse_absolute, static_file_absolute_url

from structures import __title__
from structures.core.notification_types import NotificationType
from structures.models.notifications import Notification, NotificationBase, Webhook

from .helpers import target_datetime_formatted


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
        return f"{self.__class__.__name__}(notification={self.notification!r})"

    @property
    def notification(self) -> Notification:
        """Return notification object this embed is created from."""
        return self._notification

    @property
    def ping_type(self) -> Optional[Webhook.PingType]:
        """Return Ping Type of the related notification."""
        return self._ping_type

    def compile_damage_text(self, field_postfix: str, factor: int = 1) -> str:
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

    def get_aggressor_link(self) -> str:
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

    def fuel_expires_target_date(self) -> str:
        """Return calculated target date when fuel expires. Returns '?' when no data."""
        if self._structure and self._structure.fuel_expires_at:
            return target_datetime_formatted(self._structure.fuel_expires_at)
        return "?"

    def eve_moon(self, key: str = "moonID") -> EveMoon:
        """Return it's moon extracted from the notification text.
        Will raise error if not found.
        """
        eve_moon_id = self._parsed_text[key]
        eve_moon, _ = EveMoon.objects.get_or_create_esi(id=eve_moon_id)
        return eve_moon

    def eve_solar_system(self, key: str = "solarSystemID") -> EveSolarSystem:
        """Return solar system extracted from the notification text.
        Will raise error if not found.
        """
        eve_solar_system_id = self._parsed_text[key]
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=eve_solar_system_id
        )
        return solar_system

    def eve_structure_type(self, key: str = "structureTypeID") -> EveType:
        """Return structure type extracted from the notification text.
        Will raise error if not found.
        """
        eve_type_id = self._parsed_text[key]
        structure_type, _ = EveType.objects.get_or_create_esi(id=eve_type_id)
        return structure_type

    def generate_embed(self) -> dhooks_lite.Embed:
        """Returns generated Discord embed for this object.

        Will use custom color for embeds if self.notification has the
        property "color_override" defined

        Will use custom ping type if self.notification has the
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
        if self.notification.color_override:
            self._color = self.notification.color_override
        if self.notification.ping_type_override:
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

    # pylint: disable = too-many-locals
    @staticmethod
    def create(notification: "NotificationBase") -> "NotificationBaseEmbed":
        """Creates a new instance of the respective subclass for given Notification."""

        from .billing_embeds import (
            NotificationBillingBillOutOfMoneyMsg,
            NotificationBillingIHubBillAboutToExpire,
            NotificationBillingIHubDestroyedByBillFailure,
        )
        from .character_embeds import (
            NotificationCharAppAcceptMsg,
            NotificationCharAppWithdrawMsg,
            NotificationCharLeftCorpMsg,
            NotificationCorpAppInvitedMsg,
            NotificationCorpAppNewMsg,
            NotificationCorpAppRejectCustomMsg,
        )
        from .moonmining_embeds import (
            NotificationMoonminningAutomaticFracture,
            NotificationMoonminningExtractionCanceled,
            NotificationMoonminningExtractionFinished,
            NotificationMoonminningExtractionStarted,
            NotificationMoonminningLaserFired,
        )
        from .orbital_embeds import (
            NotificationOrbitalAttacked,
            NotificationOrbitalReinforced,
        )
        from .sov_embeds import (
            NotificationSovAllAnchoringMsg,
            NotificationSovAllClaimAcquiredMsg,
            NotificationSovAllClaimLostMsg,
            NotificationSovCommandNodeEventStarted,
            NotificationSovEntosisCaptureStarted,
            NotificationSovStructureDestroyed,
            NotificationSovStructureReinforced,
        )
        from .structures_embeds import (
            NotificationStructureAnchoring,
            NotificationStructureDestroyed,
            NotificationStructureFuelAlert,
            NotificationStructureJumpFuelAlert,
            NotificationStructureLostArmor,
            NotificationStructureLostShield,
            NotificationStructureOnline,
            NotificationStructureOwnershipTransferred,
            NotificationStructureRefueledExtra,
            NotificationStructureReinforceChange,
            NotificationStructureServicesOffline,
            NotificationStructureUnanchoring,
            NotificationStructureUnderAttack,
            NotificationStructureWentHighPower,
            NotificationStructureWentLowPower,
        )
        from .tower_embeds import (
            NotificationTowerAlertMsg,
            NotificationTowerRefueledExtra,
            NotificationTowerReinforcedExtra,
            NotificationTowerResourceAlertMsg,
        )
        from .war_embeds import (
            NotificationAllyJoinedWarMsg,
            NotificationCorpWarSurrenderMsg,
            NotificationWarAdopted,
            NotificationWarCorporationBecameEligible,
            NotificationWarCorporationNoLongerEligible,
            NotificationWarDeclared,
            NotificationWarInherited,
            NotificationWarRetractedByConcord,
            NotificationWarSurrenderOfferMsg,
        )

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
