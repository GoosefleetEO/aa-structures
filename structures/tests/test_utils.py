from unittest.mock import Mock, patch

from django.test import TestCase

from .. import app_settings
from . import set_logger

MODULE_PATH = 'structures.utils'

logger = set_logger(MODULE_PATH, __file__)

class TestSetAppSetting(TestCase):

    @patch(MODULE_PATH + '.settings')
    def test_default_if_not_set(self, mock_settings):        
        mock_settings.TEST_SETTING_DUMMY = Mock(spec=None)
        result = app_settings.clean_setting(
            'TEST_SETTING_DUMMY',             
            False,             
        )
        self.assertEqual(result, False)


    @patch(MODULE_PATH + '.settings')
    def test_default_if_not_set_for_none(self, mock_settings):        
        mock_settings.TEST_SETTING_DUMMY = Mock(spec=None)
        result = app_settings.clean_setting(
            'TEST_SETTING_DUMMY',             
            None,
            required_type=int
        )
        self.assertEqual(result, None)


    @patch(MODULE_PATH + '.settings')
    def test_true_stays_true(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = True
        result = app_settings.clean_setting(
            'TEST_SETTING_DUMMY',             
            False,         
        )
        self.assertEqual(result, True)

    @patch(MODULE_PATH + '.settings')
    def test_false_stays_false(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = False
        result = app_settings.clean_setting(
            'TEST_SETTING_DUMMY',             
            False
        )
        self.assertEqual(result, False)

    @patch(MODULE_PATH + '.settings')
    def test_default_for_invalid_type_bool(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = 'invalid type'
        result = app_settings.clean_setting(
            'TEST_SETTING_DUMMY',             
            False
        )
        self.assertEqual(result, False)


    @patch(MODULE_PATH + '.settings')
    def test_default_for_invalid_type_int(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = 'invalid type'
        result = app_settings.clean_setting(
            'TEST_SETTING_DUMMY',             
            50
        )
        self.assertEqual(result, 50)

    @patch(MODULE_PATH + '.settings')
    def test_default_if_below_minimum_1(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = -5
        result = app_settings.clean_setting(
            'TEST_SETTING_DUMMY',             
            default_value=50
        )
        self.assertEqual(result, 50)

    @patch(MODULE_PATH + '.settings')
    def test_default_if_below_minimum_2(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = -50
        result = app_settings.clean_setting(
            'TEST_SETTING_DUMMY',             
            default_value=50,
            min_value=-10
        )
        self.assertEqual(result, 50)

    @patch(MODULE_PATH + '.settings')
    def test_default_for_invalid_type_int(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = 1000
        result = app_settings.clean_setting(
            'TEST_SETTING_DUMMY',             
            default_value=50,
            max_value=100
        )
        self.assertEqual(result, 50)

    
    @patch(MODULE_PATH + '.settings')
    def test_default_is_none_needs_required_type(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = 'invalid type'
        with self.assertRaises(ValueError):
            result = app_settings.clean_setting(
                'TEST_SETTING_DUMMY',             
                default_value=None
            )
        

