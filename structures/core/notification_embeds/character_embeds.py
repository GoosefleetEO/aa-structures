"""Character & corporation embeds."""

# pylint: disable=missing-class-docstring

import dhooks_lite

from django.utils.translation import gettext as __
from eveuniverse.models import EveEntity

from structures.models import Notification, Webhook

from .helpers import (
    gen_corporation_link,
    gen_eve_entity_link,
    gen_eve_entity_link_from_id,
)
from .main import NotificationBaseEmbed


class NotificationCorpCharEmbed(NotificationBaseEmbed):
    def __init__(self, notification: Notification) -> None:
        super().__init__(notification)
        self._character, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["charID"]
        )
        self._corporation, _ = EveEntity.objects.get_or_create_esi(
            id=self._parsed_text["corpID"]
        )
        self._character_link = gen_eve_entity_link(self._character)
        self._corporation_link = gen_corporation_link(self._corporation.name)
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
        inviting_character = gen_eve_entity_link_from_id(
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
