from unittest.mock import Mock, patch

from bravado.exception import (
    HTTPBadGateway,
    HTTPForbidden,
    HTTPGatewayTimeout,
    HTTPServiceUnavailable,
)

from app_utils.logging import make_logger_prefix
from app_utils.testing import NoSocketsTestCase

from structures.helpers.esi_fetch import esi_fetch, esi_fetch_with_localization
from structures.models.eveuniverse import EsiNameLocalization
from structures.tests.testdata import (
    esi_get_corporations_corporation_id_structures,
    esi_get_universe_categories_category_id,
    esi_mock_client,
)

MODULE_PATH = __package__ + ".esi_fetch"


class TestEsiFetch(NoSocketsTestCase):
    def setUp(self):
        self.add_prefix = make_logger_prefix("Test")
        esi_get_corporations_corporation_id_structures.override_data = None

    @patch(MODULE_PATH + "._esi_client")
    def test_can_fetch_object_from_esi(self, mock_esi_client):
        esi_fetch(
            esi_path="Universe.get_universe_categories_category_id",
            args={"category_id": 65},
            logger_tag="dummy",
        )
        self.assertEqual(
            len(
                mock_esi_client.return_value.Universe.get_universe_categories_category_id.mock_calls
            ),
            2,
        )
        (
            args,
            kwargs,
        ) = (
            mock_esi_client.return_value.Universe.get_universe_categories_category_id.call_args
        )
        self.assertEqual(kwargs, {"category_id": 65})

    @patch(MODULE_PATH + "._esi_client")
    def test_can_fetch_object_with_client(self, mock_esi_client):
        mock_client = Mock()
        esi_fetch(
            esi_path="Universe.get_universe_categories_category_id",
            args={"category_id": 65},
            logger_tag="dummy",
            esi_client=mock_client,
        )
        self.assertEqual(
            len(mock_client.Universe.get_universe_categories_category_id.mock_calls), 2
        )
        (
            args,
            kwargs,
        ) = mock_client.Universe.get_universe_categories_category_id.call_args
        self.assertEqual(kwargs, {"category_id": 65})

    @patch(MODULE_PATH + "._esi_client")
    def test_can_fetch_object_with_token(self, mock_esi_client):
        mock_token = Mock()
        mock_token.access_token = "my_access_token"
        esi_fetch(
            esi_path="Universe.get_universe_categories_category_id",
            args={"category_id": 65},
            logger_tag="dummy",
            token=mock_token,
        )
        self.assertEqual(
            len(
                mock_esi_client.return_value.Universe.get_universe_categories_category_id.mock_calls
            ),
            2,
        )
        (
            args,
            kwargs,
        ) = (
            mock_esi_client.return_value.Universe.get_universe_categories_category_id.call_args
        )
        self.assertEqual(kwargs, {"category_id": 65, "token": "my_access_token"})

    # @patch(MODULE_PATH + "._esi_client")
    def test_can_fetch_object_from_esi_wo_args(self):
        # mock_esi_client.side_effect = esi_mock_client
        mock_client = esi_mock_client()
        solar_systems = esi_fetch(
            esi_path="Universe.get_universe_systems",
            logger_tag="dummy",
            esi_client=mock_client,
        )
        expected = [30002506, 31000005, 30002537, 30000474, 30000476]
        self.assertSetEqual(set(solar_systems), set(expected))

    @patch(MODULE_PATH + "._esi_client")
    def test_uses_timeout_by_default(self, mock_esi_client):
        # fmt: off
        esi_fetch(esi_path="Universe.get_universe_systems", logger_tag="dummy")
        args, kwargs = \
            mock_esi_client.return_value.Universe.get_universe_systems.return_value\
            .result.call_args
        self.assertEqual(kwargs['timeout'], (5, 30))
        # fmt: on

    @patch(MODULE_PATH + ".STRUCTURES_ESI_TIMEOUT_ENABLED", False)
    @patch(MODULE_PATH + "._esi_client")
    def test_can_disable_timeout(self, mock_esi_client):
        # fmt: off
        esi_fetch(esi_path="Universe.get_universe_systems", logger_tag="dummy")
        args, kwargs = \
            mock_esi_client.return_value.Universe.get_universe_systems.return_value\
            .result.call_args
        self.assertNotIn("timeout", kwargs)
        # fmt: on

    @patch(MODULE_PATH + "._esi_client")
    def test_raises_exception_on_invalid_esi_path(self, mock_esi_client):
        with self.assertRaises(ValueError):
            esi_fetch("invalid", {"group_id": 65})

    @patch(MODULE_PATH + "._esi_client", spec_set=True)
    def test_raises_exception_on_wrong_esi_category(self, mock_esi_client):
        my_client = Mock(spec="Universe.get_universe_categories_category_id")
        mock_esi_client.return_value = my_client
        with self.assertRaises(ValueError):
            esi_fetch("invalid.get_universe_groups_group_id", {"group_id": 65})

    @patch(MODULE_PATH + "._esi_client", spec_set=True)
    def test_raises_exception_on_wrong_esi_method(self, mock_esi_client):
        my_client = Mock(spec="Universe.get_universe_categories_category_id")
        mock_esi_client.return_value = my_client
        with self.assertRaises(ValueError):
            esi_fetch("Universe.invalid", {"group_id": 65})

    @patch(MODULE_PATH + ".ESI_RETRY_SLEEP_SECS", 0)
    @patch(MODULE_PATH + "._esi_client")
    def test_can_retry_on_exceptions(self, mock_esi_client):
        MyException = RuntimeError

        def my_side_effect(**kwargs):
            """special mock client for testing retry ability"""
            nonlocal retry_counter, max_retries

            if retry_counter < max_retries:
                retry_counter += 1
                raise MyException(
                    response=Mock(**{"text": "test"}),
                    message="retry_counter=%d" % retry_counter,
                )
            else:
                return esi_get_universe_categories_category_id(category_id=65).result()

        mock_esi_client.return_value.Universe.get_universe_categories_category_id.return_value.result.side_effect = (
            my_side_effect
        )

        # can retry 3 times and then proceed normally on 502s
        MyException = HTTPBadGateway
        retry_counter = 0
        max_retries = 3
        response_object = esi_fetch(
            "Universe.get_universe_categories_category_id", {"category_id": 65}
        )
        self.assertEqual(response_object["id"], 65)
        self.assertEqual(response_object["name"], "Structure")
        self.assertEqual(retry_counter, 3)

        # will abort on the 4th retry and pass on exception if needed
        retry_counter = 0
        max_retries = 4
        with self.assertRaises(MyException):
            response_object = esi_fetch(
                "Universe.get_universe_categories_category_id",
                {"category_id": 65},
                Mock(),
            )
        self.assertEqual(retry_counter, 4)

        # will retry on 503s
        MyException = HTTPServiceUnavailable
        retry_counter = 0
        max_retries = 3
        response_object = esi_fetch(
            "Universe.get_universe_categories_category_id", {"category_id": 65}
        )
        self.assertEqual(response_object["id"], 65)
        self.assertEqual(response_object["name"], "Structure")
        self.assertEqual(retry_counter, 3)

        # will retry on 504s
        MyException = HTTPGatewayTimeout
        retry_counter = 0
        max_retries = 3
        response_object = esi_fetch(
            "Universe.get_universe_categories_category_id", {"category_id": 65}
        )
        self.assertEqual(response_object["id"], 65)
        self.assertEqual(response_object["name"], "Structure")
        self.assertEqual(retry_counter, 3)

        # will not retry on other HTTP exceptions
        MyException = HTTPForbidden
        retry_counter = 0
        max_retries = 3
        with self.assertRaises(MyException):
            response_object = esi_fetch(
                "Universe.get_universe_categories_category_id",
                {"category_id": 65},
                Mock(),
            )
        self.assertEqual(retry_counter, 1)

    def test_can_fetch_multiple_pages(self):
        mock_client = esi_mock_client()

        structures = esi_fetch(
            "Corporation.get_corporations_corporation_id_structures",
            args={"corporation_id": 2001},
            esi_client=mock_client,
            has_pages=True,
        )

        # has all structures
        structure_ids = {x["structure_id"] for x in structures}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

        # has services
        service_names = list()
        for obj in structures:
            if obj["structure_id"] == 1000000000001:
                service_names = {x["name"] for x in obj["services"]}
        expected = {"Clone Bay", "Market Hub"}
        self.assertEqual(service_names, expected)

    def test_can_fetch_multiple_pages_2(self):
        """fetching pages from django-esi 2.0 API"""
        mock_client = esi_mock_client(version=2.0)

        structures = esi_fetch(
            "Corporation.get_corporations_corporation_id_structures",
            args={"corporation_id": 2001},
            esi_client=mock_client,
            has_pages=True,
        )

        # has all structures
        structure_ids = {x["structure_id"] for x in structures}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

        # has services
        service_names = list()
        for obj in structures:
            if obj["structure_id"] == 1000000000001:
                service_names = {x["name"] for x in obj["services"]}
        expected = {"Clone Bay", "Market Hub"}
        self.assertEqual(service_names, expected)

    def test_can_fetch_multiple_pages_and_languages(self):
        mock_client = esi_mock_client()

        structures_list = esi_fetch_with_localization(
            "Corporation.get_corporations_corporation_id_structures",
            args={"corporation_id": 2001},
            esi_client=mock_client,
            has_pages=True,
            languages=EsiNameLocalization.ESI_LANGUAGES,
            logger_tag="dummy",
        )

        for language, structures in structures_list.items():
            # has all structures
            structure_ids = {x["structure_id"] for x in structures}
            expected = {1000000000001, 1000000000002, 1000000000003}
            self.assertSetEqual(structure_ids, expected)

            # has services in all languages
            service_names = list()
            for obj in structures:
                if obj["structure_id"] == 1000000000001:
                    service_names = {x["name"] for x in obj["services"]}
            if language == "en-us":
                expected = {"Clone Bay", "Market Hub"}
            else:
                expected = {"Clone Bay_" + language, "Market Hub_" + language}
            self.assertEqual(service_names, expected)
