import dhooks_lite

from django.test import TestCase, override_settings
from django.utils.timezone import now

from ...core import notification_embeds as ne
from ...models.notifications import EveEntity, Notification, NotificationType, Webhook
from ..testdata import (
    create_structures,
    load_notification_entities,
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
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # then
        self.assertIsInstance(
            notification_embed, ne.NotificationMoonminningExtractionFinished
        )
        self.assertEqual(str(notification_embed), "1000000403")
        self.assertEqual(
            repr(notification_embed),
            "NotificationMoonminningExtractionFinished(notification=Notification("
            "notification_id=1000000403, owner='Wayne Technologies', "
            "notif_type='MoonminingExtractionFinished'))",
        )

    def test_should_generate_embed_from_notification(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # when
        discord_embed = notification_embed.generate_embed()
        # then
        self.assertIsInstance(discord_embed, dhooks_lite.Embed)
        self.assertTrue(discord_embed.footer)

    def test_should_generate_embed_for_all_supported_notification_types(self):
        types_tested = set()
        for notification in Notification.objects.select_related(
            "owner", "sender"
        ).all():
            if notification.notif_type in NotificationType.values:
                # given
                notification_embed = ne.NotificationBaseEmbed.create(notification)
                # when
                discord_embed = notification_embed.generate_embed()
                # then
                self.assertIsInstance(discord_embed, dhooks_lite.Embed)
                types_tested.add(notification.notif_type)
        self.assertSetEqual(set(NotificationType.values), types_tested)

    def test_should_raise_exception_for_unsupported_notif_types(self):
        # given
        notification = Notification.objects.create(
            notification_id=666,
            owner=self.owner,
            sender=EveEntity.objects.get(id=2001),
            timestamp=now(),
            notif_type="XXXUnsupportedNotificationTypeXXX",
            last_updated=now(),
        )
        # when / then
        with self.assertRaises(NotImplementedError):
            ne.NotificationBaseEmbed.create(notification)

    def test_should_require_notification_for_init(self):
        with self.assertRaises(TypeError):
            ne.NotificationBaseEmbed(notification="dummy")

    def test_should_require_notification_for_factory(self):
        with self.assertRaises(TypeError):
            ne.NotificationBaseEmbed.create(notification="dummy")

    def test_should_not_allow_generating_embed_for_base_class(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        notification_embed = ne.NotificationBaseEmbed(notification=notification)
        # when
        with self.assertRaises(ValueError):
            notification_embed.generate_embed()

    def test_should_set_ping_everyone_for_color_danger(self):
        # given
        notification = Notification.objects.get(notification_id=1000000513)
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        notification_embed._color = Webhook.Color.DANGER
        # when
        notification_embed.generate_embed()
        # then
        self.assertEqual(notification_embed.ping_type, Webhook.PingType.EVERYONE)

    def test_should_set_ping_everyone_for_color_warning(self):
        # given
        notification = Notification.objects.get(notification_id=1000000513)
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        notification_embed._color = Webhook.Color.WARNING
        # when
        notification_embed.generate_embed()
        # then
        self.assertEqual(notification_embed.ping_type, Webhook.PingType.HERE)

    def test_should_not_set_ping_everyone_for_color_info(self):
        # given
        notification = Notification.objects.get(notification_id=1000000513)
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        notification_embed._color = Webhook.Color.INFO
        # when
        notification_embed.generate_embed()
        # then
        self.assertEqual(notification_embed.ping_type, Webhook.PingType.NONE)

    def test_should_not_set_ping_everyone_for_color_success(self):
        # given
        notification = Notification.objects.get(notification_id=1000000513)
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        notification_embed._color = Webhook.Color.SUCCESS
        # when
        notification_embed.generate_embed()
        # then
        self.assertEqual(notification_embed.ping_type, Webhook.PingType.NONE)

    @override_settings(DEBUG=True)
    def test_should_set_footer_in_developer_mode(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # when
        discord_embed = notification_embed.generate_embed()
        # then
        self.assertTrue(discord_embed.footer)
