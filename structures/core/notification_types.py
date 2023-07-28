"""Global definition of known notification types."""

from typing import List, Set

from django.db import models
from django.utils.translation import gettext_lazy as _

from structures.app_settings import STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS


class NotificationType(models.TextChoices):
    """Definition of all supported notification types."""

    # upwell structures
    STRUCTURE_ANCHORING = "StructureAnchoring", _("Upwell structure anchoring")
    STRUCTURE_ONLINE = "StructureOnline", _("Upwell structure went online")
    STRUCTURE_SERVICES_OFFLINE = "StructureServicesOffline", _(
        "Upwell structure services went offline"
    )
    STRUCTURE_WENT_HIGH_POWER = "StructureWentHighPower", _(
        "Upwell structure went high power"
    )
    STRUCTURE_WENT_LOW_POWER = "StructureWentLowPower", _(
        "Upwell structure went low power"
    )
    STRUCTURE_UNANCHORING = "StructureUnanchoring", _("Upwell structure unanchoring")
    STRUCTURE_FUEL_ALERT = "StructureFuelAlert", _("Upwell structure fuel alert")
    STRUCTURE_REFUELED_EXTRA = "StructureRefueledExtra", _("Upwell structure refueled")
    STRUCTURE_JUMP_FUEL_ALERT = "StructureJumpFuelAlert", _(
        "Upwell structure jump fuel alert"
    )
    STRUCTURE_UNDER_ATTACK = "StructureUnderAttack", _(
        "Upwell structure is under attack"
    )
    STRUCTURE_LOST_SHIELD = "StructureLostShields", _("Upwell structure lost shields")
    STRUCTURE_LOST_ARMOR = "StructureLostArmor", _("Upwell structure lost armor")
    STRUCTURE_DESTROYED = "StructureDestroyed", _("Upwell structure destroyed")

    STRUCTURE_REINFORCE_CHANGED = "StructuresReinforcementChanged", _(
        "Upwell structure reinforcement time changed"
    )
    OWNERSHIP_TRANSFERRED = "OwnershipTransferred", _(
        "Upwell structure ownership transferred"
    )

    # customs offices
    ORBITAL_ATTACKED = "OrbitalAttacked", _("Customs office attacked")
    ORBITAL_REINFORCED = "OrbitalReinforced", _("Customs office reinforced")

    # starbases
    TOWER_ALERT_MSG = "TowerAlertMsg", _("Starbase attacked")
    TOWER_RESOURCE_ALERT_MSG = "TowerResourceAlertMsg", _("Starbase fuel alert")
    TOWER_REFUELED_EXTRA = "TowerRefueledExtra", _("Starbase refueled (BETA)")
    TOWER_REINFORCED_EXTRA = "TowerReinforcedExtra", _("Starbase reinforced (BETA)")

    # moon mining
    MOONMINING_EXTRACTION_STARTED = "MoonminingExtractionStarted", _(
        "Moon mining extraction started"
    )
    MOONMINING_LASER_FIRED = "MoonminingLaserFired", _("Moonmining laser fired")
    MOONMINING_EXTRACTION_CANCELLED = "MoonminingExtractionCancelled", _(
        "Moon mining extraction cancelled"
    )
    MOONMINING_EXTRACTION_FINISHED = "MoonminingExtractionFinished", _(
        "Moon mining extraction finished"
    )
    MOONMINING_AUTOMATIC_FRACTURE = "MoonminingAutomaticFracture", _(
        "Moon mining automatic fracture triggered"
    )

    # sov
    SOV_STRUCTURE_REINFORCED = "SovStructureReinforced", _(
        "Sovereignty structure reinforced"
    )
    SOV_STRUCTURE_DESTROYED = "SovStructureDestroyed", _(
        "Sovereignty structure destroyed"
    )
    SOV_ENTOSIS_CAPTURE_STARTED = "EntosisCaptureStarted", _(
        "Sovereignty entosis capture started"
    )
    SOV_COMMAND_NODE_EVENT_STARTED = "SovCommandNodeEventStarted", _(
        "Sovereignty command node event started"
    )
    SOV_ALL_CLAIM_ACQUIRED_MSG = "SovAllClaimAquiredMsg", _(
        "Sovereignty claim acknowledgment"  # SovAllClaimAquiredMsg [sic!]
    )
    SOV_ALL_CLAIM_LOST_MSG = "SovAllClaimLostMsg", _("Sovereignty lost")
    SOV_ALL_ANCHORING_MSG = "AllAnchoringMsg", _(
        "Structure anchoring in alliance space"
    )

    # wars
    WAR_WAR_DECLARED = "WarDeclared", _("War declared")
    WAR_ALLY_JOINED_WAR_AGGRESSOR_MSG = "AllyJoinedWarAggressorMsg", _(
        "War ally joined aggressor"
    )
    WAR_ALLY_JOINED_WAR_ALLY_MSG = "AllyJoinedWarAllyMsg", _("War ally joined ally")
    WAR_ALLY_JOINED_WAR_DEFENDER_MSG = "AllyJoinedWarDefenderMsg", _(
        "War ally joined defender"
    )
    WAR_WAR_ADOPTED = "WarAdopted", _("War adopted")
    WAR_WAR_INHERITED = "WarInherited", _("War inherited")
    WAR_CORP_WAR_SURRENDER_MSG = "CorpWarSurrenderMsg", _("War party surrendered")
    WAR_WAR_RETRACTED_BY_CONCORD = "WarRetractedByConcord", _(
        "War retracted by Concord"
    )
    WAR_CORPORATION_BECAME_ELIGIBLE = "CorpBecameWarEligible", _(
        "War corporation became eligible"
    )
    WAR_CORPORATION_NO_LONGER_ELIGIBLE = "CorpNoLongerWarEligible", _(
        "War corporation no longer eligible"
    )
    WAR_WAR_SURRENDER_OFFER_MSG = "WarSurrenderOfferMsg", _("War surrender offered")

    # corporation membership
    CORP_APP_NEW_MSG = "CorpAppNewMsg", _("Character submitted application")
    CORP_APP_INVITED_MSG = "CorpAppInvitedMsg", _(
        "Character invited to join corporation"
    )
    CORP_APP_REJECT_CUSTOM_MSG = "CorpAppRejectCustomMsg", _(
        "Corp application rejected"
    )
    CHAR_APP_WITHDRAW_MSG = "CharAppWithdrawMsg", _("Character withdrew application")
    CHAR_APP_ACCEPT_MSG = "CharAppAcceptMsg", _("Character joins corporation")
    CHAR_LEFT_CORP_MSG = "CharLeftCorpMsg", _("Character leaves corporation")

    # billing
    BILLING_BILL_OUT_OF_MONEY_MSG = "BillOutOfMoneyMsg", _("Bill out of money")
    BILLING_I_HUB_BILL_ABOUT_TO_EXPIRE = (
        "InfrastructureHubBillAboutToExpire",
        _("I-HUB bill about to expire"),
    )
    BILLING_I_HUB_DESTROYED_BY_BILL_FAILURE = (
        "IHubDestroyedByBillFailure",
        _("I_HUB destroyed by bill failure"),
    )

    @classmethod
    def esi_notifications(cls) -> Set["NotificationType"]:
        """Return all ESI notification types."""
        return set(cls.values) - cls.generated_notifications()

    @classmethod
    def generated_notifications(cls) -> Set["NotificationType"]:
        """Return all generated notification types."""
        return {
            cls.STRUCTURE_JUMP_FUEL_ALERT,
            cls.STRUCTURE_REFUELED_EXTRA,
            cls.TOWER_REFUELED_EXTRA,
            cls.TOWER_REINFORCED_EXTRA,
        }

    @classmethod
    def webhook_defaults(cls) -> List["NotificationType"]:
        """List of default notifications for new webhooks."""
        return [
            cls.STRUCTURE_ANCHORING,
            cls.STRUCTURE_DESTROYED,
            cls.STRUCTURE_FUEL_ALERT,
            cls.STRUCTURE_LOST_ARMOR,
            cls.STRUCTURE_LOST_SHIELD,
            cls.STRUCTURE_ONLINE,
            cls.STRUCTURE_SERVICES_OFFLINE,
            cls.STRUCTURE_UNDER_ATTACK,
            cls.STRUCTURE_WENT_HIGH_POWER,
            cls.STRUCTURE_WENT_LOW_POWER,
            cls.ORBITAL_ATTACKED,
            cls.ORBITAL_REINFORCED,
            cls.TOWER_ALERT_MSG,
            cls.TOWER_RESOURCE_ALERT_MSG,
            cls.SOV_STRUCTURE_REINFORCED,
            cls.SOV_STRUCTURE_DESTROYED,
        ]

    @classmethod
    def relevant_for_timerboard(cls) -> Set["NotificationType"]:
        """Notification types that can create timers."""
        return {
            cls.STRUCTURE_LOST_SHIELD,
            cls.STRUCTURE_LOST_ARMOR,
            cls.ORBITAL_REINFORCED,
            cls.MOONMINING_EXTRACTION_STARTED,
            cls.MOONMINING_EXTRACTION_CANCELLED,
            cls.SOV_STRUCTURE_REINFORCED,
            cls.TOWER_REINFORCED_EXTRA,
        }

    @classmethod
    def relevant_for_alliance_level(cls) -> Set["NotificationType"]:
        """Notification types that require the alliance level flag."""
        return {
            # billing
            cls.BILLING_BILL_OUT_OF_MONEY_MSG,
            cls.BILLING_I_HUB_DESTROYED_BY_BILL_FAILURE,
            cls.BILLING_I_HUB_BILL_ABOUT_TO_EXPIRE,
            # sov
            cls.SOV_ENTOSIS_CAPTURE_STARTED,
            cls.SOV_COMMAND_NODE_EVENT_STARTED,
            cls.SOV_ALL_CLAIM_ACQUIRED_MSG,
            cls.SOV_STRUCTURE_REINFORCED,
            cls.SOV_STRUCTURE_DESTROYED,
            cls.SOV_ALL_CLAIM_LOST_MSG,
            # cls.SOV_ALL_ANCHORING_MSG, # This notif is not broadcasted to all corporations
            # wars
            cls.WAR_ALLY_JOINED_WAR_AGGRESSOR_MSG,
            cls.WAR_ALLY_JOINED_WAR_ALLY_MSG,
            cls.WAR_ALLY_JOINED_WAR_DEFENDER_MSG,
            cls.WAR_CORP_WAR_SURRENDER_MSG,
            cls.WAR_CORPORATION_BECAME_ELIGIBLE,
            cls.WAR_CORPORATION_NO_LONGER_ELIGIBLE,
            cls.WAR_WAR_ADOPTED,
            cls.WAR_WAR_DECLARED,
            cls.WAR_WAR_INHERITED,
            cls.WAR_WAR_RETRACTED_BY_CONCORD,
            cls.WAR_WAR_SURRENDER_OFFER_MSG,
        }

    @classmethod
    def relevant_for_moonmining(cls) -> Set["NotificationType"]:
        """Notification types about moon mining."""
        return {
            cls.MOONMINING_EXTRACTION_STARTED,
            cls.MOONMINING_EXTRACTION_CANCELLED,
            cls.MOONMINING_LASER_FIRED,
            cls.MOONMINING_EXTRACTION_FINISHED,
            cls.MOONMINING_AUTOMATIC_FRACTURE,
        }

    @classmethod
    def structure_related(cls) -> Set["NotificationType"]:
        """Notification types that are related to a structure."""
        return {
            cls.STRUCTURE_ONLINE,
            cls.STRUCTURE_FUEL_ALERT,
            cls.STRUCTURE_JUMP_FUEL_ALERT,
            cls.STRUCTURE_REFUELED_EXTRA,
            cls.STRUCTURE_SERVICES_OFFLINE,
            cls.STRUCTURE_WENT_LOW_POWER,
            cls.STRUCTURE_WENT_HIGH_POWER,
            cls.STRUCTURE_UNANCHORING,
            cls.STRUCTURE_UNDER_ATTACK,
            cls.STRUCTURE_LOST_SHIELD,
            cls.STRUCTURE_LOST_ARMOR,
            cls.STRUCTURE_DESTROYED,
            cls.OWNERSHIP_TRANSFERRED,
            cls.STRUCTURE_ANCHORING,
            cls.MOONMINING_EXTRACTION_STARTED,
            cls.MOONMINING_EXTRACTION_FINISHED,
            cls.MOONMINING_AUTOMATIC_FRACTURE,
            cls.MOONMINING_EXTRACTION_CANCELLED,
            cls.MOONMINING_LASER_FIRED,
            cls.STRUCTURE_REINFORCE_CHANGED,
            cls.ORBITAL_ATTACKED,
            cls.ORBITAL_REINFORCED,
            cls.TOWER_ALERT_MSG,
            cls.TOWER_RESOURCE_ALERT_MSG,
            cls.TOWER_REFUELED_EXTRA,
            cls.TOWER_REINFORCED_EXTRA,
        }

    @classmethod
    def relevant_for_forwarding(cls) -> Set["NotificationType"]:
        """Notification types that are forwarded to Discord."""
        my_set = cls.values_enabled()
        # if STRUCTURES_NOTIFICATION_DISABLE_ESI_FUEL_ALERTS:
        #     my_set.discard(cls.STRUCTURE_FUEL_ALERT)
        #     my_set.discard(cls.TOWER_RESOURCE_ALERT_MSG)
        return my_set

    @classmethod
    def values_enabled(cls) -> Set["NotificationType"]:
        """Values of enabled notif types only."""
        my_set = set(cls.values)  # type: ignore
        if not STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS:
            my_set.discard(cls.STRUCTURE_REFUELED_EXTRA)
            my_set.discard(cls.TOWER_REFUELED_EXTRA)
        return my_set

    @classmethod
    def choices_enabled(cls) -> List[tuple]:
        """Choices list containing enabled notif types only."""
        return [choice for choice in cls.choices if choice[0] in cls.values_enabled()]
