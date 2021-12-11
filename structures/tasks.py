from typing import Iterable, Optional

from celery import chain, shared_task

from django.contrib.auth.models import User

from allianceauth.notifications import notify
from allianceauth.services.hooks import get_extension_logger
from allianceauth.services.tasks import QueueOnce
from app_utils.esi import fetch_esi_status
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import STRUCTURES_TASKS_TIME_LIMIT
from .models import (
    EveSovereigntyMap,
    FuelAlertConfig,
    JumpFuelAlertConfig,
    Notification,
    Owner,
    Webhook,
)

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

TASK_PRIO_HIGH = 2


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_all_structures():
    """Update all structures.

    Main task for starting regular update of all structures
    and related data from ESI.
    """
    if not fetch_esi_status().is_ok:
        logger.warning("ESI currently not available. Aborting.")
    else:
        chain(update_sov_map.si(), update_structures.si()).delay()


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_sov_map():
    """Update sovereignty map from ESI."""
    EveSovereigntyMap.objects.update_from_esi()


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_structures():
    """Update all structures for all active owners from ESI."""
    for owner in Owner.objects.all():
        if owner.is_active:
            update_structures_for_owner.delay(owner.pk)

    if (
        Owner.objects.filter(is_active=True).count() > 0
        and Owner.objects.filter(is_active=True, is_alliance_main=True).count() == 0
    ):
        logger.warning(
            "No owner configured to process alliance wide notifications. "
            "Please set 'is alliance main' to True for the designated owner."
        )


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_all_for_owner(owner_pk, user_pk=None):
    """Update structures and notifications for owner from ESI."""
    chain(
        update_structures_for_owner.si(owner_pk, user_pk),
        process_notifications_for_owner.si(owner_pk, user_pk),
    ).delay()


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_structures_for_owner(owner_pk, user_pk=None):
    """Fetch all structures for owner and update related corp assets from ESI."""
    if not fetch_esi_status().is_ok:
        logger.warning("ESI currently not available. Aborting.")
    else:
        chain(
            update_structures_esi_for_owner.si(owner_pk, user_pk),
            update_structures_assets_for_owner.si(owner_pk, user_pk),
        ).delay()


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_structures_esi_for_owner(owner_pk, user_pk=None):
    """Update all structures for owner for ESI."""
    owner = Owner.objects.get(pk=owner_pk)
    owner.update_structures_esi(_get_user(user_pk))


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_structures_assets_for_owner(owner_pk, user_pk=None):
    """Update all related assets for owner."""
    owner = Owner.objects.get(pk=owner_pk)
    owner.update_asset_esi(_get_user(user_pk))


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def fetch_all_notifications():
    """Fetch notifications for all owners and send new fuel notifications."""
    for owner in Owner.objects.all():
        if owner.is_active:
            owner.update_is_up()
            process_notifications_for_owner.apply_async(
                kwargs={"owner_pk": owner.pk}, priority=TASK_PRIO_HIGH
            )
    for config_pk in FuelAlertConfig.objects.filter(is_enabled=True).values_list(
        "pk", flat=True
    ):
        send_structure_fuel_notifications_for_config.delay(config_pk)
    for config_pk in JumpFuelAlertConfig.objects.filter(is_enabled=True).values_list(
        "pk", flat=True
    ):
        send_jump_fuel_notifications_for_config.delay(config_pk)


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def process_notifications_for_owner(owner_pk, user_pk=None):
    """Fetch all notification for owner from ESI and processes them."""
    if not fetch_esi_status().is_ok:
        logger.warning("ESI currently not available. Aborting.")
    else:
        owner = Owner.objects.get(pk=owner_pk)
        owner.fetch_notifications_esi(_get_user(user_pk))
        owner.send_new_notifications()
        send_queued_messages_for_webhooks(owner.webhooks.filter(is_active=True))


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def send_structure_fuel_notifications_for_config(config_pk: int):
    FuelAlertConfig.objects.get(pk=config_pk).send_new_notifications()
    send_queued_messages_for_webhooks(FuelAlertConfig.relevant_webhooks())


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def send_jump_fuel_notifications_for_config(config_pk: int):
    JumpFuelAlertConfig.objects.get(pk=config_pk).send_new_notifications()
    send_queued_messages_for_webhooks(JumpFuelAlertConfig.relevant_webhooks())


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def send_notifications(notification_pks: list) -> None:
    """Send notifications defined by list of pks (used for admin action)."""
    notifications = Notification.objects.filter(pk__in=notification_pks)
    if notifications:
        logger.info("Trying to send %s notifications to webhooks...", notification_pks)
        for notif in notifications:
            notif.send_to_configured_webhooks()
        send_queued_messages_for_webhooks(Webhook.objects.filter(is_active=True))


def send_queued_messages_for_webhooks(webhooks: Iterable[Webhook]):
    """Send queued message for given webhooks."""
    for webhook in webhooks:
        if webhook.queue_size() > 0:
            send_messages_for_webhook.apply_async(
                kwargs={"webhook_pk": webhook.pk}, priority=TASK_PRIO_HIGH
            )


@shared_task(base=QueueOnce)
def send_messages_for_webhook(webhook_pk: int) -> None:
    """Send all currently queued messages for given webhook to Discord."""
    Webhook.objects.send_queued_messages_for_webhook(webhook_pk)


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def send_test_notifications_to_webhook(webhook_pk, user_pk=None) -> None:
    """Send test notification to given webhook."""
    try:
        webhook = Webhook.objects.get(pk=webhook_pk)
        if user_pk:
            user = User.objects.get(pk=user_pk)
        else:
            user = None
    except Webhook.DoesNotExist:
        logger.error("Webhook with pk = %s does not exist. Aborting.", webhook_pk)
    except User.DoesNotExist:
        logger.error("User with pk = %s does not exist. Aborting.", user_pk)
    else:
        send_report, send_success = webhook.send_test_message(user)
        if user:
            message = 'Test notification to webhook "{}" {}.\n'.format(
                webhook, "completed successfully" if send_success else "has failed"
            )
            if not send_success:
                message += "Error: {}".format(send_report)

            notify(
                user=user,
                title='{}: Test notification to "{}": {}'.format(
                    __title__, webhook, "OK" if send_success else "FAILED"
                ),
                message=message,
                level="success" if send_success else "danger",
            )


def _get_user(user_pk: int) -> Optional[User]:
    """Fetch the user or return None."""
    user = None
    if user_pk:
        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            logger.warning("Ignoring non-existing user with pk %s", user_pk)
    return user
