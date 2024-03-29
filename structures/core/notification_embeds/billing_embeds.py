"""Main logic for generating notification embeds."""

# pylint: disable=missing-class-docstring


import dhooks_lite

from django.db import models
from django.utils.translation import gettext as _
from eveuniverse.models import EveType

from app_utils.datetime import ldap_time_2_datetime

from structures.constants import EveTypeId
from structures.helpers import get_or_create_esi_obj
from structures.models import Notification, Webhook

from .helpers import gen_solar_system_text, target_datetime_formatted
from .main import NotificationBaseEmbed


class BillType(models.IntegerChoices):
    """A bill type for infrastructure hub bills."""

    UNKNOWN = 0, _("Unknown Bill")
    INFRASTRUCTURE_HUB = 7, _("Infrastructure Hub Bill")

    @classmethod
    def to_enum(cls, bill_id: int):
        """Create a new enum from a bill type ID."""
        try:
            return cls(bill_id)
        except ValueError:
            return cls.UNKNOWN


class NotificationBillingBillOutOfMoneyMsg(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        bill_type_id = self._parsed_text["billTypeID"]
        bill_type_str = BillType.to_enum(bill_type_id).label
        due_date = ldap_time_2_datetime(self._parsed_text["dueDate"])
        self._title = _("Insufficient Funds for Bill")
        self._description = _(
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
        solar_system_link = gen_solar_system_text(self._notification.eve_solar_system())
        due_date = ldap_time_2_datetime(self._parsed_text.get("dueDate"))
        self._title = _("IHub Bill About to Expire")
        self._description = _(
            "Maintenance bill for Infrastructure Hub in %(solar_system)s "
            "expires at %(due_date)s, "
            "if not paid in time this Infrastructure Hub will self-destruct."
        ) % {
            "solar_system": solar_system_link,
            "due_date": target_datetime_formatted(due_date),
        }
        self._color = Webhook.Color.DANGER
        structure_type = get_or_create_esi_obj(EveType, id=EveTypeId.IHUB)
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )


class NotificationBillingIHubDestroyedByBillFailure(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        solar_system_link = gen_solar_system_text(self._notification.eve_solar_system())
        structure_type = self._notification.eve_structure_type()
        self._title = (
            _("%s has self-destructed due to unpaid maintenance bills")
            % structure_type.name
        )
        self._description = _(
            "%(structure_type)s in %(solar_system)s has self-destructed, "
            "as the standard maintenance bills where not paid."
        ) % {"structure_type": structure_type.name, "solar_system": solar_system_link}
        self._color = Webhook.Color.DANGER
        self._thumbnail = dhooks_lite.Thumbnail(
            structure_type.icon_url(size=self.ICON_DEFAULT_SIZE)
        )
