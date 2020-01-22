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
        data = json.load(f)

    return data


def _load_universe_structures_data():
    with open(
        _currentdir + '/universe_structures.json', 
        'r', 
        encoding='utf-8'
    ) as f:
        data = json.load(f)

    return data


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


def _load_corp_customs_offices_data():
    with open(
        _currentdir + '/corp_customs_offices.json', 
        'r', 
        encoding='utf-8'
    ) as f:
        data = json.load(f)

    return data


def _load_corp_asset_data():
    with open(
        _currentdir + '/corp_assets.json', 
        'r', 
        encoding='utf-8'
    ) as f:
        data = json.load(f)

    return data


corp_structures_data = _load_corp_structures_data()
universe_structures_data = _load_universe_structures_data()
entities_testdata = _load_testdata_entities()
notifications_testdata = _load_testdata_notifications()
corp_customs_offices_data = _load_corp_customs_offices_data()
corp_asset_data = _load_corp_asset_data()


##############################
# functions for mocking calls to ESI with test data

def esi_get_corporations_corporation_id_structures(corporation_id, page=None):
    """simulates ESI endpoint of same name for mock test
    will use the respective test data (corp_structures_data)
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
        my_corp_structures_data = corp_structures_data
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


def esi_get_corporations_corporation_id_customs_offices(
    corporation_id, 
    page=None
):
    """simulates ESI endpoint of same name for mock test
    will use the respective test data (corp_customs_offices_data)
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
        my_corp_customs_offices_data = corp_customs_offices_data
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

    if str(corporation_id) not in corp_asset_data[category]:
        raise RuntimeError(
            'No asset data found for corporation {} in {}'.format(
                corporation_id,
                category
        ))
    else:        
        mock_operation = Mock()
        mock_operation.result.return_value = \
            corp_asset_data[category][str(corporation_id)]
        return mock_operation


def esi_post_corporations_corporation_id_assets_locations(
    corporation_id: int, 
    item_ids: list
) -> list:
    return _esi_post_corporations_corporation_id_assets(
        'locations', 
        corporation_id,
        item_ids
    )

def esi_post_corporations_corporation_id_assets_names(
    corporation_id: int, 
    item_ids: list
) -> list:
    return _esi_post_corporations_corporation_id_assets(
        'names', 
        corporation_id,
        item_ids
    )
    
