from unittest.mock import Mock, patch

from bravado.exception import HTTPBadRequest

from ..models import EveCategory
from ..helpers import EsiHelper
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


class TestEsiHelper(NoSocketsTestCase):
    
    def setUp(self):
        self.add_prefix = make_logger_prefix('Test')
        esi_get_corporations_corporation_id_structures.override_data = None

    @patch(MODULE_PATH + '.provider')
    def test_can_fetch_object_from_esi(
        self, mock_provider
    ):                    
        EsiHelper.fetch_esi_object(
            esi_path='Universe.get_universe_categories_category_id',
            args={'category_id': 65},
            add_prefix=self.add_prefix
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
    def test_raises_exception_on_invalid_esi_path(
        self, mock_provider
    ):                        
        with self.assertRaises(ValueError):
            EsiHelper.fetch_esi_object(
                'invalid', 
                Mock(),
                self.add_prefix
            )
    
    @patch(MODULE_PATH + '.provider', autospec=dummy_provider)
    def test_raises_exception_on_wrong_esi_category(
        self, mock_provider
    ):                        
        with self.assertRaises(ValueError):
            EsiHelper.fetch_esi_object(
                'invalid.get_universe_groups_group_id',               
                Mock(),
                self.add_prefix
            )
    
    @patch(MODULE_PATH + '.provider', autospec=dummy_provider)
    def test_raises_exception_on_wrong_esi_method(
        self, mock_provider
    ):                
        with self.assertRaises(ValueError):
            EsiHelper.fetch_esi_object(
                'Universe.invalid',                 
                Mock(),
                self.add_prefix
            )
    
    @patch(MODULE_PATH + '.EsiHelper._ESI_SLEEP_SECONDS_ON_RETRY', 0)
    @patch(MODULE_PATH + '.provider')
    def test_can_retry_create_on_bad_request(self, mock_provider):        
        
        def my_side_effect():
            """special mock client for testing retry ability"""
            nonlocal retry_counter, max_retries
            
            if retry_counter < max_retries:                
                retry_counter += 1
                raise HTTPBadRequest(
                    response=Mock(), 
                    message='retry_counter=%d' % retry_counter
                )
            else:                
                return esi_get_universe_categories_category_id(category_id=65)\
                    .result()
            
        mock_provider.client.Universe\
            .get_universe_categories_category_id.return_value\
            .result.side_effect = my_side_effect

        # can retry 3 times and then proceed normally
        retry_counter = 0
        max_retries = 3        
        obj, created = EveCategory.objects.update_or_create_esi(65)        
        self.assertTrue(created)
        self.assertIsInstance(obj, EveCategory)
        self.assertEqual(obj.id, 65)
        self.assertEqual(obj.name, 'Structure')
        self.assertEqual(retry_counter, 3)

        # will abort on the 4th retry and pass on exception if needed
        retry_counter = 0
        max_retries = 4
        with self.assertRaises(HTTPBadRequest):
            EveCategory.objects.update_or_create_esi(65)        
        self.assertEqual(retry_counter, 4)

    def test_can_fetch_multiple_pages(self):
        mock_client = esi_mock_client()

        structures = EsiHelper.fetch_esi_objects_with_pages(
            'Corporation.get_corporations_corporation_id_structures',
            args={'corporation_id': 2001},
            add_prefix=self.add_prefix,
            esi_client=mock_client,
            has_pages=True
        )        
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(
            {x['structure_id'] for x in structures}, 
            expected
        )
