import logging
import json
import re
from time import sleep

from bravado.exception import *

from django.db import models, transaction
from esi.clients import esi_client_factory
from allianceauth.eveonline.models import EveCharacter

from .utils import LoggerAddTag, make_logger_prefix, get_swagger_spec_path


logger = LoggerAddTag(logging.getLogger(__name__), __package__)


class EveGroupManager(models.Manager):
    
    def get_or_create_esi(
            self,             
            eve_group_id: int,
            esi_client: object = None
    ) -> list:
        """gets or creates eve_group object with data fetched from ESI"""
        from .models import EveGroup
        try:
            obj = self.get(id=eve_group_id)
            created = False
        except EveGroup.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_group_id,
                esi_client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_group_id: int,
            esi_client: object = None
    ) -> list:
        """updates or creates eve_group object with data fetched from ESI"""
        from .models import EveGroup

        addPrefix = make_logger_prefix(eve_group_id)

        logger.info(addPrefix('Fetching eve_group from ESI'))
        if not esi_client:
            esi_client = esi_client_factory()
        try:
            eve_group = esi_client.Universe.get_universe_groups_group_id(
                group_id=eve_group_id
            ).result()
            obj, created = self.update_or_create(
                id=eve_group_id,
                defaults={
                    'name': eve_group['name']                    
                }
            ) 
        except Exception as ex:
            logger.warn(addPrefix(
                'Failed to load eve_group: '.format(ex)
            ))
            raise ex
        
        return obj, created


class EveTypeManager(models.Manager):
    
    def get_or_create_esi(
            self,             
            eve_type_id: int,
            esi_client: object = None
    ) -> list:
        """gets or creates eve_type object with data fetched from ESI"""
        from .models import EveType
        try:
            obj = self.get(id=eve_type_id)
            created = False
        except EveType.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_type_id,
                esi_client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_type_id: int,
            esi_client: object = None
    ) -> list:
        """updates or creates eve_type object with data fetched from ESI"""
        from .models import EveType, EveGroup

        addPrefix = make_logger_prefix(eve_type_id)

        logger.info(addPrefix('Fetching eve_type from ESI'))
        if not esi_client:
            esi_client = esi_client_factory()
        try:
            eve_type = esi_client.Universe.get_universe_types_type_id(
                type_id=eve_type_id
            ).result()
            eve_group, _ = EveGroup.objects.get_or_create_esi(                
                eve_type['group_id'],
                esi_client
            )
            obj, created = self.update_or_create(
                id=eve_type_id,
                defaults={
                    'name': eve_type['name'],                    
                    'eve_group': eve_group
                }
            ) 
        except Exception as ex:
            logger.warn(addPrefix(
                'Failed to load eve_type: '.format(ex)
            ))
            raise ex
        
        return obj, created


class EveRegionManager(models.Manager):
    
    def get_or_create_esi(
            self,             
            eve_region_id: int,
            esi_client: object = None
    ) -> list:
        """gets or creates eve_region object with data fetched from ESI"""
        from .models import EveRegion
        try:
            obj = self.get(id=eve_region_id)
            created = False
        except EveRegion.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_region_id,
                esi_client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_region_id: int,
            esi_client: object = None
    ) -> list:
        """updates or creates eve_region object with data fetched from ESI"""
        from .models import EveGroup

        addPrefix = make_logger_prefix(eve_region_id)

        logger.info(addPrefix('Fetching eve_region from ESI'))
        if not esi_client:
            esi_client = esi_client_factory()
        try:
            eve_region = esi_client.Universe.get_universe_regions_region_id(
                region_id=eve_region_id
            ).result()
            obj, created = self.update_or_create(
                id=eve_region_id,
                defaults={
                    'name': eve_region['name']                    
                }
            ) 
        except Exception as ex:
            logger.warn(addPrefix(
                'Failed to load eve_region: '.format(ex)
            ))
            raise ex
        
        return obj, created


class EveConstellationManager(models.Manager):
    
    def get_or_create_esi(
            self,             
            eve_constellation_id: int,
            esi_client: object = None
    ) -> list:
        """gets or creates eve_constellation object with data fetched from ESI"""
        from .models import EveConstellation
        try:
            obj = self.get(id=eve_constellation_id)
            created = False
        except EveConstellation.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_constellation_id,
                esi_client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_constellation_id: int,
            esi_client: object = None
    ) -> list:
        """updates or creates eve_constellation object with data fetched from ESI"""
        from .models import EveConstellation, EveRegion

        addPrefix = make_logger_prefix(eve_constellation_id)

        logger.info(addPrefix('Fetching eve_constellation from ESI'))
        if not esi_client:
            esi_client = esi_client_factory()
        try:
            eve_constellation = esi_client.Universe.get_universe_constellations_constellation_id(
                constellation_id=eve_constellation_id
            ).result()
            eve_region, _ = EveRegion.objects.get_or_create_esi(                
                eve_constellation['region_id'],
                esi_client
            )
            obj, created = self.update_or_create(
                id=eve_constellation_id,
                defaults={
                    'name': eve_constellation['name'],                    
                    'eve_region': eve_region
                }
            ) 
        except Exception as ex:
            logger.warn(addPrefix(
                'Failed to load eve_constellation: '.format(ex)
            ))
            raise ex
        
        return obj, created


class EveSolarSystemManager(models.Manager):
    
    def get_or_create_esi(
            self,             
            eve_solar_system_id: int,
            esi_client: object = None
    ) -> list:
        """gets or creates eve_solar_system object with data fetched from ESI"""
        from .models import EveSolarSystem
        try:
            obj = self.get(id=eve_solar_system_id)
            created = False
        except EveSolarSystem.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_solar_system_id,
                esi_client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_solar_system_id: int,
            esi_client: object = None
    ) -> list:
        """updates or creates eve_solar_system object with data fetched from ESI"""
        from .models import EveSolarSystem, EveConstellation

        addPrefix = make_logger_prefix(eve_solar_system_id)

        logger.info(addPrefix('Fetching eve_solar_system from ESI'))
        if not esi_client:
            esi_client = esi_client_factory()
        try:
            eve_solar_system = esi_client.Universe.get_universe_systems_system_id(
                system_id=eve_solar_system_id
            ).result()
            eve_constellation, _ = EveConstellation.objects.get_or_create_esi( 
                eve_solar_system['constellation_id'],
                esi_client
            )
            obj, created = self.update_or_create(
                id=eve_solar_system_id,
                defaults={
                    'name': eve_solar_system['name'],
                    'eve_constellation': eve_constellation,
                    'security_status': eve_solar_system['security_status'],
                }
            ) 
        except Exception as ex:
            logger.warn(addPrefix(
                'Failed to load eve_solar_system: '.format(ex)
            ))
            raise ex
        
        return obj, created


class EveMoonManager(models.Manager):
    
    def get_or_create_esi(
            self,             
            moon_id: int,
            esi_client: object = None
    ) -> list:
        """gets or creates EveMoon object with data fetched from ESI"""
        from .models import EveMoon
        try:
            obj = self.get(id=moon_id)
            created = False
        except EveMoon.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                moon_id,
                esi_client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            moon_id: int,
            esi_client: object = None
    ) -> list:
        """updates or creates EveMoon object with data fetched from ESI"""
        from .models import EveMoon, EveSolarSystem

        addPrefix = make_logger_prefix(moon_id)

        logger.info(addPrefix('Fetching eve_moon from ESI'))
        if not esi_client:
            esi_client = esi_client_factory()
        try:
            eve_moon = esi_client.Universe.get_universe_moons_moon_id(
                moon_id=moon_id
            ).result()
            eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi( 
                eve_moon['system_id'],
                esi_client
            )
            obj, created = self.update_or_create(
                id=moon_id,
                defaults={
                    'name': eve_moon['name'],                    
                    'position_x': eve_moon['position']['x'],
                    'position_y': eve_moon['position']['y'],
                    'position_z': eve_moon['position']['z'],
                    'eve_solar_system': eve_solar_system,
                }
            ) 
        except Exception as ex:
            logger.warn(addPrefix(
                'Failed to load eve_moon: '.format(ex)
            ))
            raise ex
        
        return obj, created


class EveEntityManager(models.Manager):
    
    def get_or_create_esi(
            self,             
            eve_entity_id: int,
            esi_client: object = None
    ) -> list:
        """gets or creates EveEntity obj with data fetched from ESI"""
        from .models import EveEntity
        try:
            obj = self.get(id=eve_entity_id)
            created = False
        except EveEntity.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_entity_id,
                esi_client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_entity_id: int,
            esi_client: object = None
    ) -> list:
        """updates or creates eve_group object with data fetched from ESI"""
        from .models import EveEntity

        addPrefix = make_logger_prefix(eve_entity_id)

        logger.info(addPrefix('Trying to fetch eve entity from ESI'))
        if not esi_client:
            esi_client = esi_client_factory()
        try:
            response = esi_client.Universe.post_universe_names(
                ids=[eve_entity_id]
            ).result()
            if len(response) > 0:
                first = response[0]
                type = EveEntity.get_matching_entity_type(
                    first['category']
                )
                if not type:
                    type = EveEntity.CATEGORY_OTHER

                obj, created = self.update_or_create(
                    id=eve_entity_id,
                    defaults={
                        'category': type,
                        'name': first['name']
                    }
                )
            else:
                raise ValueError(
                    'Did not find a matching entity for ID {}'.format(
                        eve_entity_id
                )) 
        except Exception as ex:
            logger.warn(addPrefix(
                'Failed to load eve entity: '.format(ex)
            ))
            raise ex
        
        return obj, created


class StructureManager(models.Manager):

    def get_or_create_esi(
        self,
        structure_id,
        esi_client
    ):    
        """get or create a structure from ESI for given structure ID"""
        from .models import Structure, Owner

        try:
            obj = Structure.objects.get(id=structure_id)
            created = False
        except Structure.DoesNotExist:
            structure_info = \
                esi_client.Universe.get_universe_structures_structure_id(
                    structure_id=structure_id
                ).result()
            structure = {
                'structure_id': structure_id,
                'name': structure_info['name'],
                'position': structure_info['position'],
                'type_id': structure_info['type_id'],
                'system_id': structure_info['solar_system_id']
            }            
            owner = Owner.objects.get(
                corporation__corporation_id=structure_info['owner_id']
            )
            obj, created = self.update_or_create_from_dict(
                structure,
                owner,
                esi_client
            ) 
        return obj, created
        
    def update_or_create_from_dict(
        self, 
        structure: dict, 
        owner: object,        
        esi_client: object
    ):
        """update or create structure from given dict"""
        from .models import EveType, EveSolarSystem, Structure,\
            StructureService, Owner
        matches = re.search('^\S+ - (.+)', structure['name'])
        if matches:
            name = matches.group(1)
        else:
            name = structure['name']        
        eve_type, _ = EveType.objects.get_or_create_esi(
            structure['type_id'],
            esi_client
        )
        eve_solar_system, _ = \
            EveSolarSystem.objects.get_or_create_esi(
                structure['system_id'],
                esi_client
        )
        fuel_expires = \
            structure['fuel_expires'] \
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

        reinforce_hour = \
            structure['reinforce_hour'] \
            if 'reinforce_hour' in structure else None
        
        reinforce_weekday = \
            structure['reinforce_weekday'] \
            if 'reinforce_weekday' in structure else None

        state = \
            Structure.get_matching_state(structure['state']) \
            if 'state' in structure else Structure.STATE_UNKNOWN

        state_timer_start = \
            structure['state_timer_start'] \
            if 'state_timer_start' in structure else None

        state_timer_end = \
            structure['state_timer_end'] \
            if 'state_timer_end' in structure else None

        unanchors_at =  \
            structure['unanchors_at']\
            if 'unanchors_at' in structure else None

        obj, created = Structure.objects.update_or_create(
            id=structure['structure_id'],
            defaults={
                'owner': owner,
                'eve_type': eve_type,
                'name': name,
                'eve_solar_system': eve_solar_system,
                'position_x': structure['position']['x'],
                'position_y': structure['position']['y'],
                'position_z': structure['position']['z'],
                'fuel_expires': fuel_expires,
                'next_reinforce_hour': next_reinforce_hour,
                'next_reinforce_weekday': next_reinforce_weekday,
                'next_reinforce_apply': next_reinforce_apply,
                'reinforce_hour': reinforce_hour,
                'reinforce_weekday': reinforce_weekday,
                'state': state,
                'state_timer_start': state_timer_start,
                'state_timer_end': state_timer_end,
                'unanchors_at': unanchors_at,
                'last_updated': owner.structures_last_sync
            }
        )
        if 'services' in structure and structure['services']:
            for service in structure['services']:
                state = StructureService.get_matching_state(
                    service['state']
                )
                StructureService.objects.create(
                    structure=obj,
                    name=service['name'],
                    state=state
                ) 
        return obj, created