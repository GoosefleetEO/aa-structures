import logging
from pydoc import locate

from django.db import models

from allianceauth.eveonline.providers import provider
from esi.clients import esi_client_factory

from .utils import LoggerAddTag, make_logger_prefix, get_swagger_spec_path


logger = LoggerAddTag(logging.getLogger(__name__), __package__)


class EveUniverseManager(models.Manager):

    def get_or_create_esi(
            self, eve_id: int, esi_client: object = None
    ) -> tuple:
        """gets or creates eve universe object with data fetched from ESI"""        
        try:
            obj = self.get(id=eve_id)
            created = False        
        except self.model.DoesNotExist:
            obj, created = self.update_or_create_esi(eve_id, esi_client)

        return obj, created

    def update_or_create_esi(
            self, eve_id: int, esi_client: object = None
    ) -> tuple:
        """updates or creates eve object with data fetched from ESI"""        
        addPrefix = make_logger_prefix('{}:{}'.format(
            self.model.__name__, eve_id
        ))
        logger.info(addPrefix('Fetching data from ESI'))
        try:
            if esi_client is None:
                esi_client = provider.client
            args = {self.model.esi_pk(): eve_id}
            operation = getattr(esi_client.Universe, self.model.esi_method())(**args)
            eve_data_obj = operation.result()            
            fk_mappings = self.model.fk_mappings()
            field_mappings = self.model.field_mappings()
            defaults = dict()
            for key in self.model.field_names_not_pk():
                if key in fk_mappings:
                    esi_key, ParentClass = fk_mappings[key]
                    value, _ = ParentClass.objects.get_or_create_esi(
                        eve_data_obj[esi_key], esi_client
                    )
                else:
                    if key in field_mappings:
                        mapping = field_mappings[key]
                        if len(mapping) != 2:
                            raise ValueError(
                                'Currently only supports mapping to 1-level '
                                'nested dicts'
                            )
                        value = eve_data_obj[mapping[0]][mapping[1]]
                    else:
                        value = eve_data_obj[key]
                
                defaults[key] = value

            obj, created = self.update_or_create(
                id=eve_id,
                defaults=defaults
            )            
            for key, child_class in self.model.child_mappings().items():
                ChildClass = locate(__package__ + '.models.' + child_class)
                for eve_data_obj_2 in eve_data_obj[key]:
                    eve_id = eve_data_obj_2[ChildClass.esi_pk()]
                    ChildClass.objects.get_or_create_esi(eve_id, esi_client)
            
        except Exception as ex:
            logger.warn(addPrefix('Failed to update or create: %s' % ex))
            raise ex

        return obj, created


class EveCategoryManager(models.Manager):

    def get_or_create_esi(
            self,
            eve_category_id: int,
            esi_client: object = None
    ) -> list:
        """gets or creates eve_category object with data fetched from ESI"""
        from .models import EveCategory
        try:
            obj = self.get(id=eve_category_id)
            created = False
        except EveCategory.DoesNotExist:
            obj, created = self.update_or_create_esi(
                eve_category_id,
                esi_client
            )

        return obj, created

    def update_or_create_esi(
            self,
            eve_category_id: int,
            esi_client: object = None
    ) -> list:
        """updates or creates eve_category object with data fetched from ESI"""
        addPrefix = make_logger_prefix(eve_category_id)
        logger.info(addPrefix('Fetching category from ESI'))
        if not esi_client:
            esi_client = esi_client_factory(spec_file=get_swagger_spec_path())
        try:
            eve_category = esi_client.Universe\
                .get_universe_categories_category_id(
                    category_id=eve_category_id
                ).result()
            obj, created = self.update_or_create(
                id=eve_category_id,
                defaults={
                    'name': eve_category['name']
                }
            )
        except Exception as ex:
            logger.warn(addPrefix(
                'Failed to load category: '.format(ex)
            ))
            raise ex

        return obj, created


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
        from .models import EveCategory

        addPrefix = make_logger_prefix(eve_group_id)

        logger.info(addPrefix('Fetching group from ESI'))
        if not esi_client:
            esi_client = esi_client_factory(spec_file=get_swagger_spec_path())
        try:
            group = esi_client.Universe.get_universe_groups_group_id(
                group_id=eve_group_id
            ).result()
            eve_category, _ = EveCategory.objects.get_or_create_esi(
                group['category_id'],
                esi_client
            )
            obj, created = self.update_or_create(
                id=eve_group_id,
                defaults={
                    'name': group['name'],
                    'eve_category': eve_category
                }
            )
        except Exception as ex:
            logger.warn(addPrefix('Failed to load group: '.format(ex)))
            raise ex

        return obj, created


class EveTypeManager(models.Manager):

    def get_or_create_esi(
            self,
            eve_type_id: int,
            esi_client: object = None
    ) -> list:
        """gets or creates type object with data fetched from ESI"""
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
        """updates or creates type object with data fetched from ESI"""
        from .models import EveGroup

        addPrefix = make_logger_prefix(eve_type_id)

        logger.info(addPrefix('Fetching eve_type from ESI'))
        if not esi_client:
            esi_client = esi_client_factory(spec_file=get_swagger_spec_path())
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
                'Failed to load type: '.format(ex)
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
            esi_client = esi_client_factory(spec_file=get_swagger_spec_path())
        try:
            response = esi_client.Universe.post_universe_names(
                ids=[eve_entity_id]
            ).result()
            if len(response) > 0:
                first = response[0]
                type = EveEntity.get_matching_entity_category(
                    first['category']
                )
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
                    )
                )
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
            StructureService, EvePlanet, EveMoon
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
                esi_client
            )
        else:
            eve_planet = None

        if 'moon_id' in structure:
            eve_moon, _ = EveMoon.objects.get_or_create_esi(
                structure['moon_id'],
                esi_client
            )
        else:
            eve_moon = None

        obj, created = Structure.objects.update_or_create(
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
                state = StructureService.get_matching_state(
                    service['state']
                )
                StructureService.objects.create(
                    structure=obj,
                    name=service['name'],
                    state=state
                )
        return obj, created
