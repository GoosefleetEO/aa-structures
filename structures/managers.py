import logging
from pydoc import locate

from bravado.exception import HTTPError

from django.db import models

from . import __title__
from .helpers import EsiSmartRequest
from .utils import LoggerAddTag, make_logger_prefix


logger = LoggerAddTag(logging.getLogger(__name__), __title__)


class EveUniverseManager(models.Manager):
    
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
        from .models import EsiNameLocalization
        add_prefix = make_logger_prefix(
            '%s(id=%d)' % (self.model.__name__, eve_id)
        )        
        try:            
            esi_path = 'Universe.' + self.model.esi_method()
            args = {self.model.esi_pk(): eve_id}
            if self.model.has_esi_localization():
                eve_data_objects = \
                    EsiSmartRequest.fetch_with_localization(
                        esi_path=esi_path,
                        args=args,                        
                        languages=EsiNameLocalization.ESI_LANGUAGES,
                        logger_tag=add_prefix()
                    )
            else:
                eve_data_objects = dict()
                eve_data_objects[EsiNameLocalization.ESI_DEFAULT_LANGUAGE] = \
                    EsiSmartRequest.fetch(
                        esi_path=esi_path,
                        args=args,
                        logger_tag=add_prefix()
                    )   # noqa E123
            defaults = self.model.map_esi_fields_to_model(eve_data_objects)
            obj, created = self.update_or_create(id=eve_id, defaults=defaults)
            obj.set_generated_translations()
            obj.save()
            self._update_or_create_children(eve_data_objects)
        
        except Exception as ex:
            logger.warn(add_prefix('Failed to update or create: %s' % ex))
            raise ex

        return obj, created
        
    def _update_or_create_children(self, eve_data_objects: dict) -> None:
        """updates or creates child objects if specified"""
        eve_data_obj = eve_data_objects[self.model.ESI_DEFAULT_LANGUAGE]
        for key, child_class in self.model.child_mappings().items():
            ChildClass = locate(__package__ + '.models.' + child_class)
            for eve_data_obj_2 in eve_data_obj[key]:
                eve_id = eve_data_obj_2[ChildClass.esi_pk()]
                ChildClass.objects.update_or_create_esi(eve_id)                
                
    def update_all_esi(self) -> int:
        """update all objects from ESI. Returns count of updated  objects"""
        logger.info(
            '%s: Updating %d objects from from ESI...' 
            % (self.model.__name__, self.count())
        )
        count_updated = 0
        for eve_obj in self.all().order_by('last_updated'):
            try:
                self.update_or_create_esi(eve_obj.id)
                count_updated += 1
            except HTTPError as ex:
                logger.exception('Update interrupted by exception: %s' % ex)

        return count_updated


class EveEntityManager(models.Manager):

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
        try:            
            response = EsiSmartRequest.fetch(
                esi_path='Universe.post_universe_names', 
                args={'ids': [eve_entity_id]},
                logger_tag=add_prefix()
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


class StructureManager(models.Manager):

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
        This will only fetch basic info about a structure
        
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
            
            structure_info = EsiSmartRequest.fetch(
                esi_path='Universe.get_universe_structures_structure_id', 
                args={'structure_id': structure_id},                 
                esi_client=esi_client,
                logger_tag=add_prefix()
            )            
            structure = {
                'structure_id': structure_id,
                'name': self.model.extract_name_from_esi_respose(
                    structure_info['name']
                ),
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
        from .models.eveuniverse import EveUniverse
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
                args = {
                    'structure': obj,
                    'name': service['name'],
                    'state': state
                }
                for lang in EveUniverse.ESI_LANGUAGES:
                    if lang != EveUniverse.ESI_DEFAULT_LANGUAGE:
                        field_name = 'name_%s' % lang
                        if field_name in service:
                            args[field_name] = service[field_name]

                StructureService.objects.create(**args)
        return obj, created
