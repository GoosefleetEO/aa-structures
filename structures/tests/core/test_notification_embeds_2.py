import dhooks_lite

from app_utils.testing import NoSocketsTestCase

from ...core.notification_embeds import (
    NotificationBaseEmbed,
    NotificationTowerReinforcedExtra,
)
from ...models import NotificationType
from ..testdata.factories_2 import (
    EveEntityAllianceFactory,
    GeneratedNotificationFactory,
    NotificationFactory,
    OwnerFactory,
)
from ..testdata.helpers import load_eveuniverse


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
