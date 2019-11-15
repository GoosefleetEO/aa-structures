import logging
import os
import hashlib
import json

from celery import shared_task

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

from .utils import LoggerAddTag, make_logger_prefix, get_swagger_spec_path
from .models import *


logger = LoggerAddTag(logging.getLogger(__name__), __package__)


"""
Swagger Operations:
get_corporations_corporation_id_structures
"""


@shared_task
def run_structures_sync(force_sync = False, user_pk = None):
        
    for owner in Owner.objects.all():        
        
        owner.last_sync = now()
        owner.save()

        add_prefix = make_logger_prefix(owner)
                
        # abort if character is not configured
        if owner.character is None:
            logger.error(add_prefix(
                'No character configured to sync'
            ))           
            owner.last_error = Owner.ERROR_NO_CHARACTER
            owner.save()
            raise ValueError()

        # abort if character does not have sufficient permissions
        if not owner.character.user.has_perm(
                'structures.basic_access'
            ):
            logger.error(add_prefix(
                'Character does not have sufficient permission '
                + 'to sync structures'
            ))            
            owner.last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
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
            owner.last_error = Owner.ERROR_TOKEN_INVALID
            owner.save()
            raise TokenInvalidError()                    
        except TokenExpiredError:            
            logger.error(add_prefix(
                'Token expired for fetching structures'
            ))
            owner.last_error = Owner.ERROR_TOKEN_EXPIRED
            owner.save()
            raise TokenExpiredError()
        else:
            if not token:
                logger.error(add_prefix(
                    'Missing token for fetching structures'
                ))            
                owner.last_error = Owner.ERROR_TOKEN_INVALID
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
            operation = client.Corporation.get_corporations_corporation_id_structures(
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
                structure_info = client.Universe.get_universe_structures_structure_id(
                    structure_id=structure['structure_id']
                ).result()
                structure['name'] = structure_info['name']
                structure['position'] = structure_info['position']                

            if settings.DEBUG:
                # store to disk (for debugging)
                with open('structures_raw.json', 'w', encoding='utf-8') as f:
                    json.dump(
                        structures, 
                        f, 
                        cls=DjangoJSONEncoder, 
                        sort_keys=True, 
                        indent=4
                    )
            
            # determine if structures have changed by comparing their hashes
            new_version_hash = hashlib.md5(
                json.dumps(structures, cls=DjangoJSONEncoder).encode('utf-8')
            ).hexdigest()
            if force_sync or new_version_hash != owner.version_hash:
                logger.info(add_prefix(
                    'Storing update with {:,} structures'.format(
                        len(structures)
                    ))
                )
                
                # update structures in local DB                
                with transaction.atomic():                
                    Structure.objects.filter(owner=owner).delete()
                    for structure in structures:                    
                        eve_type, _ = EveType.objects.get_or_create_esi(
                            client,
                            structure['type_id']
                        )
                        eve_solar_system, _ = \
                            EveSolarSystem.objects.get_or_create_esi(
                                client,
                                structure['system_id']
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


                        obj, created = Structure.objects.update_or_create(
                            id=structure['structure_id'],
                            defaults={
                                'owner': owner,
                                'eve_type': eve_type,
                                'name': structure['name'],
                                'eve_solar_system': eve_solar_system,
                                'position_x': structure['position']['x'],
                                'position_y': structure['position']['y'],
                                'position_z': structure['position']['z'],
                                'fuel_expires': fuel_expires,
                                'next_reinforce_hour': next_reinforce_hour,
                                'next_reinforce_weekday': next_reinforce_weekday,
                                'next_reinforce_apply': next_reinforce_apply,
                                'profile_id': structure['profile_id'],
                                'reinforce_hour': structure['reinforce_hour'],
                                'reinforce_weekday': reinforce_weekday,
                                'state': state,
                                'state_timer_start': state_timer_start,
                                'state_timer_end': state_timer_end,
                                'unanchors_at': unanchors_at,
                                'last_updated': owner.last_sync,
                               
                            }                        
                        )                        
                    owner.version_hash = new_version_hash                
                    owner.save()
                    success = True

                owner.last_error = Owner.ERROR_NONE
                owner.save()

            else:
                logger.info(add_prefix('Structures are unchanged.'))
                success = True

            
        except Exception as ex:
                logger.error(add_prefix(
                    'An unexpected error ocurred {}'. format(ex)
                ))                                
                owner.last_error = Owner.ERROR_UNKNOWN
                owner.save()
                raise ex

    
    if user_pk:
        error_code = None
        try:
            message = 'Syncing of structures for "{}" {}.\n'.format(
                owner.organization.name,                
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
                title='Freight: Structures sync for {}: {}'.format(
                    owner.organization.name,
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