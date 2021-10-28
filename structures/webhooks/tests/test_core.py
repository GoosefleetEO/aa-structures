import json
from random import randint
from unittest.mock import patch

import dhooks_lite

from django.test import TestCase

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.json import JSONDateTimeDecoder

from .. import core

MODULE_PATH = core.__package__ + ".core"


class Webhook(core.DiscordWebhookMixin):
    """Fake Webhook model used for testing

    TODO: Replace with Django model inheriting from WebhookBase
    """

    def __init__(self, name, url) -> None:
        self.pk = randint(1, 10000)
        self.name = name
        self.url = url
        super().__init__()


@patch(MODULE_PATH + ".sleep", lambda _: None)
class TestDiscordWebhookMixin(TestCase):
    def setUp(self) -> None:
        self.webhook = Webhook("Dummy 1", "dummy-1-url")
        self.webhook.clear_queue()

    def test_str(self):
        self.assertEqual(str(self.webhook), "Dummy 1")

    def test_repr(self):
        expected = "Webhook(pk=%s, name='Dummy 1')" % self.webhook.pk
        self.assertEqual(repr(self.webhook), expected)

    def test_can_size_and_clear_queue(self):
        # 0 when empty
        self.assertEqual(self.webhook.queue_size(), 0)

        # 3 after 3 messages added
        self.webhook.send_message("dummy")
        self.webhook.send_message("dummy")
        self.webhook.send_message("dummy")
        self.assertEqual(self.webhook.queue_size(), 3)

        # 0 after clearing queue
        self.webhook.clear_queue()
        self.assertEqual(self.webhook.queue_size(), 0)

    def test_can_send_simple_message(self):
        self.webhook.send_message(content="test-content")
        self.assertEqual(self.webhook.queue_size(), 1)
        message = json.loads(
            self.webhook._main_queue.dequeue(), cls=JSONDateTimeDecoder
        )
        self.assertDictEqual(message, {"content": "test-content"})

    def test_can_send_full_message(self):
        self.webhook.send_message(
            content="test-content",
            username="test-username",
            avatar_url="http://www.example.com/test",
            embeds=[dhooks_lite.Embed(description="test-description")],
        )
        self.assertEqual(self.webhook.queue_size(), 1)
        message = json.loads(
            self.webhook._main_queue.dequeue(), cls=JSONDateTimeDecoder
        )
        self.assertDictEqual(
            message,
            {
                "content": "test-content",
                "username": "test-username",
                "avatar_url": "http://www.example.com/test",
                "embeds": [dhooks_lite.Embed(description="test-description").asdict()],
            },
        )

    @patch(MODULE_PATH + ".dhooks_lite.Webhook.execute")
    def test_send_queued_messages_normal_simple(self, mock_execute):
        mock_execute.return_value = dhooks_lite.WebhookResponse(
            {}, status_code=200, content={"dummy": True}
        )

        self.webhook.send_message("dummy")
        self.webhook.send_message("dummy")

        result = self.webhook.send_queued_messages()
        self.assertEqual(result, 2)
        self.assertEqual(self.webhook.queue_size(), 0)
        self.assertEqual(self.webhook._error_queue.size(), 0)

    @patch(MODULE_PATH + ".dhooks_lite.Webhook.execute")
    def test_send_queued_messages_normal_complex(self, mock_execute):
        mock_execute.return_value = dhooks_lite.WebhookResponse(
            {}, status_code=200, content={"dummy": True}
        )

        self.webhook.send_message(
            content="dummy",
            username="test-username",
            avatar_url="test-avatar-url",
            embeds=[dhooks_lite.Embed(description="test-description")],
        )
        self.webhook.send_message("dummy")

        result = self.webhook.send_queued_messages()
        self.assertEqual(result, 2)
        self.assertEqual(self.webhook.queue_size(), 0)
        self.assertEqual(self.webhook._error_queue.size(), 0)

    @patch(MODULE_PATH + ".dhooks_lite.Webhook.execute")
    def test_send_queued_messages_errors_are_requeued(self, mock_execute):
        mock_execute.return_value = dhooks_lite.WebhookResponse(
            {}, status_code=404, content={"dummy": True}
        )

        self.webhook.send_message("dummy")
        self.webhook.send_message("dummy")

        result = self.webhook.send_queued_messages()
        self.assertEqual(result, 0)
        self.assertEqual(self.webhook.queue_size(), 2)
        self.assertEqual(self.webhook._error_queue.size(), 0)

    def test_can_create_discord_link(self):
        result = self.webhook.create_link("test-name", "test-url")
        self.assertEqual(result, "[test-name](test-url)")


@patch(MODULE_PATH + ".dhooks_lite.Webhook.execute")
class TestSendTestMessage(TestCase):
    def setUp(self) -> None:
        self.webhook = Webhook("Dummy 1", "dummy-1-url")
        self.user = AuthUtils.create_user("Bruce Wayne")

    def test_normal_no_user(self, mock_execute):
        mock_response = dhooks_lite.WebhookResponse(
            {}, status_code=200, content={"dummy": True}
        )
        mock_execute.return_value = mock_response

        result_1, result_2 = self.webhook.send_test_message()
        self.assertEqual(result_1, "(no info)")
        self.assertTrue(result_2)
        self.assertTrue(mock_execute.called)

    def test_normal_with_user(self, mock_execute):
        mock_response = dhooks_lite.WebhookResponse(
            {}, status_code=200, content={"dummy": True}
        )
        mock_execute.return_value = mock_response

        result_1, result_2 = self.webhook.send_test_message(self.user)
        self.assertEqual(result_1, "(no info)")
        self.assertTrue(result_2)
        self.assertTrue(mock_execute.called)

    def test_error_1(self, mock_execute):
        mock_response = dhooks_lite.WebhookResponse(
            {}, status_code=404, content={"dummy": True}
        )
        mock_execute.return_value = mock_response

        result_1, result_2 = self.webhook.send_test_message()
        self.assertEqual(result_1, "(no info)")
        self.assertFalse(result_2)
        self.assertTrue(mock_execute.called)

    def test_error_2(self, mock_execute):
        mock_execute.side_effect = OSError

        result_1, result_2 = self.webhook.send_test_message()
        self.assertEqual(result_1, "OSError")
        self.assertFalse(result_2)
        self.assertTrue(mock_execute.called)
