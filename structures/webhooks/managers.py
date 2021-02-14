from django.db import models

from allianceauth.services.hooks import get_extension_logger

from .. import __title__
from app_utils.logging import LoggerAddTag

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class WebhookBaseManager(models.Manager):
    def send_queued_messages_for_webhook(self, webhook_pk: int) -> None:
        """sends all currently queued messages to given webhook

        !! this method should be called from a tasks with QueueOnce !!
        """
        try:
            webhook = self.get(pk=webhook_pk)
        except self.model.DoesNotExist:
            logger.error("Webhook with pk = %s does not exist. Aborting.", webhook_pk)
        else:
            if not webhook.is_active:
                logger.info("Tracker %s: Webhook disabled - skipping sending", webhook)
                return

            logger.info("Started sending messages to webhook %s", webhook)
            webhook.send_queued_messages()
            logger.info("Completed sending messages to webhook %s", webhook)
