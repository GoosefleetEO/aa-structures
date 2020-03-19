"""Owner related models"""

from datetime import datetime, timedelta
import json
import logging
import os
import re
from time import sleep

from django.core.serializers.json import DjangoJSONEncoder
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCorporationInfo
from allianceauth.notifications import notify

from esi.clients import esi_client_factory
from esi.errors import TokenExpiredError, TokenInvalidError, TokenError
from esi.models import Token

from .. import __title__
from ..app_settings import (    
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_DEVELOPER_MODE,
    STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED,
    STRUCTURES_FEATURE_CUSTOMS_OFFICES,
    STRUCTURES_FEATURE_STARBASES,
    STRUCTURES_ADD_TIMERS,
    STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION,        
    STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES,    
    STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES,            
    STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES,    
)
from .eveuniverse import EvePlanet, EveSolarSystem, EveType
from ..helpers import EsiHelper
from .structures import Structure
from .notifications import EveEntity, Notification
                
from ..utils import (
    LoggerAddTag, 
    make_logger_prefix, 
    chunks, 
    DATETIME_FORMAT, 
    get_swagger_spec_path
)

logger = LoggerAddTag(logging.getLogger(__name__), __title__)


class General(models.Model):
    """Meta model for global app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ('basic_access', _('Can access this app and view')),
            ('view_alliance_structures', _('Can view alliance structures')),
            ('view_all_structures', _('Can view all structures')),
            ('add_structure_owner', _('Can add new structure owner')),
        )


class Owner(models.Model):
    """A corporation that owns structures"""

    # errors
    ERROR_NONE = 0
    ERROR_TOKEN_INVALID = 1
    ERROR_TOKEN_EXPIRED = 2
    ERROR_INSUFFICIENT_PERMISSIONS = 3
    ERROR_NO_CHARACTER = 4
    ERROR_ESI_UNAVAILABLE = 5
    ERROR_OPERATION_MODE_MISMATCH = 6
    ERROR_UNKNOWN = 99

    ERRORS_LIST = [
        (
            ERROR_NONE,
            _('No error')
        ),
        (
            ERROR_TOKEN_INVALID,
            _('Invalid token')
        ),
        (
            ERROR_TOKEN_EXPIRED,
            _('Expired token')
        ),
        (
            ERROR_INSUFFICIENT_PERMISSIONS,
            _('Insufficient permissions')
        ),
        (
            ERROR_NO_CHARACTER,
            _('No character set for fetching data from ESI')
        ),
        (
            ERROR_ESI_UNAVAILABLE,
            _('ESI API is currently unavailable')
        ),
        (
            ERROR_OPERATION_MODE_MISMATCH,
            _('Operaton mode does not match with current setting')
        ),
        (
            ERROR_UNKNOWN,
            _('Unknown error')
        ),
    ]

    corporation = models.OneToOneField(
        EveCorporationInfo,
        primary_key=True,
        on_delete=models.CASCADE,
        help_text=_('Corporation owning structures')
    )
    character = models.ForeignKey(
        CharacterOwnership,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        help_text=_('character used for syncing structures')
    )
    structures_last_sync = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('when the last sync happened')
    )
    structures_last_error = models.IntegerField(
        choices=ERRORS_LIST,
        default=ERROR_NONE,
        help_text=_('error that occurred at the last sync atttempt (if any)')
    )
    notifications_last_sync = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('when the last sync happened')
    )
    notifications_last_error = models.IntegerField(
        choices=ERRORS_LIST,
        default=ERROR_NONE,
        help_text=_('error that occurred at the last sync atttempt (if any)')
    )
    forwarding_last_sync = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('when the last sync happened')
    )
    forwarding_last_error = models.IntegerField(
        choices=ERRORS_LIST,
        default=ERROR_NONE,
        help_text=_('error that occurred at the last sync atttempt (if any)')
    )
    webhooks = models.ManyToManyField(
        'Webhook',
        default=None,
        blank=True,
        help_text=_('notifications are sent to these webhooks. ')
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_(
            'whether this owner is currently included in the sync process'
        )
    )
    is_alliance_main = models.BooleanField(
        default=False,
        help_text=_(
            'whether alliance wide notifications '
            'are forwarded for this owner (e.g. sov notifications)'
        )
    )
    is_included_in_service_status = models.BooleanField(
        default=True,
        help_text=_(
            'whether the sync status of this owner is included in '
            'the overall status of this services'
        )
    )

    def __str__(self) -> str:
        return str(self.corporation.corporation_name)

    def __repr__(self):
        return '{}(id={}, corporation=\'{}\')'.format(
            self.__class__.__name__,
            self.id,
            self.__str__
        )

    def is_structure_sync_ok(self) -> bool:
        """returns true if they have been no errors
        and last syncing occurred within alloted time
        """
        return self.structures_last_error == self.ERROR_NONE \
            and self.structures_last_sync \
            and self.structures_last_sync > (now() - timedelta(
                minutes=STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES
            ))

    def is_notification_sync_ok(self) -> bool:
        """returns true if they have been no errors
        and last syncing occurred within alloted time
        """
        return self.notifications_last_error == self.ERROR_NONE \
            and self.notifications_last_sync \
            and self.notifications_last_sync > (now() - timedelta(
                minutes=STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES
            ))

    def is_forwarding_sync_ok(self) -> bool:
        """returns true if they have been no errors
        and last syncing occurred within alloted time
        """
        return self.forwarding_last_error == self.ERROR_NONE \
            and self.forwarding_last_sync \
            and self.forwarding_last_sync > (now() - timedelta(
                minutes=STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES
            ))

    def is_all_syncs_ok(self) -> bool:
        """returns true if they have been no errors
        and last syncing occurred within alloted time for all sync categories
        """
        return self.is_structure_sync_ok() \
            and self.is_notification_sync_ok() \
            and self.is_forwarding_sync_ok()

    @classmethod
    def to_friendly_error_message(cls, error) -> str:
        msg = [(x, y) for x, y in cls.ERRORS_LIST if x == error]
        return msg[0][1] if len(msg) > 0 else 'Undefined error'

    @classmethod
    def get_esi_scopes(cls) -> list:
        scopes = [
            'esi-corporations.read_structures.v1',
            'esi-universe.read_structures.v1',
            'esi-characters.read_notifications.v1',
        ]
        if STRUCTURES_FEATURE_CUSTOMS_OFFICES:
            scopes += [
                'esi-planets.read_customs_offices.v1',
                'esi-assets.read_corporation_assets.v1'
            ]
        if STRUCTURES_FEATURE_STARBASES:
            scopes += [
                'esi-corporations.read_starbases.v1'
            ]
        return scopes

    def update_structures_esi(self, user: User = None):
        """updates all structures from ESI"""
        
        add_prefix = self._logger_prefix()
        try:
            self.structures_last_error = Owner.ERROR_NONE
            self.structures_last_sync = now()
            self.save()            
            esi_client, error = self.esi_client()
            if error:
                self.structures_last_error = error
                self.save()
                raise TokenError(self.to_friendly_error_message(error))

            try:                
                structures = self._fetch_upwell_structures(esi_client)
                if STRUCTURES_FEATURE_CUSTOMS_OFFICES:
                    structures += self._fetch_custom_offices(esi_client)
                if STRUCTURES_FEATURE_STARBASES:
                    structures += self._fetch_starbases(esi_client)

                logger.info(add_prefix(
                    'Storing updates for {:,} structures'.format(
                        len(structures)
                    )
                ))
                with transaction.atomic():
                    # remove structures no longer returned from ESI
                    ids_local = {
                        x.id
                        for x in Structure.objects.filter(owner=self)
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
                            structure, self
                        )

                    self.structures_last_error = self.ERROR_NONE
                    self.save()

            except Exception as ex:
                logger.exception(add_prefix(
                    'An unexpected error ocurred {}'. format(ex)
                ))
                self.structures_last_error = self.ERROR_UNKNOWN
                self.save()
                raise ex

        except Exception as ex:
            success = False
            error_code = str(ex)
        else:
            success = True
            error_code = None

        if user:
            self._send_report_to_user(                
                'structures',
                self.structure_set.count(),
                success,
                error_code,
                user
            )

        return success

    def _fetch_upwell_structures(self, esi_client: object) -> list:
        """fetch Upwell structures from ESI for self"""

        add_prefix = self._logger_prefix()        
        corporation_id = self.corporation.corporation_id
        
        structures = EsiHelper.fetch_esi_objects_with_pages(
            'Corporation.get_corporations_corporation_id_structures',
            args={'corporation_id': corporation_id},
            add_prefix=add_prefix,
            has_pages=True,
            esi_client=esi_client
        )
            
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
                structure_info = EsiHelper.fetch_esi_object(
                    'Universe.get_universe_structures_structure_id',
                    args={'structure_id': structure['structure_id']},
                    add_prefix=add_prefix,
                    esi_client=esi_client
                )
                matches = re.search(r'^\S+ - (.+)', structure_info['name'])
                if matches:
                    name = matches.group(1)
                else:
                    name = structure_info['name']
                structure['name'] = name
                structure['position'] = structure_info['position']

        if STRUCTURES_DEVELOPER_MODE:
            self._store_raw_data('structures', structures, corporation_id)

        return structures

    def _fetch_custom_offices(self, esi_client: object) -> list:
        """fetch custom offices from ESI for self"""

        def extract_planet_name(text: str) -> str:
            """extract name of planet from assert name for a customs office"""
            reg_ex = re.compile(r'Customs Office \((.+)\)')
            matches = reg_ex.match(text)
            return matches.group(1) if matches else text
        
        add_prefix = self._logger_prefix()        
        corporation_id = self.corporation.corporation_id

        pocos = EsiHelper.fetch_esi_objects_with_pages(
            'Planetary_Interaction.get_corporations_corporation_id_customs_offices',
            args={'corporation_id': corporation_id},
            add_prefix=add_prefix,
            has_pages=True,
            esi_client=esi_client
        )       
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
                locations_data_chunk = EsiHelper.fetch_esi_object(
                    'Assets.post_corporations_corporation_id_assets_locations',
                    args={
                        'corporation_id': corporation_id, 
                        'item_ids': item_ids_chunk
                    },
                    add_prefix=add_prefix,
                    esi_client=esi_client
                )
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
                names_data_chunk = EsiHelper.fetch_esi_object(
                    'Assets.post_corporations_corporation_id_assets_names',
                    args={
                        'corporation_id': corporation_id, 
                        'item_ids': item_ids
                    },
                    add_prefix=add_prefix,
                    esi_client=esi_client
                )
                names_data += names_data_chunk
            names = {
                x['item_id']: extract_planet_name(x['name']) for x in names_data
            }

            # making sure we have all solar systems loaded
            # incl. their planets for later name matching
            for solar_system_id in {int(x['system_id']) for x in pocos}:
                EveSolarSystem.objects.get_or_create_esi(solar_system_id)

            # compile pocos into structures list
            for poco in pocos:
                office_id = poco['office_id']
                if office_id in names:
                    try:
                        eve_planet = EvePlanet.objects.get(name=names[office_id])
                        planet_id = eve_planet.id                    
                        name = eve_planet.eve_type.name_localized_for_language(
                            STRUCTURES_DEFAULT_LANGUAGE
                        )

                    except EvePlanet.DoesNotExist:
                        name = names[office_id]
                        planet_id = None
                else:
                    name = None
                    planet_id = None

                reinforce_exit_start = datetime(
                    year=2000,
                    month=1,
                    day=1,
                    hour=poco['reinforce_exit_start']
                )
                reinforce_hour = reinforce_exit_start + timedelta(hours=1)
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

        if STRUCTURES_DEVELOPER_MODE:
            self._store_raw_data('customs_offices', structures, corporation_id)

        return structures

    def _fetch_starbases(self, esi_client: object) -> list:
        """fetch starbases from ESI for self"""

        add_prefix = self._logger_prefix()        
        corporation_id = self.corporation.corporation_id
        starbases = EsiHelper.fetch_esi_objects_with_pages(
            'Corporation.get_corporations_corporation_id_starbases',
            args={'corporation_id': corporation_id},
            add_prefix=add_prefix,
            has_pages=True,
            esi_client=esi_client
        )
        # convert into structures data format
        structures = list()
        if not starbases:
            logger.info(add_prefix('No starbases retrieved from ESI'))
        else:
            logger.info(add_prefix(
                'Fetching names for {} starbases from ESI'.format(len(starbases))
            ))
            item_ids = [x['starbase_id'] for x in starbases]
            names_data = list()
            for item_ids_chunk in chunks(item_ids, 999):
                names_data_chunk = EsiHelper.fetch_esi_object(
                    'Assets.post_corporations_corporation_id_assets_names',
                    args={
                        'corporation_id': corporation_id, 
                        'item_ids': item_ids_chunk
                    },
                    add_prefix=add_prefix,
                    esi_client=esi_client
                )
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

        if STRUCTURES_DEVELOPER_MODE:
            self._store_raw_data('starbases', structures, corporation_id)

        return structures
    
    def fetch_notifications_esi(self, user: User = None):
        """fetches notification for self and proceses them"""
        
        add_prefix = self._logger_prefix()
        notifications_count = 0
        try:
            self.notifications_last_error = Owner.ERROR_NONE
            self.notifications_last_sync = now()
            self.save()            
            esi_client, error = self.esi_client()
            if error:
                self.notifications_last_error = error
                self.save()
                raise TokenError(self.to_friendly_error_message(error))
           
            # fetch notifications from ESI
            try:
                # fetching data from ESI                
                notifications = EsiHelper.fetch_esi_object(
                    'Character.get_characters_character_id_notifications',
                    args={
                        'character_id': self.character.character.character_id
                    },
                    add_prefix=add_prefix,
                    esi_client=esi_client
                )                
                if STRUCTURES_DEVELOPER_MODE:
                    self._store_raw_data(
                        'notifications',
                        notifications,
                        self.corporation.corporation_id
                    )

                if STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED:
                    # store notifications to disk in continuous file per corp
                    folder_name = 'structures_notifications_archive'
                    os.makedirs(folder_name, exist_ok=True)
                    filename = '{}/notifications_{}_{}.txt'.format(
                        folder_name,
                        self.corporation.corporation_id,
                        now().date().isoformat()
                    )
                    logger.info(add_prefix(
                        'Storing notifications into archive file: {}'.format(
                            filename
                        )
                    ))
                    with open(file=filename, mode='a', encoding='utf-8') as f:
                        f.write('[{}] {}:\n'.format(
                            now().strftime(DATETIME_FORMAT),
                            self.corporation.corporation_ticker
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
                                sender, _ = EveEntity.objects.get_or_create_esi(
                                    notification['sender_id']
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
                                owner=self,
                                defaults={
                                    'sender': sender,
                                    'timestamp': notification['timestamp'],
                                    'notification_type': notification_type,
                                    'text': text,
                                    'is_read': is_read,
                                    'last_updated': self.notifications_last_sync,
                                }
                            )
                            if created:
                                obj.created = now()
                                obj.save()
                                new_notifications_count += 1

                    self.notifications_last_error = self.ERROR_NONE
                    self.save()

                if new_notifications_count > 0:
                    logger.info(add_prefix(
                        'Received {} new notifications from ESI'.format(
                            new_notifications_count
                        )
                    ))

                    if STRUCTURES_ADD_TIMERS:
                        cutoff_dt_for_stale = now() - timedelta(
                            hours=STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
                        )
                        my_types = Notification.get_types_for_timerboard()
                        notifications = Notification.objects\
                            .filter(owner=self)\
                            .filter(notification_type__in=my_types)\
                            .exclude(is_timer_added=True) \
                            .filter(timestamp__gte=cutoff_dt_for_stale) \
                            .select_related().order_by('timestamp')

                        if len(notifications) > 0:
                            if not esi_client:
                                esi_client = self.esi_client()

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
                self.notifications_last_error = self.ERROR_UNKNOWN
                self.save()
                raise ex

        except Exception as ex:
            success = False
            error_code = str(ex)
        else:
            success = True
            error_code = None

        if user:
            self._send_report_to_user(                
                'notifications',
                notifications_count,
                success,
                error_code,
                user
            )

        return success
    
    def send_new_notifications(
        self, rate_limited: bool = True, user: User = None
    ) -> bool:
        """forwards all new notification for this owner to Discord"""

        add_prefix = self._logger_prefix()
        notifications_count = 0
        try:
            try:
                self.forwarding_last_error = Owner.ERROR_NONE
                self.forwarding_last_sync = now()
                self.save()

                cutoff_dt_for_stale = now() - timedelta(
                    hours=STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION
                )
                new_notifications_count = 0
                active_webhooks_count = 0
                esi_client = None
                for webhook in self.webhooks.filter(is_active=True):
                    active_webhooks_count += 1
                    notifications_qs = Notification.objects\
                        .filter(owner=self)\
                        .filter(is_sent=False)\
                        .filter(timestamp__gte=cutoff_dt_for_stale) \
                        .filter(notification_type__in=webhook.notification_types)\
                        .select_related().order_by('timestamp')

                    if notifications_qs.count() > 0:
                        new_notifications_count += notifications_qs.count()
                        logger.info(add_prefix(
                            'Found {} new notifications for webhook {}'.format(
                                notifications_qs.count(),
                                webhook
                            )
                        ))
                        if not esi_client:
                            esi_client, error = self.esi_client()
                            if error:
                                self.forwarding_last_error = error
                                self.save()
                                raise TokenError(
                                    add_prefix('Failed to get a valid token')
                                )

                        for notification in notifications_qs:
                            if (not notification.filter_for_npc_attacks()
                                and not notification.filter_for_alliance_level()
                            ):
                                notification.send_to_webhook(webhook, esi_client)
                                notifications_count += 1
                                if rate_limited:
                                    sleep(1)

                if active_webhooks_count == 0:
                    logger.info(add_prefix('No active webhooks'))

                if new_notifications_count == 0:
                    logger.info(add_prefix('No new notifications found'))

                self.forwarding_last_error = self.ERROR_NONE
                self.save()

            except TokenError:
                pass

            except Exception as ex:
                logger.exception(add_prefix(
                    'An unexpected error ocurred {}'. format(ex)
                ))
                self.forwarding_last_error = self.ERROR_UNKNOWN
                self.save()
                raise ex
     
        except Exception as ex:
            success = False
            error_code = str(ex)
        else:
            success = True
            error_code = None

        if user:
            self._send_report_to_user(                
                'notifications',
                notifications_count,
                success,
                error_code,
                user
            )

        return success

    def _logger_prefix(self):
        """returns standard logger prefix function"""
        return make_logger_prefix(self.corporation.corporation_ticker)

    def esi_client(self) -> object:
        """returns a new ESI client for the given owner with token"""
        token = None
        error = None
        add_prefix = self._logger_prefix()

        # abort if character is not configured
        if self.character is None:
            logger.error(add_prefix('No character configured to sync'))
            error = self.ERROR_NO_CHARACTER

        # abort if character does not have sufficient permissions
        elif not self.character.user.has_perm(
                'structures.add_structure_owner'
        ):
            logger.error(add_prefix(
                'self character does not have sufficient permission to sync'
            ))
            error = self.ERROR_INSUFFICIENT_PERMISSIONS

        else:
            try:
                # get token
                token = Token.objects.filter(
                    user=self.character.user,
                    character_id=self.character.character.character_id
                ).require_scopes(
                    self.get_esi_scopes()
                ).require_valid().first()
            except TokenInvalidError:
                logger.error(add_prefix(
                    'Invalid token for fetching structures'
                ))
                error = self.ERROR_TOKEN_INVALID
            except TokenExpiredError:
                logger.error(add_prefix(
                    'Token expired for fetching structures'
                ))
                error = self.ERROR_TOKEN_EXPIRED
            else:
                if not token:
                    logger.error(add_prefix(
                        'No token found with sufficient scopes'
                    ))
                    error = self.ERROR_TOKEN_INVALID

        if token:
            logger.info(add_prefix('Starting ESI client...'))
            logger.debug('Using token: {}'.format(token))                
            client = esi_client_factory(
                token=token, spec_file=get_swagger_spec_path()
            )
        else:
            client = None
        
        return client, error

    def _send_report_to_user(
        self,        
        topic: str,
        topic_count: int,
        success: bool,
        error_code,
        user        
    ):
        add_prefix = self._logger_prefix()
        try:            
            if success:
                message_details = '%(count)s %(topic)s synced.' % {
                    'count': topic_count, 
                    'topic': topic
                }
            else:
                message_details = _('Error: %s') % error_code

            message = _(
                'Syncing of %(topic)s for "%(owner)s" %(result)s.\n'
                '%(message_details)s'
            ) % {
                'topic': topic,
                'owner': self.corporation.corporation_name,
                'result': _('completed successfully') if success else _('has failed'),
                'message_details': message_details,
            }

            notify(
                user,
                title=_(
                    '%(title)s: %(topic)s updated for '
                    '%(owner)s: %(result)s') % {
                        'title': _(__title__),
                        'topic': topic,
                        'owner': self.corporation.corporation_name,
                        'result': _('OK') if success else _('FAILED')
                },
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

    @staticmethod
    def _store_raw_data(name: str, data: list, corporation_id: int):
        """store raw data for debug purposes"""
        with open(
            '{}_raw_{}.json'.format(name, corporation_id), 'w', encoding='utf-8'
        ) as f:
            json.dump(data, f, cls=DjangoJSONEncoder, sort_keys=True, indent=4)
