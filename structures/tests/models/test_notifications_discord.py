from app_utils.django import app_labels

if "discord" in app_labels():
    import re
    from unittest.mock import patch

    from requests.exceptions import HTTPError

    from django.contrib.auth.models import Group

    from app_utils.testing import NoSocketsTestCase

    from ...models import Notification
    from ..testdata.factories import create_webhook
    from ..testdata.helpers import (
        create_structures,
        load_entities,
        load_notification_entities,
        set_owner_character,
    )
    from ..testdata.load_eveuniverse import load_eveuniverse

    MODULE_PATH = "structures.models.notifications"

    @patch(MODULE_PATH + ".Notification._import_discord")
    @patch(MODULE_PATH + ".Webhook.send_message", spec=True)
    class TestGroupPings(NoSocketsTestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            load_eveuniverse()
            load_entities()
            cls.group_1 = Group.objects.create(name="Dummy Group 1")
            cls.group_2 = Group.objects.create(name="Dummy Group 2")
            create_structures(dont_load_entities=True)

        def setUp(self):
            _, self.owner = set_owner_character(character_id=1001)
            load_notification_entities(self.owner)

        @staticmethod
        def _my_group_to_role(group: Group) -> dict:
            if not isinstance(group, Group):
                raise TypeError("group must be of type Group")
            return {"id": group.pk, "name": group.name}

        def test_can_ping_via_webhook(self, mock_send_message, mock_import_discord):
            # given
            mock_send_message.return_value = 1
            mock_import_discord.return_value.objects.group_to_role.side_effect = (
                self._my_group_to_role
            )
            webhook = create_webhook()
            webhook.ping_groups.add(self.group_1)
            obj = Notification.objects.get(notification_id=1000000509)
            # when
            result = obj.send_to_webhook(webhook)
            # then
            self.assertTrue(result)
            self.assertTrue(mock_import_discord.called)
            _, kwargs = mock_send_message.call_args
            self.assertIn(f"<@&{self.group_1.pk}>", kwargs["content"])

        def test_can_ping_via_owner(self, mock_send_message, mock_import_discord):
            # given
            mock_send_message.return_value = 1
            mock_import_discord.return_value.objects.group_to_role.side_effect = (
                self._my_group_to_role
            )
            webhook = create_webhook()
            self.owner.ping_groups.add(self.group_2)
            obj = Notification.objects.get(notification_id=1000000509)
            # when
            result = obj.send_to_webhook(webhook)
            # then
            self.assertTrue(result)
            self.assertTrue(mock_import_discord.called)
            _, kwargs = mock_send_message.call_args
            self.assertIn(f"<@&{self.group_2.pk}>", kwargs["content"])

        def test_can_ping_both(self, mock_send_message, mock_import_discord):
            mock_send_message.return_value = 1
            mock_import_discord.return_value.objects.group_to_role.side_effect = (
                self._my_group_to_role
            )
            webhook = create_webhook()
            webhook.ping_groups.add(self.group_1)
            self.owner.ping_groups.add(self.group_2)
            obj = Notification.objects.get(notification_id=1000000509)
            # when
            result = obj.send_to_webhook(webhook)
            # then
            self.assertTrue(result)
            self.assertTrue(mock_import_discord.called)
            _, kwargs = mock_send_message.call_args
            self.assertIn(f"<@&{self.group_1.pk}>", kwargs["content"])
            self.assertIn(f"<@&{self.group_2.pk}>", kwargs["content"])

        def test_no_ping_if_not_set(self, mock_send_message, mock_import_discord):
            # given
            mock_send_message.return_value = 1
            mock_import_discord.return_value.objects.group_to_role.side_effect = (
                self._my_group_to_role
            )
            webhook = create_webhook()
            obj = Notification.objects.get(notification_id=1000000509)
            # when
            result = obj.send_to_webhook(webhook)
            # then
            self.assertTrue(result)
            self.assertFalse(mock_import_discord.called)
            _, kwargs = mock_send_message.call_args
            self.assertFalse(re.search(r"(<@&\d+>)", kwargs["content"]))

        def test_can_handle_http_error(self, mock_send_message, mock_import_discord):
            # given
            mock_send_message.return_value = 1
            mock_import_discord.return_value.objects.group_to_role.side_effect = (
                HTTPError
            )
            webhook = create_webhook()
            webhook.ping_groups.add(self.group_1)
            obj = Notification.objects.get(notification_id=1000000509)
            # when
            result = obj.send_to_webhook(webhook)
            # then
            self.assertTrue(result)
            self.assertTrue(mock_import_discord.called)
            _, kwargs = mock_send_message.call_args
            self.assertFalse(re.search(r"(<@&\d+>)", kwargs["content"]))
