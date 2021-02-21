from celery import chain, shared_task

from django.contrib.auth.models import User

from allianceauth.notifications import notify
from allianceauth.services.hooks import get_extension_logger
from allianceauth.services.tasks import QueueOnce
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import STRUCTURES_TASKS_TIME_LIMIT
from .models import EveSovereigntyMap, Notification, Owner, Webhook

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

TASK_PRIO_HIGH = 2


@shared_task(base=QueueOnce)
def send_messages_for_webhook(webhook_pk: int) -> None:
    """sends all currently queued messages for given webhook to Discord"""
    Webhook.objects.send_queued_messages_for_webhook(webhook_pk)


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_structures_for_owner(owner_pk, user_pk=None):
    """fetches all structures for owner and update the corp assets related to them from ESI"""
    chain(
        update_structures_esi_for_owner.si(owner_pk, user_pk),
        update_structures_assets_for_owner.si(owner_pk, user_pk),
    ).delay()


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_structures_esi_for_owner(owner_pk, user_pk=None):
    """fetches all structures for owner"""
    _get_owner(owner_pk).update_structures_esi(_get_user(user_pk))


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_structures_assets_for_owner(owner_pk, user_pk=None):
    """fetches all structures for owner"""
    _get_owner(owner_pk).update_asset_esi(_get_user(user_pk))


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_structures():
    """fetches all structures for all active owner from ESI"""
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
def update_sov_map():
    """updates the sovereignty map"""
    EveSovereigntyMap.objects.update_from_esi()


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_all_structures():
    """main task for starting regular update of all structures
    and related data from ESI
    """
    chain(update_sov_map.si(), update_structures.si()).delay()


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def process_notifications_for_owner(owner_pk, user_pk=None):
    """fetches all notification for owner from ESI and processes them"""
    owner = _get_owner(owner_pk)
    owner.fetch_notifications_esi(_get_user(user_pk))
    owner.send_new_notifications()
    for webhook in owner.webhooks.filter(is_active=True):
        if webhook.queue_size() > 0:
            send_messages_for_webhook.apply_async(
                kwargs={"webhook_pk": webhook.pk}, priority=TASK_PRIO_HIGH
            )


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def fetch_all_notifications():
    """fetch notifications for all owners"""
    for owner in Owner.objects.all():
        if owner.is_active:
            process_notifications_for_owner.apply_async(
                kwargs={"owner_pk": owner.pk}, priority=TASK_PRIO_HIGH
            )


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def send_notifications(notification_pks: list) -> None:
    """send notifications defined by list of pks (used for admin action)"""
    notifications = Notification.objects.filter(pk__in=notification_pks)
    if notifications:
        logger.info(
            "Trying to send {} notifications to webhooks...".format(
                len(notification_pks)
            )
        )
        webhooks = set()
        for notif in notifications:
            for webhook in notif.owner.webhooks.filter(is_active=True):
                webhooks.add(webhook)
                if (
                    str(notif.notif_type) in webhook.notification_types
                    and not notif.filter_for_npc_attacks()
                    and not notif.filter_for_alliance_level()
                ):
                    notif.send_to_webhook(webhook)

        for webhook in webhooks:
            send_messages_for_webhook.apply_async(
                kwargs={"webhook_pk": webhook.pk}, priority=TASK_PRIO_HIGH
            )


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def send_test_notifications_to_webhook(webhook_pk, user_pk=None) -> None:
    """sends test notification to given webhook"""
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


def _get_owner(owner_pk: int) -> Owner:
    """returns the owner or raises exception"""
    try:
        owner = Owner.objects.get(pk=owner_pk)
    except Owner.DoesNotExist:
        raise Owner.DoesNotExist(
            "Requested owner with pk {} does not exist".format(owner_pk)
        )
    return owner


def _get_user(user_pk: int) -> User:
    """returns the user or None. Logs if user is requested but can't be found."""
    user = None
    if user_pk:
        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            logger.warning("Ignoring non-existing user with pk {}".format(user_pk))
    return user
