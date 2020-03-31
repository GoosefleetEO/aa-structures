from datetime import timedelta
from unittest.mock import Mock, patch

import requests

from django.test import TestCase
from django.utils import translation

from ..utils import (
    clean_setting, 
    messages_plus, 
    make_logger_prefix,
    chunks, 
    timeuntil_str, 
    NoSocketsTestCase, 
    SocketAccessError,
    app_labels,
    add_no_wrap_html,
    yesno_str
)
from ..utils import set_test_logger


MODULE_PATH = 'structures.utils'
logger = set_test_logger(MODULE_PATH, __file__)


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


class TestTimeUntil(TestCase):

    def test_timeuntil(self):
        duration = timedelta(
            days=365 + 30 * 4 + 5, seconds=3600 * 14 + 60 * 33 + 10
        )
        expected = '1y 4mt 5d 14h 33m 10s'
        self.assertEqual(timeuntil_str(duration), expected)
    
        duration = timedelta(
            days=2, seconds=3600 * 14 + 60 * 33 + 10
        )
        expected = '2d 14h 33m 10s'
        self.assertEqual(timeuntil_str(duration), expected)

        duration = timedelta(
            days=2, seconds=3600 * 14 + 60 * 33 + 10
        )
        expected = '2d 14h 33m 10s'
        self.assertEqual(timeuntil_str(duration), expected)

        duration = timedelta(
            days=0, seconds=60 * 33 + 10
        )
        expected = '0h 33m 10s'
        self.assertEqual(timeuntil_str(duration), expected)

        duration = timedelta(
            days=0, seconds=10
        )
        expected = '0h 0m 10s'
        self.assertEqual(timeuntil_str(duration), expected)

        duration = timedelta(
            days=-10, seconds=-20
        )
        expected = ''
        self.assertEqual(timeuntil_str(duration), expected)


class TestNoSocketsTestCase(NoSocketsTestCase):

    def test_raises_exception_on_attempted_network_access(self):
        
        with self.assertRaises(SocketAccessError):
            requests.get('https://www.google.com')


class TestAppLabel(TestCase):

    def test_returns_set_of_app_labels(self):
        labels = app_labels()
        for label in ['authentication', 'groupmanagement', 'eveonline']:
            self.assertIn(label, labels)


class TestHtmlHelper(TestCase):

    def test_add_no_wrap_html(self):
        expected = '<span style="white-space: nowrap;">Dummy</span>'
        self.assertEqual(add_no_wrap_html('Dummy'), expected)

    def test_yesno_str(self):
        with translation.override('en'):
            self.assertEqual(yesno_str(True), 'yes')
            self.assertEqual(yesno_str(False), 'no')
            self.assertEqual(yesno_str(None), 'no')
            self.assertEqual(yesno_str(123), 'no')
            self.assertEqual(yesno_str('xxxx'), 'no')


class TestMakeLoggerPrefix(TestCase):

    def test_make_logger_prefix_with_content(self):
        add_prefix = make_logger_prefix('tag')
        expected = 'tag: dummy'
        self.assertEqual(add_prefix('dummy'), expected)

    def test_make_logger_prefix_empty(self):
        add_prefix = make_logger_prefix('tag')
        expected = 'tag'
        self.assertEqual(add_prefix(), expected)
