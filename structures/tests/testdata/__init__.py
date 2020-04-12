"""functions for loading test data and for building mocks"""

from copy import deepcopy
from datetime import timedelta
import inspect
import json
import math
import os
from random import randrange
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.utils.timezone import now

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo

from ...models import (
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
    EveEntity,
    Webhook,
    Owner,
    Notification,
    Structure,    
)
from ...models.eveuniverse import EveUniverse

ESI_CORP_STRUCTURES_PAGE_SIZE = 2

_currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
    inspect.currentframe()
)))


##############################
# internal functions

def _load_esi_data():
    with open(
        _currentdir + '/esi_data.json', 
        'r', 
        encoding='utf-8'
    ) as f:
        data = json.load(f)

    return data


def _load_testdata_entities() -> dict:    
    with open(
        _currentdir + '/entities.json', 
        'r', 
        encoding='utf-8'
    ) as f:
        entities = json.load(f)
    
    # update timestamp to current
    for notification in entities['Notification']:
        notification['timestamp'] = now() - timedelta(
            hours=randrange(3), 
            minutes=randrange(60), 
            seconds=randrange(60)
        )

    # update timestamps on structures
    for structure in entities['Structure']:
        if 'fuel_expires' in structure:
            fuel_expires = now() + timedelta(days=1 + randrange(5))
            structure['fuel_expires'] = fuel_expires

        if 'state_timer_start' in structure:
            state_timer_start = now() + timedelta(days=1 + randrange(3))
            structure['state_timer_start'] = state_timer_start
            state_timer_end = state_timer_start + timedelta(minutes=15)
            structure['state_timer_end'] = state_timer_end

        if 'unanchors_at' in structure:
            unanchors_at = now() + timedelta(days=3 + randrange(5))
            structure['unanchors_at'] = unanchors_at
        
    return entities


_esi_data = _load_esi_data()
esi_corp_structures_data = \
    _esi_data['Corporation']['get_corporations_corporation_id_structures']
entities_testdata = _load_testdata_entities()


##############################
# functions for mocking calls to ESI with test data

ESI_LANGUAGES = {'de', 'en-us', 'fr', 'ja', 'ru', 'zh', 'ko'}


def esi_get_universe_planets_planet_id(planet_id, language=None):
    """simulates ESI endpoint of same name for mock test
    will use the respective test data 
    unless the function property override_data is set
    """

    entity = None
    for x in entities_testdata['EvePlanet']:
        if x['id'] == planet_id:
            entity = x.copy()
            break
    
    if entity is None:        
        raise ValueError(
            'entity with id {} not found in testdata'.format(planet_id)
        )
        
    entity['planet_id'] = entity.pop('id')
    entity['system_id'] = entity.pop('eve_solar_system_id')
    entity['type_id'] = entity.pop('eve_type_id')    
    entity['position'] = {
        'x': 1,
        'y': 2,
        'z': 3
    }

    if language in ESI_LANGUAGES.difference({'en-us'}):
        entity['name'] += '_' + language

    mock_operation = Mock()
    mock_operation.result.return_value = entity
    return mock_operation


def esi_get_corporations_corporation_id_structures(
    corporation_id, page=None, language=None
):
    """simulates ESI endpoint of same name for mock test
    will use the respective test data 
    unless the function property override_data is set
    """

    def mock_result():
        """simulates behavior of result()"""
        if mock_operation.also_return_response:            
            mock_response = Mock()
            mock_response.headers = mock_operation._headers
            return [mock_operation._data, mock_response]
        else:
            return mock_operation._data
  
    page_size = ESI_CORP_STRUCTURES_PAGE_SIZE
    if not page:
        page = 1

    if esi_get_corporations_corporation_id_structures.override_data is None:
        my_corp_structures_data = esi_corp_structures_data
    else:
        if (
            not isinstance(
                esi_get_corporations_corporation_id_structures.override_data, 
                dict
            )
        ):
            raise TypeError('data must be dict')

        my_corp_structures_data \
            = esi_get_corporations_corporation_id_structures.override_data

    if not str(corporation_id) in my_corp_structures_data:
        raise ValueError(
            'No test data for corporation ID: {}'. format(corporation_id)
        )
    
    corp_data = deepcopy(my_corp_structures_data[str(corporation_id)])

    # add pseudo localization
    if language:
        for obj in corp_data:
            if 'services' in obj and obj['services']:
                for service in obj['services']:
                    if language != 'en-us':
                        service['name'] += '_%s' % language

    start = (page - 1) * page_size
    stop = start + page_size
    pages_count = int(math.ceil(len(corp_data) / page_size))
    
    mock_operation = Mock()
    mock_operation.also_return_response = False
    mock_operation._headers = {'x-pages': pages_count}    
    mock_operation._data = corp_data[start:stop]
    mock_operation.result.side_effect = mock_result
    return mock_operation
    
    
esi_get_corporations_corporation_id_structures.override_data = None


def esi_get_corporations_corporation_id_starbases(corporation_id, page=None):
    """simulates ESI endpoint of same name for mock test
    will use the respective test data 
    unless the function property override_data is set
    """

    def mock_result():
        """simulates behavior of result()"""
        if mock_operation.also_return_response:            
            mock_response = Mock()
            mock_response.headers = mock_operation._headers
            return [mock_operation._data, mock_response]
        else:
            return mock_operation._data
  
    page_size = ESI_CORP_STRUCTURES_PAGE_SIZE
    if not page:
        page = 1

    if esi_get_corporations_corporation_id_starbases.override_data is None:
        my_corp_starbases_data = \
            _esi_data['Corporation'][
                'get_corporations_corporation_id_starbases'
            ]
    else:
        if (
            not isinstance(
                esi_get_corporations_corporation_id_starbases.override_data, 
                dict
            )
        ):
            raise TypeError('data must be dict')

        my_corp_starbases_data \
            = esi_get_corporations_corporation_id_starbases.override_data

    if not str(corporation_id) in my_corp_starbases_data:
        raise ValueError(
            'No test data for corporation ID: {}'. format(corporation_id)
        )
    
    corp_data = deepcopy(my_corp_starbases_data[str(corporation_id)])

    start = (page - 1) * page_size
    stop = start + page_size
    pages_count = int(math.ceil(len(corp_data) / page_size))
    
    mock_operation = Mock()
    mock_operation.also_return_response = False
    mock_operation._headers = {'x-pages': pages_count}    
    mock_operation._data = corp_data[start:stop]
    mock_operation.result.side_effect = mock_result
    return mock_operation
    

esi_get_corporations_corporation_id_starbases.override_data = None


def esi_get_corporations_corporation_id_starbases_starbase_id(
    corporation_id, starbase_id, system_id
):
    """simulates ESI endpoint of same name for mock test"""

    corporation_starbase_details = \
        _esi_data['Corporation']['get_corporations_corporation_id_starbases_starbase_id']   # noqa
    if str(starbase_id) in corporation_starbase_details:
        mock_operation = Mock()
        mock_operation.result.return_value = \
            corporation_starbase_details[str(starbase_id)]
        return mock_operation

    else:
        raise RuntimeError(
            'Can not find data for starbase {}'.format(starbase_id)
        )


def esi_get_universe_structures_structure_id(structure_id, *args, **kwargs):
    """simulates ESI endpoint of same name for mock test"""

    universe_structures_data = \
        _esi_data['Universe']['get_universe_structures_structure_id']
    if str(structure_id) in universe_structures_data:
        mock_operation = Mock()
        mock_operation.result.return_value = \
            universe_structures_data[str(structure_id)]
        return mock_operation

    else:
        raise RuntimeError(
            'Can not find structure for {}'.format(structure_id)
        )

 
def esi_get_characters_character_id_notifications(character_id):            
    """simulates ESI endpoint of same name for mock test"""

    mock_operation = Mock()
    mock_operation.result.return_value = entities_testdata['Notification']
    return mock_operation


def esi_get_corporations_corporation_id_customs_offices(
    corporation_id, page=None
):
    """simulates ESI endpoint of same name for mock test
    will use the respective test data
    unless the function property override_data is set
    """

    def mock_result():
        """simulates behavior of result()"""
        if mock_operation.also_return_response:            
            mock_response = Mock()
            mock_response.headers = mock_operation._headers
            return [mock_operation._data, mock_response]
        else:
            return mock_operation._data
  
    page_size = ESI_CORP_STRUCTURES_PAGE_SIZE
    if not page:
        page = 1

    if esi_get_corporations_corporation_id_customs_offices.override_data is None:   # noqa: E501
        my_corp_customs_offices_data = \
            _esi_data['Planetary_Interaction'][
                'get_corporations_corporation_id_customs_offices'
            ]

    else:
        if (not isinstance(
            esi_get_corporations_corporation_id_customs_offices.override_data, 
            dict
        )):
            raise TypeError('data must be dict')

        my_corp_customs_offices_data \
            = esi_get_corporations_corporation_id_customs_offices.override_data

    if not str(corporation_id) in my_corp_customs_offices_data:
        raise ValueError(
            'No test data for corporation ID: {}'. format(corporation_id)
        )
    
    corp_data = deepcopy(my_corp_customs_offices_data[str(corporation_id)])

    start = (page - 1) * page_size
    stop = start + page_size
    pages_count = int(math.ceil(len(corp_data) / page_size))
    
    mock_operation = Mock()
    mock_operation.also_return_response = False
    mock_operation._headers = {'x-pages': pages_count}    
    mock_operation._data = corp_data[start:stop]
    mock_operation.result.side_effect = mock_result
    return mock_operation
    

esi_get_corporations_corporation_id_customs_offices.override_data = None


def _esi_post_corporations_corporation_id_assets(
    category: str,
    corporation_id: int, 
    item_ids: list,
    my_esi_data: list = None
) -> list:
    """simulates ESI endpoint of same name for mock test"""

    if my_esi_data is None:
        my_esi_data = _esi_data['Corporation'][category]
    
    if str(corporation_id) not in my_esi_data:
        raise RuntimeError(
            'No asset data found for corporation {} in {}'.format(
                corporation_id,
                category
            )
        )
    else:        
        mock_operation = Mock()
        mock_operation.result.return_value = my_esi_data[str(corporation_id)]
        return mock_operation


def esi_post_corporations_corporation_id_assets_locations(
    corporation_id: int, item_ids: list
) -> list:
    return _esi_post_corporations_corporation_id_assets(
        'post_corporations_corporation_id_assets_locations', 
        corporation_id,
        item_ids,
        esi_post_corporations_corporation_id_assets_locations.override_data
    )


esi_post_corporations_corporation_id_assets_locations.override_data = None


def esi_post_corporations_corporation_id_assets_names(
    corporation_id: int, item_ids: list
) -> list:
    return _esi_post_corporations_corporation_id_assets(
        'post_corporations_corporation_id_assets_names', 
        corporation_id,
        item_ids,
        esi_post_corporations_corporation_id_assets_names.override_data
    )
    

esi_post_corporations_corporation_id_assets_names.override_data = None


def esi_get_universe_categories_category_id(category_id, language=None):
    mock_operation = Mock()
    obj_data = {
        "id": 65,
        "name": "Structure"
    }    
    if language in ESI_LANGUAGES.difference({'en-us'}):
        obj_data['name'] += '_' + language

    mock_operation.result.return_value = obj_data
    return mock_operation


def esi_get_universe_moons_moon_id(moon_id, language=None):
    mock_operation = Mock()
    obj_data = {
        "id": 40161465,
        "name": "Amamake II - Moon 1",
        "system_id": 30002537,
        "position": {
            "x": 1,
            "y": 2,
            "z": 3
        }
    }    
    if language in ESI_LANGUAGES.difference({'en-us'}):
        obj_data['name'] += '_' + language

    mock_operation.result.return_value = obj_data
    return mock_operation


def esi_mock_client():
    """provides a mocked ESI client"""
    mock_client = Mock()
        
    # Assets
    mock_client.Assets\
        .post_corporations_corporation_id_assets_locations = \
        esi_post_corporations_corporation_id_assets_locations
    mock_client.Assets\
        .post_corporations_corporation_id_assets_names = \
        esi_post_corporations_corporation_id_assets_names
    
    # Character
    mock_client.Character\
        .get_characters_character_id_notifications.side_effect =\
        esi_get_characters_character_id_notifications

    # Corporation
    mock_client.Corporation\
        .get_corporations_corporation_id_structures.side_effect = \
        esi_get_corporations_corporation_id_structures
    mock_client.Corporation\
        .get_corporations_corporation_id_starbases.side_effect = \
        esi_get_corporations_corporation_id_starbases
    mock_client.Corporation\
        .get_corporations_corporation_id_starbases_starbase_id.side_effect = \
        esi_get_corporations_corporation_id_starbases_starbase_id
    
    # Planetary Interaction
    mock_client.Planetary_Interaction\
        .get_corporations_corporation_id_customs_offices = \
        esi_get_corporations_corporation_id_customs_offices
    
    # Universe
    mock_client.Universe\
        .get_universe_categories_category_id\
        .side_effect = esi_get_universe_categories_category_id
        
    mock_client.Universe\
        .get_universe_groups_group_id.return_value\
        .result.return_value = {
            "id": 1657,
            "name": "Citadel",
            "category_id": 65
        } 
    mock_client.Universe\
        .get_universe_types_type_id\
        .return_value.result.return_value = {
            "id": 35832,
            "name": "Astrahus",
            "group_id": 1657
        }            
    mock_client.Universe\
        .get_universe_regions_region_id\
        .return_value.result.return_value = {
            "id": 10000005,
            "name": "Detorid"
        }
    mock_client.Universe\
        .get_universe_constellations_constellation_id\
        .return_value.result.return_value = {
            "id": 20000069,
            "name": "1RG-GU",
            "region_id": 10000005
        }
    mock_client.Universe\
        .get_universe_systems_system_id\
        .return_value.result.return_value = {
            "id": 30000474,
            "name": "1-PGSG",
            "security_status": -0.496552765369415,
            "constellation_id": 20000069,
            "star_id": 99,
            "planets":
            [
                {
                    "planet_id": 40029526
                },
                {
                    "planet_id": 40029528
                },
                {
                    "planet_id": 40029529
                }
            ]
        }
    mock_client.Universe.get_universe_planets_planet_id\
        .side_effect = esi_get_universe_planets_planet_id

    mock_client.Universe.get_universe_moons_moon_id\
        .side_effect = esi_get_universe_moons_moon_id
        
    mock_client.Universe.post_universe_names\
        .return_value.result.return_value = [
            {
                "id": 3011,
                "category": "alliance",
                "name": "Big Bad Alliance"
            }                
        ]

    mock_client.Universe\
        .get_universe_structures_structure_id.side_effect =\
        esi_get_universe_structures_structure_id
  
    return mock_client


###################################
# helper functions
# 

def load_entity(EntityClass):
    """loads testdata for given entity class"""
    entity_name = EntityClass.__name__
    EntityClass.objects.all().delete()
    for obj in entities_testdata[entity_name]:
        if issubclass(EntityClass, EveUniverse) and EntityClass.has_esi_localization():            
            for _, lc_model, lc_esi in EveUniverse.LANG_CODES_MAPPING:
                if lc_esi != EveUniverse.ESI_DEFAULT_LANGUAGE:
                    obj['name_' + lc_model] = obj['name'] + '_' + lc_model
        EntityClass.objects.create(**obj)
    assert(len(entities_testdata[entity_name]) == EntityClass.objects.count()) 


def load_entities(entities_def: list = None):
    """loads testdata for given entities classes"""
    entities_def_master = [
        EveCategory,
        EveGroup,
        EveType,
        EveRegion,
        EveConstellation,
        EveSolarSystem,
        EveMoon,
        EvePlanet,            
        EveAllianceInfo,
        EveCorporationInfo,
        EveCharacter,    
        EveEntity,
        StructureTag,
        Webhook
    ]    
    for EntityClass in entities_def_master:
        if not entities_def or EntityClass in entities_def:
            load_entity(EntityClass)


def create_structures():
    """create structure entities from test data
    Will create all structure for owner if provided
    """
    
    load_entities()
            
    default_webhooks = Webhook.objects.filter(is_default=True)
    for corporation in EveCorporationInfo.objects.all():
        EveEntity.objects.get_or_create(
            id=corporation.corporation_id,
            defaults={
                'category': EveEntity.CATEGORY_CORPORATION,
                'name': corporation.corporation_name
            }
        )
        my_owner = Owner.objects.create(corporation=corporation)
        for x in default_webhooks:
            my_owner.webhooks.add(x)

        if int(corporation.corporation_id) in [2001, 2002]:
            alliance = EveAllianceInfo.objects.get(alliance_id=3001)
            corporation.alliance = alliance
            corporation.save()

    for character in EveCharacter.objects.all():
        EveEntity.objects.get_or_create(
            id=character.character_id,
            defaults={
                'category': EveEntity.CATEGORY_CHARACTER,
                'name': character.character_name
            }
        )
        corporation = EveCorporationInfo.objects.get(
            corporation_id=character.corporation_id
        )
        if corporation.alliance:                
            character.alliance_id = corporation.alliance.alliance_id
            character.alliance_name = corporation.alliance.alliance_name
            character.save()

    StructureTag.objects.get(name='tag_a')
    tag_b = StructureTag.objects.get(name='tag_b')
    tag_c = StructureTag.objects.get(name='tag_c')
    Structure.objects.all().delete()
    for structure in entities_testdata['Structure']:
        x = structure.copy()
        x['last_updated'] = now()
        x['owner'] = Owner.objects.get(
            corporation__corporation_id=x['owner_corporation_id']
        )
        del x['owner_corporation_id']
        
        if 'services' in x:
            del x['services']

        obj = Structure.objects.create(**x)        
        if obj.state != 11:
            obj.state_timer_start = \
                now() - timedelta(days=randrange(3) + 1)
            obj.state_timer_start = \
                obj.state_timer_start + timedelta(days=randrange(4) + 1)
        
        if obj.id in [1000000000002, 1000000000003]:
            obj.tags.add(tag_c)

        if obj.id in [1000000000003]:
            obj.tags.add(tag_b)

        if 'services' in structure:            
            for service in structure['services']:
                StructureService.objects.create(
                    structure=obj,
                    name=service['name'],
                    state=StructureService.get_matching_state_for_esi_state(
                        service['state']
                    )
                )
        obj.save()


def create_user(character_id, load_data=False) -> User:
    """create a user from the given character id and returns it
    
    Needs: EveCharacter
    """
    if load_data:
        load_entity(EveCharacter)
    
    my_character = EveCharacter.objects.get(character_id=character_id)
    my_user = User.objects.create_user(
        my_character.character_name,
        'abc@example.com',
        'password'
    )
    CharacterOwnership.objects.create(
        character=my_character,
        owner_hash='x1' + my_character.character_name,
        user=my_user
    )
    my_user.profile.main_character = my_character    
    return my_user


def set_owner_character(character_id) -> list:
    """sets owner character for the owner related to the given character ir
    returns user, owner
    """
    my_user = create_user(character_id)
    my_character = my_user.profile.main_character
    my_owner = Owner.objects.get(
        corporation__corporation_id=my_character.corporation_id
    )
    my_owner.character = my_user.character_ownerships.get(
        character__character_id=my_character.character_id
    )
    my_owner.save()    
    return my_user, my_owner


def load_notification_entities(owner: Owner):        
    timestamp_start = now() - timedelta(hours=2)
    for notification in entities_testdata['Notification']:
        notification_type = \
            Notification.get_matching_notification_type(
                notification['type']
            )
        if notification_type:            
            sender = EveEntity.objects.get(id=notification['sender_id'])                
            text = notification['text'] \
                if 'text' in notification else None
            is_read = notification['is_read'] \
                if 'is_read' in notification else None
            timestamp_start = timestamp_start + timedelta(minutes=5)
            Notification.objects.update_or_create(
                notification_id=notification['notification_id'],
                owner=owner,
                defaults={
                    'sender': sender,
                    'timestamp': timestamp_start,
                    'notification_type': notification_type,
                    'text': text,
                    'is_read': is_read,
                    'last_updated': now(),
                    'is_sent': False
                }
            )   


def get_all_notification_ids() -> set:
    """returns a set of all notification ids"""
    ids = set()        
    for x in entities_testdata['Notification']:        
        if x['type'] in Notification.get_all_type_names():
            ids.add(x['notification_id'])
    return ids
