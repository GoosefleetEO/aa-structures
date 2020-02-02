"""functions for loading test data and for building mocks"""

from datetime import timedelta
import inspect
import json
import math
import os
from random import randrange
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.utils.timezone import now

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo

from ...models import *


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
        notification['timestamp'] =  now() - timedelta(
            hours=randrange(3), 
            minutes=randrange(60), 
            seconds=randrange(60)
        )
        
    return entities


_esi_data = _load_esi_data()
esi_corp_structures_data = \
    _esi_data['Corporation']['get_corporations_corporation_id_structures']
entities_testdata = _load_testdata_entities()


##############################
# functions for mocking calls to ESI with test data

def esi_get_corporations_corporation_id_structures(corporation_id, page=None):
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
        if (not isinstance(
            esi_get_corporations_corporation_id_structures.override_data, 
            dict
        )):
            raise TypeError('data must be dict')

        my_corp_structures_data \
            = esi_get_corporations_corporation_id_structures.override_data

    if not str(corporation_id) in my_corp_structures_data:
        raise ValueError(
            'No test data for corporation ID: {}'. format(corporation_id)
        )
    
    corp_data = my_corp_structures_data[str(corporation_id)]

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
    corporation_id, 
    page=None
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

    if esi_get_corporations_corporation_id_customs_offices.override_data is None:
        my_corp_customs_offices_data = \
            _esi_data['Planetary_Interaction']['get_corporations_corporation_id_customs_offices']

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
    
    corp_data = my_corp_customs_offices_data[str(corporation_id)]

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
    item_ids: list
) -> list:
    """simulates ESI endpoint of same name for mock test"""

    if str(corporation_id) not in _esi_data['Corporation'][category]:
        raise RuntimeError(
            'No asset data found for corporation {} in {}'.format(
                corporation_id,
                category
        ))
    else:        
        mock_operation = Mock()
        mock_operation.result.return_value = \
            _esi_data['Corporation'][category][str(corporation_id)]
        return mock_operation


def esi_post_corporations_corporation_id_assets_locations(
    corporation_id: int, 
    item_ids: list
) -> list:
    return _esi_post_corporations_corporation_id_assets(
        'post_corporations_corporation_id_assets_locations', 
        corporation_id,
        item_ids
    )


def esi_post_corporations_corporation_id_assets_names(
    corporation_id: int, 
    item_ids: list
) -> list:
    return _esi_post_corporations_corporation_id_assets(
        'post_corporations_corporation_id_assets_names', 
        corporation_id,
        item_ids
    )
    

###################################
# helper functions
# 

def load_entity(EntityClass):
    """loads testdata for given entity class"""
    entity_name = EntityClass.__name__        
    for x in entities_testdata[entity_name]:
        EntityClass.objects.create(**x)
    assert(len(entities_testdata[entity_name]) == EntityClass.objects.count()) 


def load_entities(entities_def: list = None):
    """loads testdata for given entities classes"""
    if not entities_def:
        entities_def = [
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
            StructureTag
        ]
    
    for EntityClass in entities_def:
        entity_name = EntityClass.__name__
        EntityClass.objects.all().delete()
        for x in entities_testdata[entity_name]:
            EntityClass.objects.create(**x)
        assert(
            len(entities_testdata[entity_name]) == EntityClass.objects.count()
        )


def create_structures():
    """create structure entities from test data
    Will create all structure for owner if provided
    """
    
    load_entities()
            
    for corporation in EveCorporationInfo.objects.all():
        EveEntity.objects.get_or_create(
            id = corporation.corporation_id,
            defaults={
                'category': EveEntity.CATEGORY_CORPORATION,
                'name': corporation.corporation_name
            }
        )
        Owner.objects.create(
            corporation=corporation
        )
        if int(corporation.corporation_id) in [2001, 2002]:
            alliance = EveAllianceInfo.objects.get(alliance_id=3001)
            corporation.alliance = alliance
            corporation.save()


    for character in EveCharacter.objects.all():
        EveEntity.objects.get_or_create(
            id = character.character_id,
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

    tag_a = StructureTag.objects.get(name='tag_a')
    tag_b = StructureTag.objects.get(name='tag_b')
    tag_c = StructureTag.objects.get(name='tag_c')
    Structure.objects.all().delete()
    for structure in entities_testdata['Structure']:
        x = structure.copy()        
        x['owner'] = Owner.objects.get(
            corporation__corporation_id=x['owner_corporation_id']
        )
        del x['owner_corporation_id']
        
        if 'services' in x:
            del x['services']
        
        obj = Structure.objects.create(**x)
        if obj.id in [1000000000001, 1000000000002]:
            obj.fuel_expires = now() + timedelta(days=randrange(10) + 1)
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
                    state=StructureService.get_matching_state(
                        service['state']
                ))
        obj.save()
                
        
def set_owner_character(character_id) -> list:
    """sets owner character for the owner related to the given character ir
    returns user, owner
    """
    my_character = EveCharacter.objects.get(character_id=1001)                        
    my_user = User.objects.create_user(
        my_character.character_name,
        'abc@example.com',
        'password'
    )
    my_ownership = CharacterOwnership.objects.create(
        character=my_character,
        owner_hash='x1',
        user=my_user
    )
    my_user.profile.main_character = my_character        
    my_owner = Owner.objects.get(
        corporation__corporation_id=my_character.corporation_id
    )
    my_owner.character = my_ownership
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
            sender_type = \
                EveEntity.get_matching_entity_type(
                    notification['sender_type']
                )                
            sender = EveEntity.objects.get(id=notification['sender_id'])                
            text = notification['text'] \
                if 'text' in notification else None
            is_read = notification['is_read'] \
                if 'is_read' in notification else None
            timestamp_start = timestamp_start + timedelta(minutes=5)
            obj = Notification.objects.update_or_create(
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