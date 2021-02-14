import json
from time import sleep
from typing import List, Tuple

import dhooks_lite
from simple_mq import SimpleMQ

from django.contrib.auth.models import User
from django.core.cache import cache

from allianceauth.services.hooks import get_extension_logger

from app_utils.json import JSONDateTimeDecoder, JSONDateTimeEncoder
from app_utils.logging import LoggerAddTag

from .. import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class DiscordWebhookMixin:
    """Mixing adding a queued Discord webhook to a model

    excepts the model to have the following two properties:
    - name: name of the webhook (string)
    - url: url of the webhook (string)
    """

    # delay in seconds between every message sent to Discord
    # this needs to be >= 1 to prevent 429 Too Many Request errors
    SEND_DELAY = 2

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._main_queue = SimpleMQ(
            cache.get_master_client(), f"{__title__}_webhook_{self.pk}_main"
        )
        self._error_queue = SimpleMQ(
            cache.get_master_client(), f"{__title__}_webhook_{self.pk}_errors"
        )

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return "{}(pk={}, name='{}')".format(
            self.__class__.__name__, self.pk, self.name
        )

    def queue_size(self) -> int:
        """returns current size of the queue"""
        return self._main_queue.size()

    def clear_queue(self) -> int:
        """deletes all messages from the queue. Returns number of cleared messages."""
        counter = 0
        while True:
            y = self._main_queue.dequeue()
            if y is None:
                break
            else:
                counter += 1

        return counter

    def send_message(
        self,
        content: str = None,
        embeds: List[dhooks_lite.Embed] = None,
        tts: bool = None,
        username: str = None,
        avatar_url: str = None,
    ) -> int:
        """Adds Discord message to queue for later sending

        Returns updated size of queue
        Raises ValueError if mesage is incomplete
        """
        if not content and not embeds:
            raise ValueError("Message must have content or embeds to be valid")

        if embeds:
            embeds_list = [obj.asdict() for obj in embeds]
        else:
            embeds_list = None

        message = dict()
        if content:
            message["content"] = content
        if embeds_list:
            message["embeds"] = embeds_list
        if tts:
            message["tts"] = tts
        if username:
            message["username"] = username
        if avatar_url:
            message["avatar_url"] = avatar_url

        return self._main_queue.enqueue(json.dumps(message, cls=JSONDateTimeEncoder))

    def send_queued_messages(self) -> int:
        """sends all messages in the queue to this webhook

        returns number of successfull sent messages

        Messages that could not be sent are put back into the queue for later retry
        """
        message_count = 0
        while True:
            message_json = self._main_queue.dequeue()
            if message_json:
                message = json.loads(message_json, cls=JSONDateTimeDecoder)
                logger.debug("Sending message to webhook %s", self)
                if self._send_message_to_webhook(message):
                    message_count += 1
                else:
                    self._error_queue.enqueue(message_json)

                sleep(self.SEND_DELAY)

            else:
                break

        while True:
            message_json = self._error_queue.dequeue()
            if message_json:
                self._main_queue.enqueue(message_json)
            else:
                break

        return message_count

    def _send_message_to_webhook(self, message: dict) -> bool:
        """sends message directly to webhook

        returns True if successful, else False
        """
        hook = dhooks_lite.Webhook(url=self.url)
        if message.get("embeds"):
            embeds = [
                dhooks_lite.Embed.from_dict(embed_dict)
                for embed_dict in message.get("embeds")
            ]
        else:
            embeds = None

        response = hook.execute(
            content=message.get("content"),
            embeds=embeds,
            username=message.get("username"),
            avatar_url=message.get("avatar_url"),
            wait_for_response=True,
        )
        logger.debug("headers: %s", response.headers)
        logger.debug("status_code: %s", response.status_code)
        logger.debug("content: %s", response.content)
        if response.status_ok:
            return True
        else:
            logger.warning(
                "Failed to send message to Discord. HTTP status code: %d, response: %s",
                response.status_code,
                response.content,
            )
            return False

    @classmethod
    def create_link(cls, name: str, url: str) -> str:
        """creates a link for messages of this webhook"""
        return f"[{str(name)}]({str(url)})"

    def send_test_message(self, user: User = None) -> Tuple[str, bool]:
        """Sends a test notification to this webhook and returns send report"""
        try:
            user_text = f" sent by **{user}**" if user else ""
            message = {
                "content": f"Test message for webhook **{self.name}**{user_text}",
                "username": __title__,
            }
            success = self._send_message_to_webhook(message)
        except Exception as ex:
            logger.warning(
                "Failed to send test notification to webhook %s: %s",
                self,
                ex,
                exc_info=True,
            )
            return type(ex).__name__, False
        else:
            return "(no info)", success

    @staticmethod
    def default_username() -> str:
        """sets the apps title as username for all messages"""
        return __title__
