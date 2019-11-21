import logging
import json
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
            client: object = None
    ) -> list:
        """gets or creates eve_group object with data fetched from ESI"""
        from .models import EveGroup
        try:
            obj = self.get(id=eve_group_id)
            created = False
        except EveGroup.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_group_id,
                client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_group_id: int,
            client: object = None
    ) -> list:
        """updates or creates eve_group object with data fetched from ESI"""
        from .models import EveGroup

        addPrefix = make_logger_prefix(eve_group_id)

        logger.info(addPrefix('Fetching eve_group from ESI'))
        if not client:
            client = esi_client_factory()
        try:
            eve_group = client.Universe.get_universe_groups_group_id(
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
            client: object = None
    ) -> list:
        """gets or creates eve_type object with data fetched from ESI"""
        from .models import EveType
        try:
            obj = self.get(id=eve_type_id)
            created = False
        except EveType.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_type_id,
                client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_type_id: int,
            client: object = None
    ) -> list:
        """updates or creates eve_type object with data fetched from ESI"""
        from .models import EveType, EveGroup

        addPrefix = make_logger_prefix(eve_type_id)

        logger.info(addPrefix('Fetching eve_type from ESI'))
        if not client:
            client = esi_client_factory()
        try:
            eve_type = client.Universe.get_universe_types_type_id(
                type_id=eve_type_id
            ).result()
            eve_group, _ = EveGroup.objects.get_or_create_esi(                
                eve_type['group_id'],
                client
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
            client: object = None
    ) -> list:
        """gets or creates eve_region object with data fetched from ESI"""
        from .models import EveRegion
        try:
            obj = self.get(id=eve_region_id)
            created = False
        except EveRegion.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_region_id,
                client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_region_id: int,
            client: object = None
    ) -> list:
        """updates or creates eve_region object with data fetched from ESI"""
        from .models import EveGroup

        addPrefix = make_logger_prefix(eve_region_id)

        logger.info(addPrefix('Fetching eve_region from ESI'))
        if not client:
            client = esi_client_factory()
        try:
            eve_region = client.Universe.get_universe_regions_region_id(
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
            client: object = None
    ) -> list:
        """gets or creates eve_constellation object with data fetched from ESI"""
        from .models import EveConstellation
        try:
            obj = self.get(id=eve_constellation_id)
            created = False
        except EveConstellation.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_constellation_id,
                client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_constellation_id: int,
            client: object = None
    ) -> list:
        """updates or creates eve_constellation object with data fetched from ESI"""
        from .models import EveConstellation, EveRegion

        addPrefix = make_logger_prefix(eve_constellation_id)

        logger.info(addPrefix('Fetching eve_constellation from ESI'))
        if not client:
            client = esi_client_factory()
        try:
            eve_constellation = client.Universe.get_universe_constellations_constellation_id(
                constellation_id=eve_constellation_id
            ).result()
            eve_region, _ = EveRegion.objects.get_or_create_esi(                
                eve_constellation['region_id'],
                client
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
            client: object = None
    ) -> list:
        """gets or creates eve_solar_system object with data fetched from ESI"""
        from .models import EveSolarSystem
        try:
            obj = self.get(id=eve_solar_system_id)
            created = False
        except EveSolarSystem.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_solar_system_id,
                client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_solar_system_id: int,
            client: object = None
    ) -> list:
        """updates or creates eve_solar_system object with data fetched from ESI"""
        from .models import EveSolarSystem, EveConstellation

        addPrefix = make_logger_prefix(eve_solar_system_id)

        logger.info(addPrefix('Fetching eve_solar_system from ESI'))
        if not client:
            client = esi_client_factory()
        try:
            eve_solar_system = client.Universe.get_universe_systems_system_id(
                system_id=eve_solar_system_id
            ).result()
            eve_constellation, _ = EveConstellation.objects.get_or_create_esi( 
                eve_solar_system['constellation_id'],
                client
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
            client: object = None
    ) -> list:
        """gets or creates EveMoon object with data fetched from ESI"""
        from .models import EveMoon
        try:
            obj = self.get(id=moon_id)
            created = False
        except EveMoon.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                moon_id,
                client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            moon_id: int,
            client: object = None
    ) -> list:
        """updates or creates EveMoon object with data fetched from ESI"""
        from .models import EveMoon, EveSolarSystem

        addPrefix = make_logger_prefix(moon_id)

        logger.info(addPrefix('Fetching eve_moon from ESI'))
        if not client:
            client = esi_client_factory()
        try:
            eve_moon = client.Universe.get_universe_moons_moon_id(
                moon_id=moon_id
            ).result()
            eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi( 
                eve_moon['system_id'],
                client
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
            client: object = None
    ) -> list:
        """gets or creates EveEntity obj with data fetched from ESI"""
        from .models import EveEntity
        try:
            obj = self.get(id=eve_entity_id)
            created = False
        except EveEntity.DoesNotExist:
            obj, created = self.update_or_create_esi(                
                eve_entity_id,
                client
            )
        
        return obj, created


    def update_or_create_esi(
            self,             
            eve_entity_id: int,
            client: object = None
    ) -> list:
        """updates or creates eve_group object with data fetched from ESI"""
        from .models import EveEntity

        addPrefix = make_logger_prefix(eve_entity_id)

        logger.info(addPrefix('Trying to fetch eve entity from ESI'))
        if not client:
            client = esi_client_factory()
        try:
            response = client.Universe.post_universe_names(
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