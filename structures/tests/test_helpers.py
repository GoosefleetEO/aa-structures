from unittest.mock import Mock, patch

from bravado.exception import (
    HTTPBadGateway, HTTPServiceUnavailable, HTTPGatewayTimeout, HTTPForbidden
)

from ..helpers import EsiSmartRequest
from ..models.eveuniverse import EsiNameLocalization
from .testdata import (
    esi_get_universe_categories_category_id, 
    esi_mock_client,
    esi_get_corporations_corporation_id_structures
)
from ..utils import NoSocketsTestCase, set_test_logger, make_logger_prefix


MODULE_PATH = 'structures.helpers'
logger = set_test_logger(MODULE_PATH, __file__)


class Dummy():
    """this class is needed to create a nested object to spec an ESI client"""
    pass


dummy_provider = Dummy()
dummy_provider.client = Dummy()
dummy_provider.client.Universe = Dummy()
dummy_provider.client.Universe.get_universe_categories_category_id = Dummy()


class TestEsiSmartRequest(NoSocketsTestCase):
    
    def setUp(self):
        self.add_prefix = make_logger_prefix('Test')
        esi_get_corporations_corporation_id_structures.override_data = None

    @patch(MODULE_PATH + '.provider')
    def test_can_fetch_object_from_esi(self, mock_provider):                    
        EsiSmartRequest.fetch(
            esi_path='Universe.get_universe_categories_category_id',
            args={'category_id': 65},
            logger_tag='dummy'
        )                
        self.assertEqual(len(mock_provider.mock_calls), 2)        
        args = mock_provider.mock_calls[0]
        self.assertEqual(len(args), 3)
        self.assertEqual(
            args[0], 'client.Universe.get_universe_categories_category_id'
        )
        self.assertEqual(
            args[2], {'category_id': 65}
        )        

    @patch(MODULE_PATH + '.provider')
    def test_raises_exception_on_invalid_esi_path(self, mock_provider):                        
        with self.assertRaises(ValueError):
            EsiSmartRequest.fetch(
                'invalid', 
                {'group_id': 65}
            )
    
    @patch(MODULE_PATH + '.provider', autospec=dummy_provider)
    def test_raises_exception_on_wrong_esi_category(self, mock_provider):                        
        with self.assertRaises(ValueError):
            EsiSmartRequest.fetch(
                'invalid.get_universe_groups_group_id',               
                {'group_id': 65}
            )
    
    @patch(MODULE_PATH + '.provider', autospec=dummy_provider)
    def test_raises_exception_on_wrong_esi_method(self, mock_provider):                
        with self.assertRaises(ValueError):
            EsiSmartRequest.fetch(
                'Universe.invalid',                 
                {'group_id': 65}
            )
    
    @patch(MODULE_PATH + '.EsiSmartRequest._ESI_RETRY_SLEEP_SECS', 0)
    @patch(MODULE_PATH + '.provider')
    def test_can_retry_on_exceptions(self, mock_provider):        
        
        def my_side_effect():
            """special mock client for testing retry ability"""
            nonlocal retry_counter, max_retries
            
            if retry_counter < max_retries:                
                retry_counter += 1
                raise MyException(
                    response=Mock(), 
                    message='retry_counter=%d' % retry_counter
                )
            else:                
                return esi_get_universe_categories_category_id(category_id=65)\
                    .result()
            
        mock_provider.client.Universe\
            .get_universe_categories_category_id.return_value\
            .result.side_effect = my_side_effect

        # can retry 3 times and then proceed normally on 502s
        MyException = HTTPBadGateway
        retry_counter = 0
        max_retries = 3        
        response_object = EsiSmartRequest.fetch(
            'Universe.get_universe_categories_category_id',
            {'category_id': 65}
        )        
        self.assertEqual(response_object['id'], 65)
        self.assertEqual(response_object['name'], 'Structure')
        self.assertEqual(retry_counter, 3)

        # will abort on the 4th retry and pass on exception if needed
        retry_counter = 0
        max_retries = 4
        with self.assertRaises(MyException):
            response_object = EsiSmartRequest.fetch(
                'Universe.get_universe_categories_category_id',
                {'category_id': 65},
                Mock()
            )
        self.assertEqual(retry_counter, 4)

        # will retry on 503s
        MyException = HTTPServiceUnavailable
        retry_counter = 0
        max_retries = 3
        response_object = EsiSmartRequest.fetch(
            'Universe.get_universe_categories_category_id',
            {'category_id': 65}
        )        
        self.assertEqual(response_object['id'], 65)
        self.assertEqual(response_object['name'], 'Structure')
        self.assertEqual(retry_counter, 3)

        # will retry on 504s
        MyException = HTTPGatewayTimeout
        retry_counter = 0
        max_retries = 3
        response_object = EsiSmartRequest.fetch(
            'Universe.get_universe_categories_category_id',
            {'category_id': 65}
        )        
        self.assertEqual(response_object['id'], 65)
        self.assertEqual(response_object['name'], 'Structure')
        self.assertEqual(retry_counter, 3)

        # will not retry on other HTTP exceptions
        MyException = HTTPForbidden
        retry_counter = 0
        max_retries = 3
        with self.assertRaises(MyException):
            response_object = EsiSmartRequest.fetch(
                'Universe.get_universe_categories_category_id',
                {'category_id': 65},
                Mock()
            )
        self.assertEqual(retry_counter, 1)

    def test_can_fetch_multiple_pages(self):
        mock_client = esi_mock_client()

        structures = EsiSmartRequest.fetch(
            'Corporation.get_corporations_corporation_id_structures',
            args={'corporation_id': 2001},
            esi_client=mock_client,
            has_pages=True
        )        
        
        # has all structures
        structure_ids = {x['structure_id'] for x in structures}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)
        
        # has services                
        service_names = list()
        for obj in structures:
            if obj['structure_id'] == 1000000000001:                        
                service_names = {x['name'] for x in obj['services']}
        expected = {'Clone Bay', 'Market Hub'}
        self.assertEqual(service_names, expected)

    def test_can_fetch_multiple_pages_and_languages(self):
        mock_client = esi_mock_client()

        structures_list = EsiSmartRequest.fetch_with_localization(
            'Corporation.get_corporations_corporation_id_structures',
            args={'corporation_id': 2001},
            esi_client=mock_client,
            has_pages=True,            
            languages=EsiNameLocalization.ESI_LANGUAGES,
            logger_tag='dummy'
        )        
        
        for language, structures in structures_list.items():
            # has all structures                
            structure_ids = {x['structure_id'] for x in structures}
            expected = {1000000000001, 1000000000002, 1000000000003}
            self.assertSetEqual(structure_ids, expected)
            
            # has services in all languages
            service_names = list()
            for obj in structures:
                if obj['structure_id'] == 1000000000001:                        
                    service_names = {x['name'] for x in obj['services']}
            if language == 'en-us':
                expected = {'Clone Bay', 'Market Hub'}
            else:
                expected = {'Clone Bay_' + language, 'Market Hub_' + language}
            self.assertEqual(service_names, expected)
