import logging
import os
import json
import re
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
from esi.errors import TokenExpiredError, TokenInvalidError
from esi.models import Token

from . import __title__
from .utils import LoggerAddTag, make_logger_prefix, get_swagger_spec_path
from .models import *


logger = LoggerAddTag(logging.getLogger('allianceauth'), __package__)


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

    add_prefix = make_logger_prefix(owner)

    try:        
        owner.structures_last_sync = now()
        owner.save()
        
        # abort if character is not configured
        if owner.character is None:
            logger.error(add_prefix(
                'No character configured to sync'
            ))           
            owner.structures_last_error = Owner.ERROR_NO_CHARACTER
            owner.save()
            raise ValueError()

        # abort if character does not have sufficient permissions
        if not owner.character.user.has_perm(
                'structures.add_structure_owner'
            ):
            logger.error(add_prefix(
                'Character does not have sufficient permission '
                + 'to sync structures'
            ))            
            owner.structures_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
            owner.save()
            raise ValueError()

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
            owner.structures_last_error = Owner.ERROR_TOKEN_INVALID
            owner.save()
            raise TokenInvalidError()                    
        except TokenExpiredError:            
            logger.error(add_prefix(
                'Token expired for fetching structures'
            ))
            owner.structures_last_error = Owner.ERROR_TOKEN_EXPIRED
            owner.save()
            raise TokenExpiredError()
        else:
            if not token:
                logger.error(add_prefix(
                    'Missing token for fetching structures'
                ))            
                owner.structures_last_error = Owner.ERROR_TOKEN_INVALID
                owner.save()
                raise TokenInvalidError()                    
            
        logger.info('Using token: {}'.format(token))
        
        try:
            # fetching data from ESI
            logger.info(add_prefix('Fetching structures from ESI - page 1'))
            client = esi_client_factory(
                token=token, 
                spec_file=get_swagger_spec_path()
            )

            # get structures from first page
            operation = \
                client.Corporation.get_corporations_corporation_id_structures(
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
                structures += client.Corporation.get_corporations_corporation_id_structures(
                    corporation_id=owner.corporation_id,
                    page=page
                ).result()
            
            # fetch additional information for structures
            for structure in structures:
                structure_info = \
                    client.Universe.get_universe_structures_structure_id(
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
                    name = re.search(
                        '^\S+ - (.+)', 
                        structure['name']
                    ).group(1)                        
                    eve_type, _ = EveType.objects.get_or_create_esi(
                        structure['type_id'],
                        client
                    )
                    eve_solar_system, _ = \
                        EveSolarSystem.objects.get_or_create_esi(
                            structure['system_id'],
                            client
                    )
                    fuel_expires = structure['fuel_expires'] \
                        if 'fuel_expires' in structure else None

                    next_reinforce_hour = \
                        structure['next_reinforce_hour']  \
                        if 'next_reinforce_hour' in structure else None

                    next_reinforce_weekday = \
                        structure['next_reinforce_weekday'] \
                        if 'next_reinforce_weekday' in structure else None

                    next_reinforce_apply = \
                        structure['next_reinforce_apply'] \
                        if 'next_reinforce_apply' in structure else None

                    reinforce_hour = structure['reinforce_hour'] \
                            if 'reinforce_hour' in structure else None
                    
                    reinforce_weekday = structure['reinforce_weekday'] \
                        if 'reinforce_weekday' in structure else None

                    state = Structure.get_matching_state(
                        structure['state']
                    )

                    state_timer_start = structure['state_timer_start'] \
                        if 'state_timer_start' in structure else None

                    state_timer_end = structure['state_timer_end'] \
                        if 'state_timer_end' in structure else None

                    unanchors_at =  structure['unanchors_at']\
                        if 'unanchors_at' in structure else None

                    obj = Structure.objects.create(
                        id=structure['structure_id'],
                        owner=owner,
                        eve_type=eve_type,
                        name=name,
                        eve_solar_system=eve_solar_system,
                        position_x=structure['position']['x'],
                        position_y=structure['position']['y'],
                        position_z=structure['position']['z'],
                        fuel_expires=fuel_expires,
                        next_reinforce_hour=next_reinforce_hour,
                        next_reinforce_weekday=next_reinforce_weekday,
                        next_reinforce_apply=next_reinforce_apply,
                        reinforce_hour=structure['reinforce_hour'],
                        reinforce_weekday=reinforce_weekday,
                        state=state,
                        state_timer_start=state_timer_start,
                        state_timer_end=state_timer_end,
                        unanchors_at=unanchors_at,
                        last_updated=owner.structures_last_sync
                    )
                    if structure['services']:
                        for service in structure['services']:
                            state = StructureService.get_matching_state(
                                service['state']
                            )
                            StructureService.objects.create(
                                structure=obj,
                                name=service['name'],
                                state=state
                            )                                
                
                owner.structures_last_error = Owner.ERROR_NONE
                owner.save()

        except Exception as ex:
                logger.error(add_prefix(
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
        try:
            message = 'Syncing of structures for "{}" {}.\n'.format(
                owner.corporation.corporation_name,
                'completed successfully' if success else 'has failed'
            )
            if success:
                message += '{:,} structures synced.'.format(
                    owner.structure_set.count()
                )
            else:
                message += 'Error code: {}'.format(error_code)
            
            notify(
                user=User.objects.get(pk=user_pk),
                title='{}: Structures updated for {}: {}'.format(
                   __title__,
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
    """fetches notification for owner and stored them in local storage"""
    
    try:
        owner = Owner.objects.get(pk=owner_pk)
    except Owner.DoesNotExist:
        raise Owner.DoesNotExist(
            "Requested owner with pk {} does not exist".format(owner_pk)
        )

    add_prefix = make_logger_prefix(owner)

    try:        
        owner.notifications_last_sync = now()
        owner.save()
        
        # abort if character is not configured
        if owner.character is None:
            logger.error(add_prefix(
                'No character configured to sync'
            ))           
            owner.notifications_last_error = Owner.ERROR_NO_CHARACTER
            owner.save()
            raise ValueError()

        # abort if character does not have sufficient permissions
        if not owner.character.user.has_perm(
                'structures.add_structure_owner'
            ):
            logger.error(add_prefix(
                'Character does not have sufficient permission '
                + 'to fetch notifications'
            ))            
            owner.notifications_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
            owner.save()
            raise ValueError()

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
                'Invalid token for fetching notifications'
            ))            
            owner.notifications_last_error = Owner.ERROR_TOKEN_INVALID
            owner.save()
            raise TokenInvalidError()                    
        except TokenExpiredError:            
            logger.error(add_prefix(
                'Token expired for fetching notifications'
            ))
            owner.notifications_last_error = Owner.ERROR_TOKEN_EXPIRED
            owner.save()
            raise TokenExpiredError()
        else:
            if not token:
                logger.error(add_prefix(
                    'Missing token for fetching notifications'
                ))            
                owner.notifications_last_error = Owner.ERROR_TOKEN_INVALID
                owner.save()
                raise TokenInvalidError()                    
            
        logger.info('Using token: {}'.format(token))
        
        try:
            # fetching data from ESI
            logger.info(add_prefix('Fetching notifications from ESI'))
            client = esi_client_factory(
                token=token, 
                spec_file=get_swagger_spec_path()
            )

            # get notifications from first page
            notifications = \
                client.Character.get_characters_character_id_notifications(
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
            
            logger.info(add_prefix(
                'Processing {:,} notifications received from ESI'.format(
                    len(notifications)
            )))
            
            # update notifications in local DB                
            with transaction.atomic():                                    
                for notification in notifications:                        
                    notification_type = \
                        Notification.get_matching_notification_type(
                            notification['type']
                        )
                    if notification_type:
                        sender_type = \
                            EveEntity.get_matching_entity_type(
                                notification['sender_type']
                            )
                        if sender_type != EveEntity.CATEGORY_OTHER:
                            sender, _ = EveEntity\
                            .objects.get_or_create_esi(
                                notification['sender_id'],
                                client
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
                        obj = Notification.objects.update_or_create(
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
                owner.notifications_last_error = Owner.ERROR_NONE
                owner.save()
            
        except Exception as ex:
                logger.error(add_prefix(
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
        try:
            message = 'Fetching notifications for "{}" {}.\n'.format(
                owner.corporation.corporation_name,
                'completed successfully' if success else 'has failed'
            )
            if success:
                message += '{:,} notifications fetched.'.format(
                    owner.structure_set.count()
                )
            else:
                message += 'Error code: {}'.format(error_code)
            
            notify(
                user=User.objects.get(pk=user_pk),
                title='{}: Notification sync for {}: {}'.format(
                   __title__,
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
    
    return success


@shared_task
def fetch_all_notifications(force_sync = False):
    """fetch notifications for all owners"""
    for owner in Owner.objects.all():
        fetch_notifications_for_owner.delay(owner.pk, force_sync=force_sync)


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
def send_new_notifications_to_webhook(webhook_pk, send_again = False):
    """sends unsent notifications for given webhook"""    
    try:
        webhook = Webhook.objects.get(pk=webhook_pk)
    except Webhook.DoesNotExist:
        logger.error(
            'Can not sent notifications to non existing webhook '
            + 'with pk {} does not exist'.format(webhook_pk)
        )
    else:
        webhook.send_new_notifications()
    

@shared_task
def send_all_new_notifications():
    """sends all unsent notifications to active webhooks and add timers"""
    active_webhooks_count = 0
    for webhook in Webhook.objects.filter(is_active__exact=True):
        active_webhooks_count += 1
        send_new_notifications_to_webhook.delay(webhook.pk)
    
    if active_webhooks_count == 0:
        logger.warn('No active webhook found for sending notifications')

    if STRUCTURES_ADD_TIMERS:
        notifications = Notification.objects\
            .filter(notification_type__in=NTYPE_RELEVANT_FOR_TIMERBOARD)\
            .exclude(is_timer_added__exact=True)
        
        if len(notifications) > 0:
            esi_client = esi_client_factory()
            for notification in notifications:
                notification.add_to_timerboard(esi_client)


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
            logger.error(add_prefix(
                'An unexpected error ocurred while trying to '
                + 'report to user: {}'. format(ex)
            ))
      