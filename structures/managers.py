import logging
from pydoc import locate
from time import sleep

from bravado.exception import HTTPBadRequest

from django.db import models

from allianceauth.eveonline.providers import provider

from .utils import LoggerAddTag, make_logger_prefix


logger = LoggerAddTag(logging.getLogger(__name__), __package__)


class EsiRequestMixin:
    """Mixin class for adding ESI request ability with retries"""

    ESI_MAX_RETRIES = 3
    ESI_SLEEP_SECONDS_ON_RETRY = 1

    @classmethod
    def _perform_esi_request(
        cls, 
        esi_category_name: str, 
        esi_method_name: str, 
        args: dict,         
        add_prefix: object,
        esi_client: object = None
    ) -> dict:
        """Performs ESI request, returns response, retries on bad requests"""
        if not esi_client:
            esi_client = provider.client
        logger.info(add_prefix('Fetching object from ESI'))
        for retry_count in range(cls.ESI_MAX_RETRIES + 1):
            if retry_count > 0:
                logger.warn(add_prefix(
                    'Fetching data from ESI - Retry {} / {}'.format(
                        retry_count, cls.ESI_MAX_RETRIES
                    )
                ))
            try:
                if not hasattr(esi_client, esi_category_name):
                    raise ValueError(
                        'Invalid ESI category: %s' % esi_category_name
                    )
                esi_category = getattr(esi_client, esi_category_name)
                if not hasattr(esi_category, esi_method_name):
                    raise ValueError(
                        'Invalid ESI method for %s category: %s'
                        % (esi_category_name, esi_method_name)
                    )                
                response = \
                    getattr(esi_category, esi_method_name)(**args).result()
                break

            except HTTPBadRequest as ex:                    
                logger.warn(add_prefix(
                    'HTTP error while trying to '
                    'fetch data from ESI: {}'.format(ex)
                ))
                if retry_count < cls.ESI_MAX_RETRIES:
                    sleep(cls.ESI_SLEEP_SECONDS_ON_RETRY)
                else:
                    raise ex

        return response

    @classmethod
    def _fetch_eve_objects_from_esi(
        cls, 
        esi_category_name: str, 
        esi_method_name: str, 
        args: dict,         
        add_prefix: object,
        has_esi_localization: bool,
        esi_client: object = None
    ) -> dict:
        """returns dict of eve data objects from ESI
        will contain one full object items for each language if supported or just one
        will retry on bad request responses from ESI
        """
        from .models.eveuniverse import EsiNameLocalization

        if has_esi_localization:
            languages = EsiNameLocalization.ESI_LANGUAGES
        else:
            languages = {EsiNameLocalization.ESI_DEFAULT_LANGUAGE}

        eve_data_objects = dict()
        for language in languages:            
            if has_esi_localization:
                args['language'] = language

            eve_data_objects[language] = cls._perform_esi_request(
                esi_category_name, esi_method_name, args, add_prefix, esi_client
            )
            
        return eve_data_objects


class EveUniverseManager(EsiRequestMixin, models.Manager):
    
    def get_or_create_esi(self, eve_id: int) -> tuple:
        """gets or creates eve universe object fetched from ESI if needed. 
        Will always get/create parent objects.
        
        eve_id: Eve Online ID of object

        Returns: object, created        
        """
        try:
            obj = self.get(id=eve_id)
            created = False        
        except self.model.DoesNotExist:
            obj, created = self.update_or_create_esi(eve_id)

        return obj, created

    def update_or_create_esi(self, eve_id: int) -> tuple:
        """updates or creates Eve Universe object with data fetched from ESI. 
        Will always update/create children and get/create parent objects.

        eve_id: Eve Online ID of object

        Returns: object, created
        """
        add_prefix = make_logger_prefix(
            '%s(id=%d)' % (self.model.__name__, eve_id)
        )        
        try:
            eve_data_objects = self._fetch_eve_objects_from_esi(
                'Universe', 
                self.model._esi_method(), 
                {self.model._esi_pk(): eve_id}, 
                add_prefix,
                self.model.has_esi_localization()
            )
            defaults = self.model._map_esi_fields_to_model(eve_data_objects)
            obj, created = self.update_or_create(
                id=eve_id, defaults=defaults
            )
            obj._set_generated_translations()
            obj.save()
            self._update_or_create_children(eve_data_objects)
        
        except Exception as ex:
            logger.warn(add_prefix('Failed to update or create: %s' % ex))
            raise ex

        return obj, created
        
    def _update_or_create_children(self, eve_data_objects: dict) -> None:
        """updates or creates child objects if specified"""
        eve_data_obj = eve_data_objects[self.model.ESI_DEFAULT_LANGUAGE]
        for key, child_class in self.model._child_mappings().items():
            ChildClass = locate(__package__ + '.models.' + child_class)
            for eve_data_obj_2 in eve_data_obj[key]:
                eve_id = eve_data_obj_2[ChildClass._esi_pk()]
                ChildClass.objects.update_or_create_esi(eve_id)                
                

class EveEntityManager(EsiRequestMixin, models.Manager):

    def get_or_create_esi(self, eve_entity_id: int) -> tuple:
        """gets or creates EveEntity obj with data fetched from ESI if needed
        
        eve_id: Eve Online ID of object
        
        Returns: object, created        
        """
        from .models import EveEntity
        try:
            obj = self.get(id=eve_entity_id)
            created = False
        except EveEntity.DoesNotExist:
            obj, created = self.update_or_create_esi(eve_entity_id)

        return obj, created

    def update_or_create_esi(self, eve_entity_id: int) -> tuple:
        """updates or creates EveEntity object with data fetched from ESI
        
        eve_id: Eve Online ID of object
        
        Returns: object, created        
        """        
        add_prefix = make_logger_prefix(
            '%s(id=%d)' % (self.model.__name__, eve_entity_id)
        )
        logger.info(add_prefix('Trying to fetch eve entity from ESI'))        
        try:            
            response = self._perform_esi_request(
                'Universe', 
                'post_universe_names', 
                {'ids': [eve_entity_id]}, 
                add_prefix
            )
            if len(response) > 0:
                first = response[0]
                category = self.model.get_matching_entity_category(
                    first['category']
                )
                obj, created = self.update_or_create(
                    id=eve_entity_id,
                    defaults={
                        'category': category,
                        'name': first['name']
                    }
                )
            else:
                raise ValueError(add_prefix('Did not find a match'))

        except Exception as ex:
            logger.warn(add_prefix('Failed to load eve entity: %s' % ex))
            raise ex

        return obj, created


class StructureManager(EsiRequestMixin, models.Manager):

    def get_or_create_esi(
        self, structure_id: int, esi_client: object
    ) -> tuple:
        """get or create a structure with data from ESI if needed
        
        structure_id: Structure ID of object in Eve Online

        esi_client: ESI client with scope: esi-universe.read_structures.v1
        
        Returns: object, created
        """
        from .models import Structure

        try:
            obj = Structure.objects.get(id=structure_id)
            created = False
        except Structure.DoesNotExist:            
            obj, created = self.update_or_create_esi(structure_id, esi_client)
        return obj, created

    def update_or_create_esi(
        self, structure_id: int, esi_client: object
    ) -> tuple:
        """update or create a structure from ESI for given structure ID
        
        structure_id: Structure ID of object in Eve Online

        esi_client: ESI client with scope: esi-universe.read_structures.v1
        
        Returns: object, created
        """
        from .models import Owner

        add_prefix = make_logger_prefix(
            '%s(id=%d)' % (self.model.__name__, structure_id)
        )
        logger.info(add_prefix('Trying to fetch structure from ESI'))
        
        try:
            if esi_client is None:
                raise ValueError('Can not fetch structure without esi client')
            
            structure_info = self._perform_esi_request(
                'Universe', 
                'get_universe_structures_structure_id', 
                {'structure_id': structure_id}, 
                add_prefix,
                esi_client
            )            
            structure = {
                'structure_id': structure_id,
                'name': structure_info['name'],
                'position': structure_info['position'],
                'type_id': structure_info['type_id'],
                'system_id': structure_info['solar_system_id']
            }
            owner = Owner.objects.get(
                corporation__corporation_id=structure_info['corporation_id']
            )
            obj, created = self.update_or_create_from_dict(
                structure=structure, owner=owner
            )
        
        except Exception as ex:
            logger.warn(add_prefix('Failed to load structure: {}'.format(ex)))
            raise ex

        return obj, created

    def update_or_create_from_dict(
        self, structure: dict, owner: object
    ) -> tuple:
        """update or create structure from given dict"""
        from .models import EveType, EveSolarSystem, Structure,\
            StructureService, EvePlanet, EveMoon
        eve_type, _ = EveType.objects.get_or_create_esi(
            structure['type_id']
        )
        eve_solar_system, _ = \
            EveSolarSystem.objects.get_or_create_esi(
                structure['system_id']
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

        state = \
            Structure.get_matching_state_for_esi_state(structure['state']) \
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

        position_x = \
            structure['position']['x']\
            if 'position' in structure else None

        position_y = \
            structure['position']['y']\
            if 'position' in structure else None

        position_z = \
            structure['position']['z']\
            if 'position' in structure else None

        if 'planet_id' in structure:
            eve_planet, _ = EvePlanet.objects.get_or_create_esi(
                structure['planet_id'],                
            )
        else:
            eve_planet = None

        if 'moon_id' in structure:
            eve_moon, _ = EveMoon.objects.get_or_create_esi(
                structure['moon_id'],             
            )
        else:
            eve_moon = None

        obj, created = self.update_or_create(
            id=structure['structure_id'],
            defaults={
                'owner': owner,
                'eve_type': eve_type,
                'name': structure['name'],
                'eve_solar_system': eve_solar_system,
                'eve_planet': eve_planet,
                'eve_moon': eve_moon,
                'position_x': position_x,
                'position_y': position_y,
                'position_z': position_z,
                'fuel_expires': fuel_expires,
                'next_reinforce_hour': next_reinforce_hour,
                'next_reinforce_weekday': next_reinforce_weekday,
                'next_reinforce_apply': next_reinforce_apply,
                'reinforce_hour': reinforce_hour,
                'state': state,
                'state_timer_start': state_timer_start,
                'state_timer_end': state_timer_end,
                'unanchors_at': unanchors_at,
                'last_updated': owner.structures_last_sync
            }
        )
        StructureService.objects.filter(structure=obj).delete()
        if 'services' in structure and structure['services']:
            for service in structure['services']:
                state = StructureService.get_matching_state_for_esi_state(
                    service['state']
                )
                StructureService.objects.create(
                    structure=obj,
                    name=service['name'],
                    state=state
                )
        return obj, created
