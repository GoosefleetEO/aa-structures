"""War embeds."""

# pylint: disable=missing-class-docstring


import dhooks_lite

from django.utils.html import strip_tags
from django.utils.translation import gettext as __
from eveuniverse.models import EveEntity

from app_utils.datetime import ldap_time_2_datetime

from structures.models import Notification, Webhook

from .helpers import (
    gen_eve_entity_link,
    gen_eve_entity_link_from_id,
    target_datetime_formatted,
)
from .main import NotificationBaseEmbed


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
            "declared_by": gen_eve_entity_link(self._declared_by),
            "against": gen_eve_entity_link(self._against),
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
            "declared_by": gen_eve_entity_link(self._declared_by),
            "against": gen_eve_entity_link(self._against),
            "alliance": gen_eve_entity_link(alliance),
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
            "declared_by": gen_eve_entity_link(self._declared_by),
            "against": gen_eve_entity_link(self._against),
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
            "declared_by": gen_eve_entity_link(self._declared_by),
            "against": gen_eve_entity_link(self._against),
            "alliance": gen_eve_entity_link(alliance),
            "quitter": gen_eve_entity_link(quitter),
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
            "declared_by": gen_eve_entity_link(self._declared_by),
            "against": gen_eve_entity_link(self._against),
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
        owner_1_link = gen_eve_entity_link(owner_1)
        owner_2_link = gen_eve_entity_link_from_id(self._parsed_text.get("ownerID2"))
        self._title = __("%s has offered a surrender") % (owner_1,)
        self._description = __(
            "%s has offered to end the war with %s in the exchange for %s ISK. "
            "If accepted, the war will end in 24 hours and your organizations will "
            "be unable to declare new wars against each other for the next 2 weeks."
        ) % (owner_1_link, owner_2_link, f"{isk_value:,.2f}")
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
            "aggressor": gen_eve_entity_link(aggressor),
            "ally": gen_eve_entity_link(ally),
            "defender": gen_eve_entity_link(defender),
            "start_time": target_datetime_formatted(start_time),
        }
        self._thumbnail = dhooks_lite.Thumbnail(
            ally.icon_url(size=self.ICON_DEFAULT_SIZE)
        )
        self._color = Webhook.Color.WARNING
