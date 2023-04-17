from unittest.mock import MagicMock, patch

from django.core.checks import Critical
from django.test import TestCase

from structures.checks import upgrade_from_1_x_check

MODULE_PATH = "structures.checks"


@patch(MODULE_PATH + "._fetch_app_version")
class TestChecks(TestCase):
    def test_should_report_error_when_1_x_version(self, mock_fetch_app_version):
        # given
        mock_fetch_app_version.return_value = "1.5.0"
        app_configs = MagicMock()
        # when
        result = upgrade_from_1_x_check(app_configs)
        # then
        self.assertIsInstance(result[0], Critical)

    def test_should_not_report_error_when_2_x_version(self, mock_fetch_app_version):
        # given
        app_configs = MagicMock()
        mock_fetch_app_version.return_value = "2.5.0"
        # when
        result = upgrade_from_1_x_check(app_configs)
        # then
        self.assertEqual(result, [])

    def test_should_not_report_error_when_memberaudit_not_installed(
        self, mock_fetch_app_version
    ):
        # given
        app_configs = MagicMock()
        mock_fetch_app_version.return_value = ""
        # when
        result = upgrade_from_1_x_check(app_configs)
        # then
        self.assertEqual(result, [])
