from time import sleep

from celery import shared_task, chain

from django.contrib.auth.models import User

from allianceauth.services.hooks import get_extension_logger
from allianceauth.notifications import notify

from . import __title__
from .app_settings import STRUCTURES_TASKS_TIME_LIMIT
from .utils import LoggerAddTag, make_logger_prefix
from .models import Owner, Notification, Webhook, EveSovereigntyMap


logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_structures_for_owner(owner_pk, user_pk=None):
    """fetches all structures for owner from ESI"""
    _get_owner(owner_pk).update_structures_esi(_get_user(user_pk))


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def update_structures():
    """fetches all structures for all active owner from ESI"""
    for owner in Owner.objects.all():
        if owner.is_active:
            update_structures_for_owner.delay(owner.pk)


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
def fetch_notifications_for_owner(owner_pk, user_pk=None):
    """fetches all notification for owner from ESI and proceses them"""
    _get_owner(owner_pk).fetch_notifications_esi(_get_user(user_pk))


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def fetch_all_notifications():
    """fetch notifications for all owners"""
    for owner in Owner.objects.all():
        if owner.is_active:
            fetch_notifications_for_owner.apply_async(
                kwargs={"owner_pk": owner.pk}, priority=2
            )


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def send_new_notifications_for_owner(owner_pk, rate_limited=True, user_pk=None):
    """forwards new notification for this owner to configured webhooks"""
    _get_owner(owner_pk).send_new_notifications(rate_limited, _get_user(user_pk))


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def send_all_new_notifications(rate_limited=True):
    """sends all unsent notifications to active webhooks and adds timers"""
    send_tasks = list()
    for owner in Owner.objects.all():
        if owner.is_active:
            send_tasks.append(
                send_new_notifications_for_owner.si(
                    owner_pk=owner.pk, rate_limited=rate_limited
                )
            )

    chain(send_tasks).apply_async(priority=2)


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def send_notifications(notification_pks: list, rate_limited=True):
    """send notifications defined by list of pks"""
    notifications = Notification.objects.filter(pk__in=notification_pks)
    if notifications:
        logger.info(
            "Trying to send {} notifications to webhooks...".format(
                len(notification_pks)
            )
        )
        for n in notifications:
            for webhook in n.owner.webhooks.all():
                if (
                    str(n.notification_type) in webhook.notification_types
                    and not n.filter_for_npc_attacks()
                    and not n.filter_for_alliance_level()
                ):
                    n.send_to_webhook(webhook)
            if rate_limited:
                sleep(1)


@shared_task(time_limit=STRUCTURES_TASKS_TIME_LIMIT)
def send_test_notifications_to_webhook(webhook_pk, user_pk=None):
    """sends test notification to given webhook"""

    add_prefix = make_logger_prefix("test notification")
    try:
        webhook = Webhook.objects.get(pk=webhook_pk)
        add_prefix = make_logger_prefix(webhook)
        send_report = webhook.send_test_notification()
        error_code = None
    except Exception as ex:
        logger.exception("Failed to send test notification")
        send_report = None
        error_code = str(ex)

    success = error_code is None
    if user_pk:
        try:
            message = 'Test notification to webhook "{}" {}.\n'.format(
                webhook, "completed successfully" if success else "has failed"
            )
            if success:
                message += "send report:\n{}".format(send_report)
            else:
                message += "Error code: {}".format(error_code)

            notify(
                user=User.objects.get(pk=user_pk),
                title='{}: Test notification to "{}": {}'.format(
                    __title__, webhook, "OK" if success else "FAILED"
                ),
                message=message,
                level="success" if success else "danger",
            )
        except Exception as ex:
            logger.exception(
                add_prefix(
                    "An unexpected error ocurred while trying to "
                    + "report to user: {}".format(ex)
                )
            )


def _get_owner(owner_pk) -> Owner:
    """returns the owner or raises exception"""
    try:
        owner = Owner.objects.get(pk=owner_pk)
    except Owner.DoesNotExist:
        raise Owner.DoesNotExist(
            "Requested owner with pk {} does not exist".format(owner_pk)
        )
    return owner


def _get_user(user_pk) -> User:
    """returns the user or None. Logs if user is requested but can't be found."""
    user = None
    if user_pk:
        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            logger.warning("Ignoring non-existing user with pk {}".format(user_pk))
    return user
