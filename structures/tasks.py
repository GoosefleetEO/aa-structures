import logging
import os
import json
from time import sleep

from celery import shared_task, group, chain

from django.db import transaction
from django.conf import settings
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import now

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.notifications import notify
from allianceauth.eveonline.models import EveCorporationInfo, EveCharacter
from esi.clients import esi_client_factory
from esi.errors import TokenExpiredError, TokenInvalidError, TokenError
from esi.models import Token

from . import __title__
from .app_settings import STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED
from .utils import LoggerAddTag, make_logger_prefix, get_swagger_spec_path
from .models import *


logger = LoggerAddTag(logging.getLogger(__name__), __package__)


def _get_token_for_owner(owner: Owner, add_prefix: make_logger_prefix) -> list:        
    """returns a valid token for given owner or an error code"""
    
    token = None
    error = Owner.ERROR_NONE

    # abort if character is not configured
    if owner.character is None:
        logger.error(add_prefix(
            'No character configured to sync'
        ))           
        error = Owner.ERROR_NO_CHARACTER        

    # abort if character does not have sufficient permissions
    elif not owner.character.user.has_perm(
            'structures.add_structure_owner'
        ):
        logger.error(add_prefix(
            'Character does not have sufficient permission '
            + 'to sync structures'
        ))            
        error = Owner.ERROR_INSUFFICIENT_PERMISSIONS        

    else:
        try:
            # get token    
            token = Token.objects.filter(
                user=owner.character.user, 
                character_id=owner.character.character.character_id
            ).require_scopes(
                Owner.get_esi_scopes()
            ).require_valid().first()
        except TokenInvalidError:        
            logger.error(add_prefix(
                'Invalid token for fetching structures'
            ))            
            error = Owner.ERROR_TOKEN_INVALID                
        except TokenExpiredError:            
            logger.error(add_prefix(
                'Token expired for fetching structures'
            ))
            error = Owner.ERROR_TOKEN_EXPIRED        
        else:
            if not token:
                logger.error(add_prefix(
                    'Missing token for fetching structures'
                ))            
                error = Owner.ERROR_TOKEN_INVALID
            
    if token:
        logger.debug('Using token: {}'.format(token))
    
    return token, error


def _send_report_to_user(
    owner: Owner, 
    topic: str,
    topic_count: int,
    success: bool,
    error_code,
    user_pk, 
    add_prefix: make_logger_prefix
):
    try:
        message = 'Syncing of {} for "{}" {}.\n'.format(
            topic,
            owner.corporation.corporation_name,
            'completed successfully' if success else 'has failed'
        )
        if success:
            message += '{:,} {} synced.'.format(                
                topic_count,
                topic
            )
        else:
            message += 'Error code: {}'.format(error_code)
        
        notify(
            user=User.objects.get(pk=user_pk),
            title='{}: {} updated for {}: {}'.format(
                __title__,
                topic,
                owner.corporation.corporation_name,
                'OK' if success else 'FAILED'
            ),
            message=message,
            level='success' if success else 'danger'
        )
    except Exception as ex:
        logger.error(add_prefix(
            'An unexpected error ocurred while trying to '
            + 'report to user: {}'. format(ex)
        ))

@shared_task
def update_structures_for_owner(
    owner_pk, 
    force_sync: bool = False, 
    user_pk = None
):
    """fetches structures from one owner"""
    
    try:
        owner = Owner.objects.get(pk=owner_pk)
    except Owner.DoesNotExist:
        raise Owner.DoesNotExist(
            "Requested owner with pk {} does not exist".format(owner_pk)
        )

    add_prefix = make_logger_prefix(owner.corporation.corporation_ticker)

    try:        
        owner.structures_last_sync = now()        
        owner.save()
        
        token, error = _get_token_for_owner(owner, add_prefix)
        if not token:
            owner.structures_last_error = error
            owner.save()
            raise RuntimeError()        
        
        try:
            # fetching data from ESI
            logger.info(add_prefix('Fetching structures from ESI - page 1'))
            esi_client = esi_client_factory(
                token=token, 
                spec_file=get_swagger_spec_path()
            )

            # get structures from first page
            operation = \
                esi_client.Corporation.get_corporations_corporation_id_structures(
                    corporation_id=owner.corporation.corporation_id
                )
            operation.also_return_response = True
            structures, response = operation.result()
            pages = int(response.headers['x-pages'])
            
            # add structures from additional pages if any            
            for page in range(2, pages + 1):
                logger.info(add_prefix(
                    'Fetching structures from ESI - page {}'.format(page)
                ))
                structures += esi_client.Corporation.get_corporations_corporation_id_structures(
                    corporation_id=owner.corporation_id,
                    page=page
                ).result()
            
            # fetch additional information for structures
            for structure in structures:
                structure_info = \
                    esi_client.Universe.get_universe_structures_structure_id(
                        structure_id=structure['structure_id']
                    ).result()
                structure['name'] = structure_info['name']
                structure['position'] = structure_info['position']                

            if settings.DEBUG:
                # store to disk (for debugging)
                with open(
                    'structures_raw_{}.json'.format(
                        owner.corporation.corporation_id
                    ), 
                    'w', 
                    encoding='utf-8'
                ) as f:
                    json.dump(
                        structures, 
                        f, 
                        cls=DjangoJSONEncoder, 
                        sort_keys=True, 
                        indent=4
                    )
                        
            logger.info(add_prefix(
                'Storing update for {:,} structures'.format(
                    len(structures)
            )))
            with transaction.atomic():
                Structure.objects.filter(owner=owner).delete()
                for structure in structures:                    
                    Structure.objects.update_or_create_from_dict(
                        structure,
                        owner,
                        esi_client
                    )                
                
                owner.structures_last_error = Owner.ERROR_NONE
                owner.save()

        except Exception as ex:
            logger.exception(add_prefix(
                'An unexpected error ocurred {}'. format(ex)
            ))                                
            owner.structures_last_error = Owner.ERROR_UNKNOWN
            owner.save()       
            raise ex     

    except Exception as ex:
        success = False              
        error_code = str(ex)
    else:
        success = True
        error_code = None

    if user_pk:
        _send_report_to_user(
            owner, 
            'structures', 
            owner.structure_set.count(),
            success, 
            error_code,
            user_pk, 
            add_prefix
        )
        
    return success


@shared_task
def update_all_structures(force_sync = False):
    """fetches structures from all known owners"""
    for owner in Owner.objects.all():
        update_structures_for_owner.delay(owner.pk, force_sync=force_sync)


@shared_task
def fetch_notifications_for_owner(
    owner_pk, 
    force_sync: bool = False,    
    user_pk = None
):
    """fetches notification for owner and proceses them"""
    
    try:
        owner = Owner.objects.get(pk=owner_pk)
    except Owner.DoesNotExist:
        raise Owner.DoesNotExist(
            "Requested owner with pk {} does not exist".format(owner_pk)
        )

    add_prefix = make_logger_prefix(owner.corporation.corporation_ticker)
    notifications_count = 0

    try:        
        owner.notifications_last_sync = now()        
        owner.save()
        
        token, error = _get_token_for_owner(owner, add_prefix)
        if not token:
            owner.notifications_last_error = error
            owner.save()
            raise RuntimeError()
        
        # fetch notifications from ESI
        try:
            # fetching data from ESI
            logger.info(add_prefix('Fetching notifications from ESI'))
            esi_client = esi_client_factory(
                token=token, 
                spec_file=get_swagger_spec_path()
            )            
            notifications = \
                esi_client.Character.get_characters_character_id_notifications(
                    character_id=token.character_id
                ).result()
            
            if settings.DEBUG:
                # store to disk (for debugging)
                with open(
                    file='notifications_raw_{}.json'.format(
                        owner.corporation.corporation_id
                    ), 
                    mode='w',
                    encoding='utf-8'
                ) as f:
                    json.dump(
                        notifications, 
                        f, 
                        cls=DjangoJSONEncoder, 
                        sort_keys=True, 
                        indent=4
                    )

            if STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED:
                # store notifications to disk in continuous file per corp
                folder_name = 'structures_notifications_archive'
                os.makedirs(folder_name, exist_ok=True)
                filename = '{}/notifications_{}_{}.txt'.format(
                    folder_name,
                    owner.corporation.corporation_id,
                    now().date().isoformat()
                )
                logger.info(add_prefix(
                    'Storing notifications into archive file: {}'.format(
                        filename
                )))
                with open(
                    file=filename, 
                    mode='a',
                    encoding='utf-8'
                ) as f:
                    f.write('[{}] {}:\n'.format(
                        now().strftime(DATETIME_FORMAT), 
                        owner.corporation.corporation_ticker
                    ))
                    json.dump(
                        notifications, 
                        f, 
                        cls=DjangoJSONEncoder, 
                        sort_keys=True, 
                        indent=4
                    )
                    f.write('\n')
            
            logger.debug(add_prefix(
                'Processing {:,} notifications received from ESI'.format(
                    len(notifications)
            )))
            
            # update notifications in local DB
            new_notifications_count = 0
            with transaction.atomic():                                    
                for notification in notifications:                        
                    notification_type = \
                        Notification.get_matching_notification_type(
                            notification['type']
                        )
                    if notification_type:
                        notifications_count += 1
                        sender_type = \
                            EveEntity.get_matching_entity_type(
                                notification['sender_type']
                            )
                        if sender_type != EveEntity.CATEGORY_OTHER:
                            sender, _ = EveEntity\
                            .objects.get_or_create_esi(
                                notification['sender_id'],
                                esi_client
                            )
                        else:
                            sender, _ = EveEntity\
                                .objects.get_or_create(
                                    id=notification['sender_id'],
                                    defaults={
                                        'category': sender_type
                                    }
                                )
                        text = notification['text'] \
                            if 'text' in notification else None
                        is_read = notification['is_read'] \
                            if 'is_read' in notification else None
                        obj, created = Notification.objects.update_or_create(
                            notification_id=notification['notification_id'],
                            owner=owner,
                            defaults={
                                'sender': sender,
                                'timestamp': notification['timestamp'],
                                'notification_type': notification_type,
                                'text': text,
                                'is_read': is_read,
                                'last_updated': owner.notifications_last_sync,
                            }                        
                        )
                        if created:
                            obj.created = now()
                            obj.save()
                            new_notifications_count += 1
                
                owner.notifications_last_error = Owner.ERROR_NONE
                owner.save()

            if new_notifications_count > 0:
                logger.info(add_prefix(
                    'Received {} new notifications from ESI'.format(
                        new_notifications_count
                )))
            else:
                logger.info(add_prefix(
                    'No new notifications received from ESI'
                ))

        except Exception as ex:
            logger.exception(add_prefix(
                'An unexpected error ocurred {}'. format(ex)
            ))                                
            owner.notifications_last_error = Owner.ERROR_UNKNOWN
            owner.save()        
            raise ex

    except Exception as ex:
        success = False
        error_code = str(ex)        
    else:
        success = True
        error_code = None

    if user_pk:        
        _send_report_to_user(
            owner, 
            'notifications', 
            notifications_count,
            success, 
            error_code,
            user_pk, 
            add_prefix
        )
    
    return success


@shared_task
def fetch_all_notifications(force_sync = False):
    """fetch notifications for all owners"""
    for owner in Owner.objects.all():
        fetch_notifications_for_owner.delay(owner.pk, force_sync=force_sync)


@shared_task
def send_new_notifications_for_owner(owner_pk, rate_limited = True):
    """forwards new notification for this owner to Discord"""
    
    def get_esi_client(owner: Owner) -> object:
        """returns a new ESI client for the given owner"""
        token, error = _get_token_for_owner(owner, add_prefix)
        if not token:
            owner.forwarding_last_error = error
            owner.save()
            raise TokenError(add_prefix(
                'Failed to get a valid token'
            ))

        return esi_client_factory(
            token=token, 
            spec_file=get_swagger_spec_path()
        )     

    try:
        owner = Owner.objects.get(pk=owner_pk)
    except Owner.DoesNotExist:
        raise Owner.DoesNotExist(
            "Requested owner with pk {} does not exist".format(owner_pk)
        )
    
    add_prefix = make_logger_prefix(owner.corporation.corporation_ticker)

    try:        
        owner.forwarding_last_sync = now()
        owner.save()
                                                    
        cutoff_dt_for_stale = now() - datetime.timedelta(
            hours=STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
        )
        new_notifications_count = 0            
        active_webhooks_count = 0    
        esi_client = None        
        for webhook in owner.webhooks.filter(is_active__exact=True):             
            active_webhooks_count += 1
            q = Notification.objects\
                .filter(owner__exact=owner)\
                .filter(is_sent__exact=False)\
                .filter(timestamp__gte=cutoff_dt_for_stale) \
                .filter(notification_type__in=webhook.notification_types)\
                .select_related().order_by('timestamp')

            if q.count() > 0:                
                new_notifications_count += q.count()
                logger.info(add_prefix(
                    'Found {} new notifications for webhook {}'.format(
                        q.count(), 
                        webhook
                )))
                if not esi_client:
                    esi_client = get_esi_client(owner)
                
                for notification in q:
                    notification.send_to_webhook(
                        webhook, 
                        esi_client
                    )
                    if rate_limited:
                        sleep(1)

        if active_webhooks_count == 0:
            logger.info(add_prefix('No active webhooks'))
        
        if new_notifications_count == 0:
            logger.info(add_prefix('No new notifications found'))

        owner.forwarding_last_error = Owner.ERROR_NONE
        owner.save()

        if STRUCTURES_ADD_TIMERS:
            notifications = Notification.objects\
                .filter(owner__exact=owner)\
                .filter(notification_type__in=NTYPE_RELEVANT_FOR_TIMERBOARD)\
                .exclude(is_timer_added__exact=True) \
                .filter(timestamp__gte=cutoff_dt_for_stale) \
                .select_related().order_by('timestamp')
            
            if len(notifications) > 0:                    
                if not esi_client:
                    esi_client = get_esi_client(owner)
                
                for notification in notifications:
                    notification.add_to_timerboard(esi_client)
        
    except TokenError:
        pass
    
    except Exception as ex:
        logger.exception(add_prefix(
            'An unexpected error ocurred {}'. format(ex)
        ))                                
        owner.forwarding_last_error = Owner.ERROR_UNKNOWN
        owner.save()
    

@shared_task
def send_all_new_notifications(rate_limited = True):
    """sends all unsent notifications to active webhooks and add timers"""
    for owner in Owner.objects.all():
        send_new_notifications_for_owner(owner.pk, rate_limited)


@shared_task
def send_notification(notification_pk):
    try:
        notification = Notification.objects.get(pk=notification_pk)
    except Notification.DoesNotExist:
        logger.error(
            'Can not sent not existing notification for given pk {}'.format(
                notification_pk
        ))
    else:    
        for webhook in notification.owner.webhooks.all():
            if str(notification.notification_type) in webhook.notification_types:
                notification.send_to_webhook(webhook)


@shared_task
def send_test_notifications_to_webhook(webhook_pk, user_pk = None):
    """sends test notification to given webhook"""    
    
    add_prefix = make_logger_prefix('test notification')
    try:
        webhook = Webhook.objects.get(pk=webhook_pk)
        add_prefix = make_logger_prefix(webhook)
        send_report = webhook.send_test_notification()
        error_code = None        
    except Exception as ex:
        logger.exception('Failed to send test notification')
        send_report = None
        error_code = str(ex)        
    
    success = (error_code == None)
    if user_pk:        
        try:
            message = 'Test notification to webhook "{}" {}.\n'.format(
                webhook,
                'completed successfully' if success else 'has failed'
            )
            if success:
                message += 'send report:\n{}'.format(send_report)
            else:
                message += 'Error code: {}'.format(error_code)
            
            notify(
                user=User.objects.get(pk=user_pk),
                title='{}: Test notification to "{}": {}'.format(
                    __title__,
                    webhook,
                    'OK' if success else 'FAILED'
                ),
                message=message,
                level='success' if success else 'danger'
            )
        except Exception as ex:
            logger.exception(add_prefix(
                'An unexpected error ocurred while trying to '
                + 'report to user: {}'. format(ex)
            ))
      