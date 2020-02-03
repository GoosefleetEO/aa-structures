from unittest.mock import Mock, patch

from django.test import TestCase

from .. import app_settings

class TestSetAppSetting(TestCase):

    @patch('structures.utils.settings')
    def test_default_if_not_set(self, mock_settings):        
        mock_settings.STRUCTURES_TEST_BOOL = Mock(spec=None)
        app_settings.set_app_setting(
            'STRUCTURES_TEST_BOOL',             
            False,             
        )
        self.assertEqual(app_settings.STRUCTURES_TEST_BOOL, False)


    @patch('structures.utils.settings')
    def test_default_if_not_set_for_none(self, mock_settings):        
        mock_settings.STRUCTURES_TEST_BOOL = Mock(spec=None)
        app_settings.set_app_setting(
            'STRUCTURES_TEST_BOOL',             
            None,
            required_type=int
        )
        self.assertEqual(app_settings.STRUCTURES_TEST_BOOL, None)


    @patch('structures.utils.settings')
    def test_true_stays_true(self, mock_settings):
        mock_settings.STRUCTURES_TEST_BOOL = True
        app_settings.set_app_setting(
            'STRUCTURES_TEST_BOOL',             
            False,         
        )
        self.assertEqual(app_settings.STRUCTURES_TEST_BOOL, True)

    @patch('structures.utils.settings')
    def test_false_stays_false(self, mock_settings):
        mock_settings.STRUCTURES_TEST_BOOL = False
        app_settings.set_app_setting(
            'STRUCTURES_TEST_BOOL',             
            False
        )
        self.assertEqual(app_settings.STRUCTURES_TEST_BOOL, False)

    @patch('structures.utils.settings')
    def test_default_for_invalid_type_bool(self, mock_settings):
        mock_settings.STRUCTURES_TEST_BOOL = 'invalid type'
        app_settings.set_app_setting(
            'STRUCTURES_TEST_BOOL',             
            False
        )
        self.assertEqual(app_settings.STRUCTURES_TEST_BOOL, False)


    @patch('structures.utils.settings')
    def test_default_for_invalid_type_int(self, mock_settings):
        mock_settings.STRUCTURES_TEST_BOOL = 'invalid type'
        app_settings.set_app_setting(
            'STRUCTURES_TEST_BOOL',             
            50
        )
        self.assertEqual(app_settings.STRUCTURES_TEST_BOOL, 50)

    @patch('structures.utils.settings')
    def test_default_if_below_minimum_1(self, mock_settings):
        mock_settings.STRUCTURES_TEST_BOOL = -5
        app_settings.set_app_setting(
            'STRUCTURES_TEST_BOOL',             
            default_value=50
        )
        self.assertEqual(app_settings.STRUCTURES_TEST_BOOL, 50)

    @patch('structures.utils.settings')
    def test_default_if_below_minimum_2(self, mock_settings):
        mock_settings.STRUCTURES_TEST_BOOL = -50
        app_settings.set_app_setting(
            'STRUCTURES_TEST_BOOL',             
            default_value=50,
            min_value=-10
        )
        self.assertEqual(app_settings.STRUCTURES_TEST_BOOL, 50)

    @patch('structures.utils.settings')
    def test_default_for_invalid_type_int(self, mock_settings):
        mock_settings.STRUCTURES_TEST_BOOL = 1000
        app_settings.set_app_setting(
            'STRUCTURES_TEST_BOOL',             
            default_value=50,
            max_value=100
        )
        self.assertEqual(app_settings.STRUCTURES_TEST_BOOL, 50)

    
    @patch('structures.utils.settings')
    def test_default_is_none_needs_required_type(self, mock_settings):
        mock_settings.STRUCTURES_TEST_BOOL = 'invalid type'
        with self.assertRaises(ValueError):
            app_settings.set_app_setting(
                'STRUCTURES_TEST_BOOL',             
                default_value=None
            )
        

