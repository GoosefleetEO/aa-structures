from unittest.mock import patch

from django.test import TestCase

from structures.core.notification_types import NotificationType

MODULE_PATH = "structures.core.notification_types"


class TestNotificationType(TestCase):
    def test_should_return_enabled_values_only(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", False):
            values = NotificationType.values_enabled()
        # then
        self.assertNotIn(NotificationType.STRUCTURE_REFUELED_EXTRA, values)
        self.assertNotIn(NotificationType.TOWER_REFUELED_EXTRA, values)

    def test_should_return_all_values(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", True):
            values = NotificationType.values_enabled()
        # then
        self.assertIn(NotificationType.STRUCTURE_REFUELED_EXTRA, values)
        self.assertIn(NotificationType.TOWER_REFUELED_EXTRA, values)

    def test_should_return_enabled_choices_only(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", False):
            choices = NotificationType.choices_enabled()
        # then
        types = {choice[0] for choice in choices}
        self.assertNotIn(NotificationType.STRUCTURE_REFUELED_EXTRA, types)
        self.assertNotIn(NotificationType.TOWER_REFUELED_EXTRA, types)

    def test_should_return_all_choices(self):
        # when
        with patch(MODULE_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", True):
            choices = NotificationType.choices_enabled()
        # then
        types = {choice[0] for choice in choices}
        self.assertIn(NotificationType.STRUCTURE_REFUELED_EXTRA, types)
        self.assertIn(NotificationType.TOWER_REFUELED_EXTRA, types)

    def test_has_correct_esi_values(self):
        # given
        esi_valid_notification_types = {
            "AcceptedAlly",
            "AcceptedSurrender",
            "AgentRetiredTrigravian",
            "AllAnchoringMsg",
            "AllMaintenanceBillMsg",
            "AllStrucInvulnerableMsg",
            "AllStructVulnerableMsg",
            "AllWarCorpJoinedAllianceMsg",
            "AllWarDeclaredMsg",
            "AllWarInvalidatedMsg",
            "AllWarRetractedMsg",
            "AllWarSurrenderMsg",
            "AllianceCapitalChanged",
            "AllianceWarDeclaredV2",
            "AllyContractCancelled",
            "AllyJoinedWarAggressorMsg",
            "AllyJoinedWarAllyMsg",
            "AllyJoinedWarDefenderMsg",
            "BattlePunishFriendlyFire",
            "BillOutOfMoneyMsg",
            "BillPaidCorpAllMsg",
            "BountyClaimMsg",
            "BountyESSShared",
            "BountyESSTaken",
            "BountyPlacedAlliance",
            "BountyPlacedChar",
            "BountyPlacedCorp",
            "BountyYourBountyClaimed",
            "BuddyConnectContactAdd",
            "CharAppAcceptMsg",
            "CharAppRejectMsg",
            "CharAppWithdrawMsg",
            "CharLeftCorpMsg",
            "CharMedalMsg",
            "CharTerminationMsg",
            "CloneActivationMsg",
            "CloneActivationMsg2",
            "CloneMovedMsg",
            "CloneRevokedMsg1",
            "CloneRevokedMsg2",
            "CombatOperationFinished",
            "ContactAdd",
            "ContactEdit",
            "ContainerPasswordMsg",
            "ContractRegionChangedToPochven",
            "CorpAllBillMsg",
            "CorpAppAcceptMsg",
            "CorpAppInvitedMsg",
            "CorpAppNewMsg",
            "CorpAppRejectCustomMsg",
            "CorpAppRejectMsg",
            "CorpBecameWarEligible",
            "CorpDividendMsg",
            "CorpFriendlyFireDisableTimerCompleted",
            "CorpFriendlyFireDisableTimerStarted",
            "CorpFriendlyFireEnableTimerCompleted",
            "CorpFriendlyFireEnableTimerStarted",
            "CorpKicked",
            "CorpLiquidationMsg",
            "CorpNewCEOMsg",
            "CorpNewsMsg",
            "CorpNoLongerWarEligible",
            "CorpOfficeExpirationMsg",
            "CorpStructLostMsg",
            "CorpTaxChangeMsg",
            "CorpVoteCEORevokedMsg",
            "CorpVoteMsg",
            "CorpWarDeclaredMsg",
            "CorpWarDeclaredV2",
            "CorpWarFightingLegalMsg",
            "CorpWarInvalidatedMsg",
            "CorpWarRetractedMsg",
            "CorpWarSurrenderMsg",
            "CustomsMsg",
            "DeclareWar",
            "DistrictAttacked",
            "DustAppAcceptedMsg",
            "ESSMainBankLink",
            "EntosisCaptureStarted",
            "ExpertSystemExpired",
            "ExpertSystemExpiryImminent",
            "FWAllianceKickMsg",
            "FWAllianceWarningMsg",
            "FWCharKickMsg",
            "FWCharRankGainMsg",
            "FWCharRankLossMsg",
            "FWCharWarningMsg",
            "FWCorpJoinMsg",
            "FWCorpKickMsg",
            "FWCorpLeaveMsg",
            "FWCorpWarningMsg",
            "FacWarCorpJoinRequestMsg",
            "FacWarCorpJoinWithdrawMsg",
            "FacWarCorpLeaveRequestMsg",
            "FacWarCorpLeaveWithdrawMsg",
            "FacWarLPDisqualifiedEvent",
            "FacWarLPDisqualifiedKill",
            "FacWarLPPayoutEvent",
            "FacWarLPPayoutKill",
            "GameTimeAdded",
            "GameTimeReceived",
            "GameTimeSent",
            "GiftReceived",
            "IHubDestroyedByBillFailure",
            "IncursionCompletedMsg",
            "IndustryOperationFinished",
            "IndustryTeamAuctionLost",
            "IndustryTeamAuctionWon",
            "InfrastructureHubBillAboutToExpire",
            "InsuranceExpirationMsg",
            "InsuranceFirstShipMsg",
            "InsuranceInvalidatedMsg",
            "InsuranceIssuedMsg",
            "InsurancePayoutMsg",
            "InvasionCompletedMsg",
            "InvasionSystemLogin",
            "InvasionSystemStart",
            "JumpCloneDeletedMsg1",
            "JumpCloneDeletedMsg2",
            "KillReportFinalBlow",
            "KillReportVictim",
            "KillRightAvailable",
            "KillRightAvailableOpen",
            "KillRightEarned",
            "KillRightUnavailable",
            "KillRightUnavailableOpen",
            "KillRightUsed",
            "LocateCharMsg",
            "MadeWarMutual",
            "MercOfferRetractedMsg",
            "MercOfferedNegotiationMsg",
            "MissionCanceledTriglavian",
            "MissionOfferExpirationMsg",
            "MissionTimeoutMsg",
            "MoonminingAutomaticFracture",
            "MoonminingExtractionCancelled",
            "MoonminingExtractionFinished",
            "MoonminingExtractionStarted",
            "MoonminingLaserFired",
            "MutualWarExpired",
            "MutualWarInviteAccepted",
            "MutualWarInviteRejected",
            "MutualWarInviteSent",
            "NPCStandingsGained",
            "NPCStandingsLost",
            "OfferToAllyRetracted",
            "OfferedSurrender",
            "OfferedToAlly",
            "OfficeLeaseCanceledInsufficientStandings",
            "OldLscMessages",
            "OperationFinished",
            "OrbitalAttacked",
            "OrbitalReinforced",
            "OwnershipTransferred",
            "RaffleCreated",
            "RaffleExpired",
            "RaffleFinished",
            "ReimbursementMsg",
            "ResearchMissionAvailableMsg",
            "RetractsWar",
            "SeasonalChallengeCompleted",
            "SovAllClaimAquiredMsg",
            "SovAllClaimLostMsg",
            "SovCommandNodeEventStarted",
            "SovCorpBillLateMsg",
            "SovCorpClaimFailMsg",
            "SovDisruptorMsg",
            "SovStationEnteredFreeport",
            "SovStructureDestroyed",
            "SovStructureReinforced",
            "SovStructureSelfDestructCancel",
            "SovStructureSelfDestructFinished",
            "SovStructureSelfDestructRequested",
            "SovereigntyIHDamageMsg",
            "SovereigntySBUDamageMsg",
            "SovereigntyTCUDamageMsg",
            "StationAggressionMsg1",
            "StationAggressionMsg2",
            "StationConquerMsg",
            "StationServiceDisabled",
            "StationServiceEnabled",
            "StationStateChangeMsg",
            "StoryLineMissionAvailableMsg",
            "StructureAnchoring",
            "StructureCourierContractChanged",
            "StructureDestroyed",
            "StructureFuelAlert",
            "StructureImpendingAbandonmentAssetsAtRisk",
            "StructureItemsDelivered",
            "StructureItemsMovedToSafety",
            "StructureLostArmor",
            "StructureLostShields",
            "StructureOnline",
            "StructureServicesOffline",
            "StructureUnanchoring",
            "StructureUnderAttack",
            "StructureWentHighPower",
            "StructureWentLowPower",
            "StructuresJobsCancelled",
            "StructuresJobsPaused",
            "StructuresReinforcementChanged",
            "TowerAlertMsg",
            "TowerResourceAlertMsg",
            "TransactionReversalMsg",
            "TutorialMsg",
            "WarAdopted",
            "WarAllyInherited",
            "WarAllyOfferDeclinedMsg",
            "WarConcordInvalidates",
            "WarDeclared",
            "WarEndedHqSecurityDrop",
            "WarHQRemovedFromSpace",
            "WarInherited",
            "WarInvalid",
            "WarRetracted",
            "WarRetractedByConcord",
            "WarSurrenderDeclinedMsg",
            "WarSurrenderOfferMsg",
        }
        # when
        for ntype in NotificationType.esi_notifications():
            with self.subTest(notification_type=ntype):
                self.assertIn(ntype, esi_valid_notification_types)