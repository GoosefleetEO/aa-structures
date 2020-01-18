"""functions for loading test data and for building mocks"""

from datetime import timedelta
import inspect
import json
import math
import os
from random import randrange
from unittest.mock import Mock

from django.utils.timezone import now


ESI_CORP_STRUCTURES_PAGE_SIZE = 2

_currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
    inspect.currentframe()
)))


##############################
# internal functions

def _load_corp_structures_data():
    with open(
        _currentdir + '/corp_structures.json', 
        'r', 
        encoding='utf-8'
    ) as f:
        corp_structures_data = json.load(f)

    return corp_structures_data


def _load_universe_structures_data():
    with open(
        _currentdir + '/universe_structures.json', 
        'r', 
        encoding='utf-8'
    ) as f:
        universe_structures_data = json.load(f)

    return universe_structures_data


def _load_testdata_notifications() -> dict:    
    with open(
        _currentdir + '/notifications.json', 
        'r', 
        encoding='utf-8'
    ) as f:
        notifications_stale = json.load(f)
    
    notifications_fresh = list()
    for notification in notifications_stale:
        notification['timestamp'] =  now() - timedelta(
            hours=randrange(3), 
            minutes=randrange(60), 
            seconds=randrange(60)
        )
        notifications_fresh.append(notification)   

    return notifications_fresh


def _load_testdata_entities() -> dict:    
    with open(
        _currentdir + '/entities.json', 
        'r', 
        encoding='utf-8'
    ) as f:
        entities = json.load(f)
    
    return entities


corp_structures_data = _load_corp_structures_data()
universe_structures_data = _load_universe_structures_data()
entities_testdata = _load_testdata_entities()
notifications_testdata = _load_testdata_notifications()


##############################
# functions for mocking calls to ESI with test data

def esi_get_corporations_corporation_id_structures(corporation_id, page=None):
    """simulates ESI endpoint of same name for mock test"""

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

    if not str(corporation_id) in corp_structures_data:
        raise ValueError(
            'No test data for corporation ID: {}'. format(corporation_id)
        )
    
    corp_data = corp_structures_data[str(corporation_id)]

    start = (page - 1) * page_size
    stop = start + page_size
    pages_count = int(math.ceil(len(corp_data) / page_size))
    
    mock_operation = Mock()
    mock_operation.also_return_response = False
    mock_operation._headers = {'x-pages': pages_count}    
    mock_operation._data = corp_data[start:stop]
    mock_operation.result.side_effect = mock_result
    return mock_operation
    

def esi_get_universe_structures_structure_id(structure_id, *args, **kwargs):
    """simulates ESI endpoint of same name for mock test"""

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
    mock_operation.result.return_value = notifications_testdata
    return mock_operation