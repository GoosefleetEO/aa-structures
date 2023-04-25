import datetime as dt

import dhooks_lite

from django.test import TestCase, override_settings
from django.utils.timezone import now
from eveuniverse.models import EveEntity

from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from structures.core import notification_embeds as ne
from structures.core.notification_embeds import (
    NotificationBaseEmbed,
    NotificationTowerReinforcedExtra,
)
from structures.models.notifications import (
    Notification,
    NotificationType,
    Structure,
    Webhook,
)

from ..testdata.factories import (
    create_notification,
    create_owner_from_user,
    create_starbase,
)
from ..testdata.factories_2 import (
    EveEntityAllianceFactory,
    GeneratedNotificationFactory,
    NotificationFactory,
    OwnerFactory,
    WebhookFactory,
)
from ..testdata.helpers import (
    create_structures,
    load_entities,
    load_notification_entities,
    markdown_to_plain,
    set_owner_character,
)
from ..testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "structures.core.notification_embeds"


class TestBilType(TestCase):
    def test_should_create_from_valid_id(self):
        self.assertEqual(ne.BillType.to_enum(7), ne.BillType.INFRASTRUCTURE_HUB)

    def test_should_create_from_invalid_id(self):
        for bill_id in range(7):
            with self.subTest(bill_id=bill_id):
                self.assertEqual(ne.BillType.to_enum(bill_id), ne.BillType.UNKNOWN)


class TestNotificationEmbeds(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)

    def test_should_create_obj_from_notification(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        # when
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # then
        self.assertIsInstance(
            notification_embed, ne.NotificationMoonminningExtractionFinished
        )
        self.assertEqual(
            str(notification_embed), "1000000403:MoonminingExtractionFinished"
        )
        self.assertEqual(
            repr(notification_embed),
            "NotificationMoonminningExtractionFinished(notification=Notification("
            "notification_id=1000000403, owner='Wayne Technologies', "
            "notif_type='MoonminingExtractionFinished'))",
        )

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


class TestNotificationEmbedsGenerate(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)
        cls.webhook = WebhookFactory()
        cls.owner.webhooks.add(cls.webhook)

    def test_should_generate_embed_from_notification(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # when
        discord_embed = notification_embed.generate_embed()
        # then
        self.assertIsInstance(discord_embed, dhooks_lite.Embed)
        self.assertEqual(discord_embed.footer.text, "Eve Online")
        self.assertIn("eve_symbol_128.png", discord_embed.footer.icon_url)

    def test_should_generate_embed_from_notification_with_custom_color(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        notification._color_override = Webhook.Color.SUCCESS
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # when
        discord_embed = notification_embed.generate_embed()
        # then
        self.assertIsInstance(discord_embed, dhooks_lite.Embed)
        self.assertEqual(discord_embed.color, Webhook.Color.SUCCESS)

    def test_should_generate_embed_from_notification_without_custom_color(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # when
        discord_embed = notification_embed.generate_embed()
        # then
        self.assertIsInstance(discord_embed, dhooks_lite.Embed)
        self.assertNotEqual(discord_embed.color, Webhook.Color.SUCCESS)

    def test_should_generate_embed_from_notification_with_ping_type_override(self):
        # given
        notification = Notification.objects.get(notification_id=1000000403)
        notification._ping_type_override = Webhook.PingType.EVERYONE
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # when
        notification_embed.generate_embed()
        # then
        self.assertEqual(notification_embed.ping_type, Webhook.PingType.EVERYONE)

    def test_should_generate_embed_for_all_supported_esi_notification_types(self):
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
        self.assertSetEqual(NotificationType.esi_notifications, types_tested)

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

    def test_should_set_special_footer_for_generated_notifications(self):
        # given
        structure = Structure.objects.get(id=1000000000001)
        notification = Notification.create_from_structure(
            structure, notif_type=NotificationType.STRUCTURE_FUEL_ALERT
        )
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # when
        discord_embed = notification_embed.generate_embed()
        # then
        self.assertEqual(discord_embed.footer.text, "Structures")
        self.assertIn("structures_logo.png", discord_embed.footer.icon_url)


class TestNotificationEmbedsClasses(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        user, _ = create_user_from_evecharacter(
            1001, permissions=["structures.add_structure_owner"]
        )
        cls.owner = create_owner_from_user(user=user)
        cls.moon_id = 40161465
        cls.solar_system_id = 30002537
        cls.type_id = 16213

    def test_should_generate_embed_for_normal_tower_resource_alert(self):
        # given
        create_starbase(
            owner=self.owner,
            eve_moon_id=self.moon_id,
            eve_solar_system_id=self.solar_system_id,
            eve_type_id=self.type_id,
        )
        data = {
            "corpID": self.owner.corporation.corporation_id,
            "moonID": self.moon_id,
            "solarSystemID": self.solar_system_id,
            "typeID": self.type_id,
            "wants": [{"quantity": 120, "typeID": 4051}],
        }
        notification = create_notification(
            owner=self.owner,
            notif_type=NotificationType.TOWER_RESOURCE_ALERT_MSG,
            data=data,
        )
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # when
        discord_embed = notification_embed.generate_embed()
        # then
        description = markdown_to_plain(discord_embed.description)
        self.assertIn("is running out of fuel in 3 hours", description)

    def test_should_generate_embed_for_generated_tower_resource_alert(self):
        # given
        structure = create_starbase(
            owner=self.owner,
            eve_moon_id=self.moon_id,
            eve_solar_system_id=self.solar_system_id,
            eve_type_id=self.type_id,
            fuel_expires_at=now() + dt.timedelta(hours=2, seconds=20),
        )
        notification = Notification.create_from_structure(
            structure=structure, notif_type=NotificationType.TOWER_RESOURCE_ALERT_MSG
        )
        notification_embed = ne.NotificationBaseEmbed.create(notification)
        # when
        discord_embed = notification_embed.generate_embed()
        # then
        description = markdown_to_plain(discord_embed.description)
        self.assertIn("is running out of fuel in 2 hours", description)


class TestGeneratedNotification(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_create_tower_reinforced_embed(self):
        # given
        notif = GeneratedNotificationFactory()
        # when
        obj = NotificationBaseEmbed.create(notif)
        # then
        self.assertIsInstance(obj, NotificationTowerReinforcedExtra)

    def test_should_generate_embed(self):
        # given
        notif = GeneratedNotificationFactory()
        embed = NotificationBaseEmbed.create(notif)
        # when
        obj = embed.generate_embed()
        # then
        self.assertIsInstance(obj, dhooks_lite.Embed)
        starbase = notif.structures.first()
        self.assertIn(starbase.name, obj.description)


class TestEveNotificationEmbeds(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        cls.owner = OwnerFactory()

    def test_should_create_sov_embed(self):
        # given
        notif = NotificationFactory(
            owner=self.owner,
            sender=EveEntityAllianceFactory(),
            notif_type=NotificationType.SOV_ENTOSIS_CAPTURE_STARTED,
            text_from_dict={"solarSystemID": 30000474, "structureTypeID": 32226},
        )
        embed = NotificationBaseEmbed.create(notif)
        # when
        obj = embed.generate_embed()
        # then
        self.assertIsInstance(obj, dhooks_lite.Embed)

    def test_should_create_sov_embed_without_sender(self):
        # given
        notif = NotificationFactory(
            owner=self.owner,
            sender=None,
            notif_type=NotificationType.SOV_ENTOSIS_CAPTURE_STARTED,
            text_from_dict={"solarSystemID": 30000474, "structureTypeID": 32226},
        )
        embed = NotificationBaseEmbed.create(notif)
        # when
        obj = embed.generate_embed()
        # then
        self.assertIsInstance(obj, dhooks_lite.Embed)
