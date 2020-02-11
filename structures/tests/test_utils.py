from unittest.mock import Mock, patch

from django.test import TestCase

from ..utils import clean_setting, messages_plus, chunks
from . import set_logger


MODULE_PATH = 'structures.utils'
logger = set_logger(MODULE_PATH, __file__)


class TestMessagePlus(TestCase):

    @patch(MODULE_PATH + '.messages')
    def test_valid_call(self, mock_messages):        
        messages_plus.debug(Mock(), 'Test Message')
        self.assertTrue(mock_messages.debug.called)
        call_args_list = mock_messages.debug.call_args_list
        args, kwargs = call_args_list[0]
        self.assertEqual(
            args[1], 
            '<span class="glyphicon glyphicon-eye-open" '
            'aria-hidden="true"></span>&nbsp;&nbsp;'
            'Test Message'
        )
    
    def test_invalid_level(self):
        with self.assertRaises(ValueError):
            messages_plus._add_messages_icon(987, 'Test Message')

    @patch(MODULE_PATH + '.messages')
    def test_all_levels(self, mock_messages):        
        text = 'Test Message'
        messages_plus.error(Mock(), text)
        self.assertTrue(mock_messages.error.called)

        messages_plus.debug(Mock(), text)
        self.assertTrue(mock_messages.debug.called)

        messages_plus.info(Mock(), text)
        self.assertTrue(mock_messages.info.called)
        
        messages_plus.success(Mock(), text)
        self.assertTrue(mock_messages.success.called)

        messages_plus.warning(Mock(), text)
        self.assertTrue(mock_messages.warning.called)


class TestChunks(TestCase):

    def test_chunks(self):
        a0 = [1, 2, 3, 4, 5, 6]
        a1 = list(chunks(a0, 2))
        self.assertListEqual(a1, [[1, 2], [3, 4], [5, 6]])
        

class TestCleanSetting(TestCase):

    @patch(MODULE_PATH + '.settings')
    def test_default_if_not_set(self, mock_settings):        
        mock_settings.TEST_SETTING_DUMMY = Mock(spec=None)
        result = clean_setting(
            'TEST_SETTING_DUMMY',             
            False,             
        )
        self.assertEqual(result, False)

    @patch(MODULE_PATH + '.settings')
    def test_default_if_not_set_for_none(self, mock_settings):        
        mock_settings.TEST_SETTING_DUMMY = Mock(spec=None)
        result = clean_setting(
            'TEST_SETTING_DUMMY',             
            None,
            required_type=int
        )
        self.assertEqual(result, None)

    @patch(MODULE_PATH + '.settings')
    def test_true_stays_true(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = True
        result = clean_setting(
            'TEST_SETTING_DUMMY',             
            False,         
        )
        self.assertEqual(result, True)

    @patch(MODULE_PATH + '.settings')
    def test_false_stays_false(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = False
        result = clean_setting(
            'TEST_SETTING_DUMMY',             
            False
        )
        self.assertEqual(result, False)

    @patch(MODULE_PATH + '.settings')
    def test_default_for_invalid_type_bool(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = 'invalid type'
        result = clean_setting(
            'TEST_SETTING_DUMMY',             
            False
        )
        self.assertEqual(result, False)

    @patch(MODULE_PATH + '.settings')
    def test_default_for_invalid_type_int(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = 'invalid type'
        result = clean_setting(
            'TEST_SETTING_DUMMY',             
            50
        )
        self.assertEqual(result, 50)

    @patch(MODULE_PATH + '.settings')
    def test_default_if_below_minimum_1(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = -5
        result = clean_setting(
            'TEST_SETTING_DUMMY',             
            default_value=50
        )
        self.assertEqual(result, 50)

    @patch(MODULE_PATH + '.settings')
    def test_default_if_below_minimum_2(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = -50
        result = clean_setting(
            'TEST_SETTING_DUMMY',             
            default_value=50,
            min_value=-10
        )
        self.assertEqual(result, 50)

    @patch(MODULE_PATH + '.settings')
    def test_default_for_invalid_type_int_2(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = 1000
        result = clean_setting(
            'TEST_SETTING_DUMMY',             
            default_value=50,
            max_value=100
        )
        self.assertEqual(result, 50)

    @patch(MODULE_PATH + '.settings')
    def test_default_is_none_needs_required_type(self, mock_settings):
        mock_settings.TEST_SETTING_DUMMY = 'invalid type'
        with self.assertRaises(ValueError):
            clean_setting(
                'TEST_SETTING_DUMMY',             
                default_value=None
            )
