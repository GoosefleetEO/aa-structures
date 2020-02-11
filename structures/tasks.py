import datetime
import logging
import os
import json
import re
from time import sleep

from celery import shared_task

from django.db import transaction
from django.conf import settings
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import now

from allianceauth.notifications import notify
from esi.clients import esi_client_factory
from esi.errors import TokenExpiredError, TokenInvalidError, TokenError
from esi.models import Token

from . import __title__
from .app_settings import (
    STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED,
    STRUCTURES_FEATURE_CUSTOMS_OFFICES,
    STRUCTURES_FEATURE_STARBASES,
    STRUCTURES_ADD_TIMERS,
    STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
)
from .utils import (
    LoggerAddTag,
    make_logger_prefix,
    get_swagger_spec_path,
    chunks, DATETIME_FORMAT
)
from .models import (
    EveCategory,
    EveGroup,
    EveType,
    EveRegion,
    EveConstellation,
    EveSolarSystem,
    EveMoon,
    EvePlanet,
    StructureTag,
    StructureService,
    Webhook,
    EveEntity,
    Owner,
    Notification,
    Structure
)


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
            'Owner character does not have sufficient permission to sync'
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
                    'No token found with sufficient scopes'
                ))
                error = Owner.ERROR_TOKEN_INVALID

    if token:
        logger.debug('Using token: {}'.format(token))

    return token, error


def _get_esi_client(owner: Owner, add_prefix: make_logger_prefix) -> object:
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
            message += 'Error: {}'.format(error_code)

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
        if settings.DEBUG:
            raise ex


def _store_raw_data(name: str, data: list, corporation_id: int):
    """store raw data for debug purposes"""
    with open(
        '{}_raw_{}.json'.format(name, corporation_id),
        'w',
        encoding='utf-8'
    ) as f:
        json.dump(
            data,
            f,
            cls=DjangoJSONEncoder,
            sort_keys=True,
            indent=4
        )


def _fetch_upwell_structures(
    owner: Owner,
    esi_client: object,
    add_prefix: make_logger_prefix
) -> list:
    """fetch Upwell structures from ESI for owner"""

    logger.info(add_prefix('Fetching Upwell structures from ESI - page 1'))

    corporation_id = owner.corporation.corporation_id
    # get structures from first page
    operation = \
        esi_client.Corporation.get_corporations_corporation_id_structures(
            corporation_id=corporation_id
        )
    operation.also_return_response = True
    structures, response = operation.result()
    pages = int(response.headers['x-pages'])

    # add structures from additional pages if any
    for page in range(2, pages + 1):
        logger.info(add_prefix(
            'Fetching Upwell structures from ESI - page {}'.format(page)
        ))
        structures += \
            esi_client.Corporation.get_corporations_corporation_id_structures(
                corporation_id=corporation_id,
                page=page
            ).result()

    # fetch additional information for structures
    if not structures:
        logger.info(add_prefix(
            'No Upwell structures retrieved from ESI'
        ))
    else:
        logger.info(add_prefix(
            'Fetching additional infos for {} '
            'Upwell structures from ESI'.format(
                len(structures)
            )
        ))
        for structure in structures:
            structure_info = \
                esi_client.Universe.get_universe_structures_structure_id(
                    structure_id=structure['structure_id']
                ).result()
            matches = re.search(r'^\S+ - (.+)', structure_info['name'])
            if matches:
                name = matches.group(1)
            else:
                name = structure_info['name']
            structure['name'] = name
            structure['position'] = structure_info['position']

    if settings.DEBUG:
        _store_raw_data('structures', structures, corporation_id)

    return structures


def _fetch_custom_offices(
    owner: Owner,
    esi_client: object,
    add_prefix: make_logger_prefix
) -> list:
    """fetch custom offices from ESI for owner"""

    def extract_planet_name(text: str) -> str:
        """extract name of planet from assert name for a customs office"""
        r = re.compile(r'Customs Office \((.+)\)')
        m = r.match(text)
        if m:
            return m.group(1)
        else:
            return text

    logger.info(add_prefix('Fetching custom offices from ESI - page 1'))
    corporation_id = owner.corporation.corporation_id

    # get pocos from first page
    operation = \
        esi_client.Planetary_Interaction\
        .get_corporations_corporation_id_customs_offices(
            corporation_id=corporation_id
        )
    operation.also_return_response = True
    pocos, response = operation.result()
    pages = int(response.headers['x-pages'])

    # add pocos from additional pages if any
    for page in range(2, pages + 1):
        logger.info(add_prefix(
            'Fetching custom offices from ESI - page {}'.format(page)
        ))
        pocos += esi_client.Planetary_Interaction\
            .get_corporations_corporation_id_customs_offices(
                corporation_id=corporation_id,
                page=page
            ).result()

    structures = list()
    if not pocos:
        logger.info(add_prefix(
            'No custom offices retrieved from ESI'
        ))
    else:
        # fetching locations
        logger.info(add_prefix(
            'Fetching locations for {} custom offices from ESI'.format(
                len(pocos)
            )
        ))
        item_ids = [x['office_id'] for x in pocos]
        locations_data = list()
        for item_ids_chunk in chunks(item_ids, 999):
            locations_data_chunk = esi_client.Assets\
                .post_corporations_corporation_id_assets_locations(
                    corporation_id=corporation_id,
                    item_ids=item_ids_chunk
                )\
                .result()
            locations_data += locations_data_chunk
        positions = {x['item_id']: x['position'] for x in locations_data}

        # fetching names
        logger.info(add_prefix(
            'Fetching names for {} custom office names from ESI'.format(
                len(pocos)
            )
        ))
        names_data = list()
        for item_ids_chunk in chunks(item_ids, 999):
            names_data_chunk = esi_client.Assets\
                .post_corporations_corporation_id_assets_names(
                    corporation_id=corporation_id,
                    item_ids=item_ids
                )\
                .result()
            names_data += names_data_chunk
        names = {
            x['item_id']: extract_planet_name(x['name']) for x in names_data
        }

        # making sure we have all solar systems loaded
        # incl. their planets for later name matching
        for solar_system_id in {int(x['system_id']) for x in pocos}:
            EveSolarSystem.objects.get_or_create_esi(
                solar_system_id,
                esi_client
            )

        # compile pocos into structures list
        for poco in pocos:
            office_id = poco['office_id']
            if office_id in names:
                try:
                    eve_planet = EvePlanet.objects.get(name=names[office_id])
                    planet_id = eve_planet.id
                    name = eve_planet.eve_type.name

                except EvePlanet.DoesNotExist:
                    name = names[office_id]
                    planet_id = None
            else:
                name = None
                planet_id = None

            reinforce_exit_start = datetime.datetime(
                year=2000,
                month=1,
                day=1,
                hour=poco['reinforce_exit_start']
            )
            reinforce_hour = reinforce_exit_start + datetime.timedelta(hours=1)
            structure = {
                'structure_id': office_id,
                'type_id': EveType.EVE_TYPE_ID_POCO,
                'corporation_id': corporation_id,
                'name': name if name else '',
                'system_id': poco['system_id'],
                'reinforce_hour': reinforce_hour.hour,
                'state': Structure.STATE_UNKNOWN
            }
            if planet_id:
                structure['planet_id'] = planet_id

            if office_id in positions:
                structure['position'] = positions[office_id]

            structures.append(structure)

    if settings.DEBUG:
        _store_raw_data('customs_offices', structures, corporation_id)

    return structures


def _fetch_starbases(
    owner: Owner,
    esi_client: object,
    add_prefix: make_logger_prefix
) -> list:
    """fetch starbases from ESI for owner"""

    logger.info(add_prefix('Fetching starbases from ESI - page 1'))
    corporation_id = owner.corporation.corporation_id

    # get starbases from first page
    operation = \
        esi_client.Corporation.get_corporations_corporation_id_starbases(
            corporation_id=corporation_id
        )
    operation.also_return_response = True
    starbases, response = operation.result()
    pages = int(response.headers['x-pages'])

    # add starbases from additional pages if any
    for page in range(2, pages + 1):
        logger.info(add_prefix(
            'Fetching starbases from ESI - page {}'.format(page)
        ))
        starbases += \
            esi_client.Corporation.get_corporations_corporation_id_starbases(
                corporation_id=corporation_id,
                page=page
            ).result()

    # convert into structures data format
    structures = list()
    if not starbases:
        logger.info(add_prefix(
            'No starbases retrieved from ESI'
        ))
    else:
        logger.info(add_prefix(
            'Fetching names for {} starbases from ESI'.format(len(starbases))
        ))
        item_ids = [x['starbase_id'] for x in starbases]
        names_data = list()
        for item_ids_chunk in chunks(item_ids, 999):
            names_data_chunk = esi_client.Assets\
                .post_corporations_corporation_id_assets_names(
                    corporation_id=corporation_id,
                    item_ids=item_ids
                )\
                .result()
            names_data += names_data_chunk
        names = {x['item_id']: x['name'] for x in names_data}
        for starbase in starbases:
            if starbase['starbase_id'] in names:
                name = names[starbase['starbase_id']]
            else:
                name = 'Starbase'
            structure = {
                'structure_id': starbase['starbase_id'],
                'type_id': starbase['type_id'],
                'corporation_id': corporation_id,
                'name': name,
                'system_id': starbase['system_id']
            }
            if 'state' in starbase:
                structure['state'] = starbase['state']

            if 'moon_id' in starbase:
                structure['moon_id'] = starbase['moon_id']

            if 'reinforced_until' in starbase:
                structure['state_timer_end'] = starbase['reinforced_until']

            if 'unanchors_at' in starbase:
                structure['unanchors_at'] = starbase['unanchors_at']

            structures.append(structure)

    if settings.DEBUG:
        _store_raw_data('starbases', structures, corporation_id)

    return structures


@shared_task
def update_structures_for_owner(
    owner_pk,
    force_sync: bool = False,
    user_pk=None
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
            raise RuntimeError(Owner.to_friendly_error_message(error))

        try:
            logger.info(add_prefix('Starting ESI client...'))
            esi_client = esi_client_factory(
                token=token,
                spec_file=get_swagger_spec_path()
            )
            structures = _fetch_upwell_structures(
                owner,
                esi_client,
                add_prefix
            )
            if STRUCTURES_FEATURE_CUSTOMS_OFFICES:
                structures += _fetch_custom_offices(
                    owner,
                    esi_client,
                    add_prefix,
                )
            if STRUCTURES_FEATURE_STARBASES:
                structures += _fetch_starbases(
                    owner,
                    esi_client,
                    add_prefix,
                )

            logger.info(add_prefix(
                'Storing updates for {:,} structures'.format(
                    len(structures)
                )
            ))
            with transaction.atomic():
                # remove locally stored structures no longer returned from ESI
                ids_local = {
                    x.id
                    for x in Structure.objects.filter(owner=owner)
                }
                ids_from_esi = {x['structure_id'] for x in structures}
                ids_to_remove = ids_local - ids_from_esi

                if len(ids_to_remove) > 0:
                    Structure.objects\
                        .filter(id__in=ids_to_remove)\
                        .delete()
                    logger.info(
                        'Removed {} structures which apparently no longer '
                        'exist.'.format(len(ids_to_remove))
                    )

                # update structures
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
def update_all_structures(force_sync=False):
    """fetches structures from all known owners"""
    for owner in Owner.objects.all():
        if owner.is_active:
            update_structures_for_owner.delay(owner.pk, force_sync=force_sync)


@shared_task
def fetch_notifications_for_owner(
    owner_pk,
    force_sync: bool = False,
    user_pk=None
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
                _store_raw_data(
                    'notifications',
                    notifications,
                    owner.corporation.corporation_id
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
                    )
                ))
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
                )
            ))

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
                            EveEntity.get_matching_entity_category(
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
                    )
                ))

                if STRUCTURES_ADD_TIMERS:
                    cutoff_dt_for_stale = now() - datetime.timedelta(
                        hours=STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
                    )
                    my_types = Notification.get_types_for_timerboard()
                    notifications = Notification.objects\
                        .filter(owner=owner)\
                        .filter(notification_type__in=my_types)\
                        .exclude(is_timer_added=True) \
                        .filter(timestamp__gte=cutoff_dt_for_stale) \
                        .select_related().order_by('timestamp')

                    if len(notifications) > 0:
                        if not esi_client:
                            esi_client = _get_esi_client(owner, add_prefix)

                        for notification in notifications:
                            notification.process_for_timerboard(esi_client)

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
def fetch_all_notifications(force_sync=False):
    """fetch notifications for all owners"""
    for owner in Owner.objects.all():
        if owner.is_active:
            fetch_notifications_for_owner.delay(
                owner.pk,
                force_sync=force_sync
            )


@shared_task
def send_new_notifications_for_owner(owner_pk, rate_limited=True):
    """forwards new notification for this owner to Discord"""

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
        for webhook in owner.webhooks.filter(is_active=True):
            active_webhooks_count += 1
            q = Notification.objects\
                .filter(owner=owner)\
                .filter(is_sent=False)\
                .filter(timestamp__gte=cutoff_dt_for_stale) \
                .filter(notification_type__in=webhook.notification_types)\
                .select_related().order_by('timestamp')

            if q.count() > 0:
                new_notifications_count += q.count()
                logger.info(add_prefix(
                    'Found {} new notifications for webhook {}'.format(
                        q.count(),
                        webhook
                    )
                ))
                if not esi_client:
                    esi_client = _get_esi_client(owner, add_prefix)

                for notification in q:
                    if (not notification.filter_for_npc_attacks()
                        and not notification.filter_for_alliance_level()
                    ):
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

    except TokenError:
        pass

    except Exception as ex:
        logger.exception(add_prefix(
            'An unexpected error ocurred {}'. format(ex)
        ))
        owner.forwarding_last_error = Owner.ERROR_UNKNOWN
        owner.save()


@shared_task
def send_all_new_notifications(rate_limited=True):
    """sends all unsent notifications to active webhooks and add timers"""
    for owner in Owner.objects.all():
        if owner.is_active:
            send_new_notifications_for_owner(owner.pk, rate_limited)


@shared_task
def send_notifications(notification_pks: list):
    """send notifications defined by list of pks"""    
    notifications = Notification.objects.filter(pk__in=notification_pks)
    if notifications:
        logger.info('Trying to send {} notifications to webhooks...'.format(
            len(notification_pks)
        ))
        esi_client = esi_client_factory(spec_file=get_swagger_spec_path())
        for n in notifications:
            for webhook in n.owner.webhooks.all():
                if (str(n.notification_type) in webhook.notification_types
                    and not n.filter_for_npc_attacks()
                    and not n.filter_for_alliance_level()
                ):
                    n.send_to_webhook(webhook, esi_client)
            sleep(1)


@shared_task
def send_test_notifications_to_webhook(webhook_pk, user_pk=None):
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

    success = (error_code is None)
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


@shared_task
def run_sde_update():
    """update selected SDE models from ESI"""
    logger.info('Starting ESI client...')
    esi_client = esi_client_factory(spec_file=get_swagger_spec_path())

    for EveModel in [EveGroup, EveSolarSystem]:
        obj_count = EveModel.objects.count()
        if obj_count > 0:
            logger.info(
                'Started updating {} {} objects and related objects '
                'from from ESI'.format(
                    obj_count,
                    EveModel.__name__,
                )
            )
            for eve_obj in EveModel.objects.all():
                EveModel.objects.update_or_create_esi(eve_obj.id, esi_client)

    logger.info('SDE update complete')


@shared_task
def purge_all_data(i_am_sure: bool = False):
    """removes all app-related data from the database
    This tool is required to allow zero migrations, which would otherwise
    fail to do FK constraints
    """

    if not i_am_sure:
        logger.info('No data deleted')
    else:
        logger.info('Started deleting all app-related data')

        models = [
            EveCategory,
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveMoon,
            EvePlanet,
            StructureTag,
            StructureService,
            Webhook,
            EveEntity,
            Owner,
            Notification,
            Structure
        ]
        with transaction.atomic():
            for MyModel in models:
                logger.info(
                    'Deleting data in model: {}'.format(MyModel.__name__)
                )
                MyModel.objects.all().delete()

        logger.info('Completed deleting all app-related data')
