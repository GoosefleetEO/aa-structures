from unittest.mock import patch

import dhooks_lite
from django.test import TestCase

from ...core import notification_embeds as ne
from ...models.notifications import Notification, Webhook
from ..testdata import (
    load_notification_entities,
    create_structures,
    set_owner_character,
)

MODULE_PATH = "structures.core.notification_embeds"


class TestNotificationEmbeds(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)
        cls.webhook = Webhook.objects.create(
            name="Test", url="http://www.example.com/dummy/"
        )
        cls.owner.webhooks.add(cls.webhook)

    def test_should_create_obj_from_notification(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        # when
        notification_embed = ne.NotificationEmbed.create(notification)
        # then
        self.assertIsInstance(
            notification_embed, ne.NotificationMoonminningExtractionFinished
        )
        self.assertEqual(str(notification_embed), "1000000403")
        self.assertEqual(
            repr(notification_embed),
            "NotificationMoonminningExtractionFinished(notification=Notification("
            "notification_id=1000000403, owner='Wayne Technologies', "
            "notification_type='MoonminingExtractionFinished'))",
        )

    def test_should_generate_embed_from_notification(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        notification_embed = ne.NotificationEmbed.create(notification)
        # when
        discord_embed = notification_embed.generate_embed()
        # then
        self.assertIsInstance(discord_embed, dhooks_lite.Embed)
        self.assertFalse(discord_embed.footer)

    def test_should_generate_embed_for_all_notification_types(self):
        types_tested = set()
        for notification in Notification.objects.select_related(
            "owner", "sender"
        ).all():
            # given
            notification_embed = ne.NotificationEmbed.create(notification)
            # when
            discord_embed = notification_embed.generate_embed()
            # then
            self.assertIsInstance(discord_embed, dhooks_lite.Embed)
            types_tested.add(notification.notification_type)
        self.assertSetEqual(Notification.get_all_types(), types_tested)

    def test_should_require_notification_for_init(self):
        with self.assertRaises(TypeError):
            ne.NotificationEmbed(notification="dummy")

    def test_should_require_notification_for_factory(self):
        with self.assertRaises(TypeError):
            ne.NotificationEmbed.create(notification="dummy")

    def test_should_not_allow_generating_embed_for_base_class(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        notification_embed = ne.NotificationEmbed(notification=notification)
        # when
        with self.assertRaises(RuntimeError):
            notification_embed.generate_embed()

    def test_should_set_ping_everyone_for_color_danger(self):
        # given
        notification = Notification.objects.get(notification_id=1000000513)
        notification_embed = ne.NotificationEmbed.create(notification)
        notification_embed._color = notification_embed.COLOR_DANGER
        # when
        notification_embed.generate_embed()
        # then
        self.assertEqual(notification_embed.ping_type, Webhook.PingType.EVERYONE)

    def test_should_set_ping_everyone_for_color_warning(self):
        # given
        notification = Notification.objects.get(notification_id=1000000513)
        notification_embed = ne.NotificationEmbed.create(notification)
        notification_embed._color = notification_embed.COLOR_WARNING
        # when
        notification_embed.generate_embed()
        # then
        self.assertEqual(notification_embed.ping_type, Webhook.PingType.HERE)

    def test_should_not_set_ping_everyone_for_color_info(self):
        # given
        notification = Notification.objects.get(notification_id=1000000513)
        notification_embed = ne.NotificationEmbed.create(notification)
        notification_embed._color = notification_embed.COLOR_INFO
        # when
        notification_embed.generate_embed()
        # then
        self.assertEqual(notification_embed.ping_type, Webhook.PingType.NONE)

    def test_should_not_set_ping_everyone_for_color_success(self):
        # given
        notification = Notification.objects.get(notification_id=1000000513)
        notification_embed = ne.NotificationEmbed.create(notification)
        notification_embed._color = notification_embed.COLOR_SUCCESS
        # when
        notification_embed.generate_embed()
        # then
        self.assertEqual(notification_embed.ping_type, Webhook.PingType.NONE)

    @patch(MODULE_PATH + ".STRUCTURES_DEVELOPER_MODE", True)
    def test_should_set_footer_in_developer_mode(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        notification_embed = ne.NotificationEmbed.create(notification)
        # when
        discord_embed = notification_embed.generate_embed()
        # then
        self.assertTrue(discord_embed.footer)
