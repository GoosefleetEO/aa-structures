import datetime as dt
from unittest.mock import patch

from bravado.exception import HTTPBadGateway, HTTPInternalServerError
from pytz import utc

from django.test import override_settings
from django.utils.timezone import now
from esi.models import Token

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.esi_testing import EsiClientStub, EsiEndpoint
from app_utils.testing import (
    BravadoResponseStub,
    NoSocketsTestCase,
    create_user_from_evecharacter,
    queryset_pks,
)

from ...models import (
    JumpFuelAlertConfig,
    Notification,
    NotificationType,
    Owner,
    StructureItem,
    Webhook,
)
from ..testdata.factories import (
    create_owner_from_user,
    create_starbase,
    create_structure_item,
    create_upwell_structure,
    create_webhook,
)
from ..testdata.factories_2 import (
    EveEntityCorporationFactory,
    OwnerFactory,
    datetime_to_esi,
)
from ..testdata.helpers import (
    create_structures,
    load_entities,
    load_notification_entities,
    set_owner_character,
)
from ..testdata.load_eveuniverse import load_eveuniverse

OWNERS_PATH = "structures.models.owners"
NOTIFICATIONS_PATH = "structures.models.notifications"


@patch(OWNERS_PATH + ".esi")
class TestFetchNotificationsEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        cls.user, _ = create_user_from_evecharacter(
            1001,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        Webhook.objects.all().delete()
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_notifications",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "notification_id": 1000000505,
                            "type": "StructureLostShields",
                            "sender_id": 2901,
                            "sender_type": "corporation",
                            "timestamp": "2019-10-04 14:52:00",
                            "text": "solarsystemID: 30002537\nstructureID: &id001 1000000000001\nstructureShowInfoData:\n- showinfo\n- 35832\n- *id001\nstructureTypeID: 35832\ntimeLeft: 1727805401093\ntimestamp: 132148470780000000\nvulnerableTime: 9000000000\n",
                        },
                    ]
                },
            )
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(endpoints)

    @patch(OWNERS_PATH + ".notify", spec=True)
    @patch(OWNERS_PATH + ".now", spec=True)
    def test_should_inform_user_about_successful_update(
        self, mock_now, mock_notify, mock_esi
    ):
        # given
        mock_esi.client = self.esi_client_stub
        mock_now.return_value = dt.datetime(2019, 8, 16, 14, 15, tzinfo=utc)
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000001)
        # when
        owner.fetch_notifications_esi(self.user)
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_notification_sync_fresh)
        self.assertTrue(mock_notify.called)

    def test_should_create_notifications(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000001)
        # when
        owner.fetch_notifications_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_notification_sync_fresh)
        # should only contain the right notifications
        notif_ids_current = set(
            Notification.objects.values_list("notification_id", flat=True)
        )
        self.assertSetEqual(notif_ids_current, {1000000505})

    @patch(OWNERS_PATH + ".now")
    def test_should_set_moon_for_structure_if_missing(self, mock_now, mock_esi_client):
        # given
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_notifications",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "notification_id": 1000000404,
                            "type": "MoonminingExtractionStarted",
                            "sender_id": 2901,
                            "sender_type": "corporation",
                            "timestamp": "2019-11-13 23:33:00",
                            "text": 'autoTime: 132186924601059151\nmoonID: 40161465\noreVolumeByType:\n  46300: 1288475.124715103\n  46301: 544691.7637724016\n  46302: 526825.4047522942\n  46303: 528996.6386983792\nreadyTime: 132186816601059151\nsolarSystemID: 30002537\nstartedBy: 1001\nstartedByLink: <a href="showinfo:1383//1001">Bruce Wayne</a>\nstructureID: 1000000000002\nstructureLink: <a href="showinfo:35835//1000000000002">Dummy</a>\nstructureName: Dummy\nstructureTypeID: 35835\n',
                            "is_read": False,
                        },
                    ]
                },
            )
        ]
        mock_esi_client.client = EsiClientStub.create_from_endpoints(endpoints)
        mock_now.return_value = dt.datetime(2019, 11, 13, 23, 50, 0, tzinfo=utc)
        owner = create_owner_from_user(self.user)
        structure = create_upwell_structure(
            owner=owner, id=1000000000002, eve_type_id=35835
        )
        # when
        owner.fetch_notifications_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_notification_sync_fresh)
        structure.refresh_from_db()
        self.assertEqual(structure.eve_moon_id, 40161465)

    def test_report_error_when_esi_returns_error_during_sync(self, mock_esi):
        def my_callback(*args, **kwargs):
            raise HTTPBadGateway(
                BravadoResponseStub(status_code=502, reason="Test Exception")
            )

        # given
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_notifications",
                "character_id",
                needs_token=True,
                data=[],
                side_effect=my_callback,
            )
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000001)
        # when
        with self.assertRaises(HTTPBadGateway):
            owner.fetch_notifications_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_notification_sync_fresh)


@patch(OWNERS_PATH + ".esi")
class TestFetchNotificationsEsi2(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_create_notifications_from_scratch(self, mock_esi):
        # given
        owner = OwnerFactory()
        sender = EveEntityCorporationFactory()
        eve_character = owner.characters.first().character_ownership.character
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_notifications",
                "character_id",
                needs_token=True,
                data={
                    str(eve_character.character_id): [
                        {
                            "notification_id": 42,
                            "is_read": False,
                            "sender_id": sender.id,
                            "sender_type": "corporation",
                            "text": "{}\n",
                            "timestamp": datetime_to_esi(now()),
                            "type": "CorpBecameWarEligible",
                        }
                    ]
                },
            )
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when
        owner.fetch_notifications_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_notification_sync_fresh)
        self.assertEqual(owner.notification_set.count(), 1)
        obj = owner.notification_set.first()
        self.assertEqual(
            obj.notif_type, NotificationType.WAR_CORPORATION_BECAME_ELIGIBLE
        )

    def test_should_handle_other_sender_correctly(self, mock_esi):
        # given
        owner = OwnerFactory()
        eve_character = owner.characters.first().character_ownership.character
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_notifications",
                "character_id",
                needs_token=True,
                data={
                    str(eve_character.character_id): [
                        {
                            "notification_id": 42,
                            "is_read": False,
                            "sender_id": 1,
                            "sender_type": "other",
                            "text": "{}\n",
                            "timestamp": datetime_to_esi(now()),
                            "type": "CorpBecameWarEligible",
                        }
                    ]
                },
            )
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when
        owner.fetch_notifications_esi()
        # then
        obj = owner.notification_set.get(notification_id=42)
        self.assertIsNone(obj.sender)


@override_settings(DEBUG=True)
@patch(NOTIFICATIONS_PATH + ".STRUCTURES_REPORT_NPC_ATTACKS", True)
@patch(NOTIFICATIONS_PATH + ".Webhook.send_message", spec=True)
class TestSendNewNotifications1(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.owner.is_alliance_main = True
        cls.owner.save()
        load_notification_entities(cls.owner)
        my_webhook = create_webhook(notification_types=NotificationType.values)
        cls.owner.webhooks.add(my_webhook)

    # TODO: Temporarily disabled
    # @patch(
    #     NOTIFICATIONS_PATH + ".STRUCTURES_NOTIFICATION_DISABLE_ESI_FUEL_ALERTS", False
    # )
    def test_should_send_all_notifications(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        # when
        self.owner.send_new_notifications()
        # then
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_forwarding_sync_fresh)
        notifications_processed = {
            int(args[1]["embeds"][0].footer.text[-10:])
            for args in mock_send_message.call_args_list
        }
        notifications_expected = set(
            self.owner.notification_set.filter(
                notif_type__in=NotificationType.values
            ).values_list("notification_id", flat=True)
        )
        self.assertSetEqual(notifications_processed, notifications_expected)

    # TODO: temporary disabled
    # @patch(
    #     NOTIFICATIONS_PATH + ".STRUCTURES_NOTIFICATION_DISABLE_ESI_FUEL_ALERTS", True
    # )
    # def test_should_send_all_notifications_except_fuel_alerts(self, mock_send_message):
    #     # given
    #     mock_send_message.return_value = True
    #     self.user = AuthUtils.add_permission_to_user_by_name(
    #         "structures.add_structure_owner", self.user
    #     )
    #     # when
    #     self.owner.send_new_notifications()
    #     # then
    #     self.owner.refresh_from_db()
    #     self.assertTrue(self.owner.is_forwarding_sync_fresh)
    #     notifications_processed = {
    #         int(args[1]["embeds"][0].footer.text[-10:])
    #         for args in mock_send_message.call_args_list
    #     }
    #     notif_types = set(NotificationType.values)
    #     notif_types.discard(NotificationType.STRUCTURE_FUEL_ALERT)
    #     notif_types.discard(NotificationType.TOWER_RESOURCE_ALERT_MSG)
    #     notifications_expected = set(
    #         self.owner.notifications.filter(notif_type__in=notif_types).values_list(
    #             "notification_id", flat=True
    #         )
    #     )
    #     self.assertSetEqual(notifications_processed, notifications_expected)

    def test_should_send_all_notifications_corp(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        user, owner = set_owner_character(character_id=1011)
        load_notification_entities(owner)
        owner.is_alliance_main = True
        owner.save()
        user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", user
        )
        # when
        owner.send_new_notifications()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_forwarding_sync_fresh)
        notifications_processed = {
            int(args[1]["embeds"][0].footer.text[-10:])
            for args in mock_send_message.call_args_list
        }
        notifications_expected = set(
            owner.notification_set.filter(
                notif_type__in=NotificationType.values
            ).values_list("notification_id", flat=True)
        )
        self.assertSetEqual(notifications_processed, notifications_expected)

    def test_should_only_send_selected_notification_types(self, mock_send_message):
        # given
        mock_send_message.return_value = 1
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        selected_notif_types = [
            NotificationType.ORBITAL_ATTACKED,
            NotificationType.STRUCTURE_DESTROYED,
        ]
        webhook = create_webhook(notification_types=selected_notif_types)
        self.owner.webhooks.clear()
        self.owner.webhooks.add(webhook)
        # when
        self.owner.send_new_notifications()
        # then
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_forwarding_sync_fresh)
        notifications_processed = {
            int(args[1]["embeds"][0].footer.text[-10:])
            for args in mock_send_message.call_args_list
        }
        notifications_expected = set(
            Notification.objects.filter(
                notif_type__in=selected_notif_types
            ).values_list("notification_id", flat=True)
        )
        self.assertSetEqual(notifications_processed, notifications_expected)


class TestSendNewNotifications2(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        user, _ = create_user_from_evecharacter(
            1001, permissions=["structures.add_structure_owner"]
        )
        cls.owner = create_owner_from_user(user=user, is_alliance_main=True)
        Webhook.objects.all().delete()
        load_notification_entities(cls.owner)

    @patch(OWNERS_PATH + ".Notification.send_to_configured_webhooks", autospec=True)
    def test_should_send_notifications_to_multiple_webhooks_but_same_owner(
        self, mock_send_to_configured_webhooks
    ):
        # given
        webhook_1 = create_webhook(
            notification_types=[
                NotificationType.ORBITAL_ATTACKED,
                NotificationType.ORBITAL_REINFORCED,
            ],
        )
        webhook_2 = create_webhook(
            notification_types=[
                NotificationType.STRUCTURE_DESTROYED,
                NotificationType.STRUCTURE_FUEL_ALERT,
            ],
        )
        self.owner.webhooks.add(webhook_1)
        self.owner.webhooks.add(webhook_2)
        # when
        self.owner.send_new_notifications()
        # then
        self.owner.refresh_from_db()
        notif_types_called = {
            obj[0][0].notif_type
            for obj in mock_send_to_configured_webhooks.call_args_list
        }
        self.assertTrue(self.owner.is_forwarding_sync_fresh)
        self.assertSetEqual(
            notif_types_called,
            {
                NotificationType.STRUCTURE_DESTROYED,
                NotificationType.STRUCTURE_FUEL_ALERT,
                NotificationType.ORBITAL_ATTACKED,
                NotificationType.ORBITAL_REINFORCED,
            },
        )

    # @patch(OWNERS_PATH + ".Token", spec=True)
    # @patch("structures.helpers.esi_fetch._esi_client")
    # @patch(
    #     NOTIFICATIONS_PATH + ".Notification.send_to_webhook", autospec=True
    # )
    # def test_can_send_notifications_to_multiple_owners(
    #     self, mock_send_to_webhook, mock_esi_client_factory, mock_token
    # ):
    #     mock_send_to_webhook.side_effect = self.my_send_to_webhook_success
    #     AuthUtils.add_permission_to_user_by_name(
    #         "structures.add_structure_owner", self.user
    #     )
    #     notification_groups_1 = ",".join(
    #         [str(x) for x in sorted([NotificationGroup.CUSTOMS_OFFICE])]
    #     )
    #     wh_structures = create_webhook(
    #         name="Structures",
    #         url="dummy-url-1",
    #         notification_types=notification_groups_1,
    #         is_active=True,
    #     )
    #     notification_groups_2 = ",".join(
    #         [str(x) for x in sorted([NotificationGroup.STARBASE])]
    #     )
    #     wh_mining = create_webhook(
    #         name="Mining",
    #         url="dummy-url-2",
    #         notification_types=notification_groups_2,
    #         is_default=True,
    #         is_active=True,
    #     )

    #     self.owner.webhooks.clear()
    #     self.owner.webhooks.add(wh_structures)
    #     self.owner.webhooks.add(wh_mining)

    #     owner2 = Owner.objects.get(corporation__corporation_id=2002)
    #     owner2.webhooks.add(wh_structures)
    #     owner2.webhooks.add(wh_mining)

    #     # move most mining notification to 2nd owner
    #     notifications = Notification.objects.filter(
    #         notification_id__in=[1000000401, 1000000403, 1000000404, 1000000405]
    #     )
    #     for x in notifications:
    #         x.owner = owner2
    #         x.save()

    #     # send notifications for 1st owner only
    #     self.assertTrue(self.owner.send_new_notifications())
    #     results = {wh_mining.pk: set(), wh_structures.pk: set()}
    #     for x in mock_send_to_webhook.call_args_list:
    #         first = x[0]
    #         notification = first[0]
    #         hook = first[1]
    #         results[hook.pk].add(notification.notification_id)

    #     # structure notifications should have been sent
    #     self.assertSetEqual(
    #         results[wh_structures.pk],
    #         {1000000402, 1000000502, 1000000504, 1000000505, 1000000509, 1000010509},
    #     )
    #     # but mining notifications should NOT have been sent
    #     self.assertSetEqual(results[wh_mining.pk], {1000000402})


@patch(OWNERS_PATH + ".esi")
class TestOwnerUpdateAssetEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        cls.user, _ = create_user_from_evecharacter(
            1001,
            permissions=["structures.basic_access", "structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        Webhook.objects.all().delete()
        endpoints = [
            EsiEndpoint(
                "Assets",
                "get_corporations_corporation_id_assets",
                "corporation_id",
                needs_token=True,
                data={
                    "2001": [
                        {
                            "is_singleton": False,
                            "item_id": 1300000001001,
                            "location_flag": "QuantumCoreRoom",
                            "location_id": 1000000000001,
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": 56201,
                        },
                        {
                            "is_singleton": True,
                            "item_id": 1300000001002,
                            "location_flag": "ServiceSlot0",
                            "location_id": 1000000000001,
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": 35894,
                        },
                        {
                            "is_singleton": True,
                            "item_id": 1300000002001,
                            "location_flag": "ServiceSlot0",
                            "location_id": 1000000000002,
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": 35894,
                        },
                        {
                            "is_singleton": True,
                            "item_id": 1500000000001,
                            "location_flag": "AutoFit",
                            "location_id": 30002537,  # Amamake,
                            "location_type": "solar_system",
                            "quantity": 1,
                            "type_id": 16213,  # control tower
                        },
                        {
                            "is_singleton": True,
                            "item_id": 1500000000002,
                            "location_flag": "AutoFit",
                            "location_id": 30002537,  # Amamake,
                            "location_type": "solar_system",
                            "quantity": 1,
                            "type_id": 32226,
                        },
                    ],
                },
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_locations",
                "corporation_id",
                needs_token=True,
                data={
                    "2001": [
                        {
                            "item_id": 1500000000002,
                            "position": {"x": 0.1, "y": 0, "z": 0},
                        }
                    ]
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(endpoints)

    def test_should_update_upwell_items_for_owner(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000001)
        create_upwell_structure(owner=owner, id=1000000000002)
        # when
        owner.update_asset_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_assets_sync_fresh)
        self.assertSetEqual(
            queryset_pks(StructureItem.objects.all()),
            {1300000001001, 1300000001002, 1300000002001},
        )
        obj = owner.structures.get(pk=1000000000001).items.get(pk=1300000001001)
        self.assertEqual(obj.eve_type_id, 56201)
        self.assertEqual(
            obj.location_flag, StructureItem.LocationFlag.QUANTUM_CORE_ROOM
        )
        self.assertEqual(obj.quantity, 1)
        self.assertFalse(obj.is_singleton)

        obj = owner.structures.get(pk=1000000000001).items.get(pk=1300000001002)
        self.assertEqual(obj.eve_type_id, 35894)
        self.assertEqual(obj.location_flag, "ServiceSlot0")
        self.assertEqual(obj.quantity, 1)
        self.assertTrue(obj.is_singleton)

        structure = owner.structures.get(id=1000000000001)
        self.assertTrue(structure.has_fitting)
        self.assertTrue(structure.has_core)

        structure = owner.structures.get(id=1000000000002)
        self.assertTrue(structure.has_fitting)
        self.assertFalse(structure.has_core)

    @patch(OWNERS_PATH + ".notify", spec=True)
    def test_should_inform_user_about_successful_update(self, mock_notify, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000001)
        # when
        owner.update_asset_esi(user=self.user)
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_assets_sync_fresh)
        self.assertTrue(mock_notify.called)

    def test_should_raise_exception_if_esi_has_error(self, mock_esi):
        def my_callback(**kwargs):
            raise HTTPInternalServerError(
                BravadoResponseStub(status_code=500, reason="Test")
            )

        # given
        endpoints = [
            EsiEndpoint(
                "Assets",
                "get_corporations_corporation_id_assets",
                "corporation_id",
                needs_token=True,
                side_effect=my_callback,
            )
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000001)
        # when
        with self.assertRaises(HTTPInternalServerError):
            owner.update_asset_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_assets_sync_fresh)

    def test_should_remove_assets_that_no_longer_exist_for_existing_structure(
        self, mock_esi
    ):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        structure = create_upwell_structure(owner=owner, id=1000000000001)
        item = create_structure_item(structure=structure)
        # when
        owner.update_asset_esi()
        # then
        self.assertFalse(structure.items.filter(pk=item.pk).exists())

    def test_should_remove_assets_that_no_longer_exist_for_removed_structure(
        self, mock_esi
    ):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000001)
        structure = create_upwell_structure(owner=owner, id=1000000000666)
        item = create_structure_item(structure=structure)
        # when
        owner.update_asset_esi()
        # then
        self.assertFalse(structure.items.filter(pk=item.pk).exists())

    def test_should_handle_asset_moved_to_another_structure(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        structure_1 = create_upwell_structure(owner=owner, id=1000000000001)
        structure_2 = create_upwell_structure(owner=owner, id=1000000000002)
        create_structure_item(
            structure=structure_2,
            id=1300000001002,
            eve_type_id=35894,
            location_flag="ServiceSlot0",
            is_singleton=True,
            quantity=1,
        )
        # when
        owner.update_asset_esi()
        # then
        self.assertSetEqual(queryset_pks(structure_2.items.all()), {1300000002001})
        self.assertSetEqual(
            queryset_pks(structure_1.items.all()), {1300000001001, 1300000001002}
        )

    def test_should_not_delete_assets_from_other_owners(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        user_2, _ = create_user_from_evecharacter(1102)
        owner_2 = create_owner_from_user(user_2)
        structure_2 = create_upwell_structure(owner=owner_2, id=1000000000004)
        create_structure_item(structure=structure_2, id=1300000003001)
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000001)
        create_upwell_structure(owner=owner, id=1000000000002)
        # when
        owner.update_asset_esi()
        # then
        self.assertSetEqual(
            queryset_pks(StructureItem.objects.all()),
            {1300000001001, 1300000001002, 1300000002001, 1300000003001},
        )

    def test_should_remove_outdated_jump_fuel_alerts(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Assets",
                "get_corporations_corporation_id_assets",
                "corporation_id",
                needs_token=True,
                data={
                    "2102": [
                        {
                            "is_singleton": False,
                            "item_id": 1300000003001,
                            "location_flag": "StructureFuel",
                            "location_id": 1000000000004,
                            "location_type": "item",
                            "quantity": 5000,
                            "type_id": 16273,
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_locations",
                "corporation_id",
                needs_token=True,
                data={"2102": []},
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        user, _ = create_user_from_evecharacter(
            1102,
            permissions=["structures.basic_access", "structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner = create_owner_from_user(user)
        structure = create_upwell_structure(owner=owner, id=1000000000004)
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure.jump_fuel_alerts.create(structure=structure, config=config)
        # when
        owner.update_asset_esi()
        # then
        self.assertEqual(structure.jump_fuel_alerts.count(), 0)

    # TODO: Add tests for error cases

    def test_should_update_starbase_items_for_owner(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        owner = create_owner_from_user(self.user)
        create_starbase(owner=owner, id=1500000000001)
        # when
        owner.update_asset_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_assets_sync_fresh)
        self.assertSetEqual(queryset_pks(StructureItem.objects.all()), {1500000000002})

    def test_should_update_upwell_items_for_owner_with_invalid_locations(
        self, mock_esi
    ):
        # given
        endpoints = [
            EsiEndpoint(
                "Assets",
                "get_corporations_corporation_id_assets",
                "corporation_id",
                needs_token=True,
                data={
                    "2102": [
                        {
                            "is_singleton": False,
                            "item_id": 1300000003001,
                            "location_flag": "StructureFuel",
                            "location_id": 1000000000004,
                            "location_type": "item",
                            "quantity": 5000,
                            "type_id": 16273,
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Assets",
                "post_corporations_corporation_id_assets_locations",
                "corporation_id",
                needs_token=True,
                http_error_code=404,
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        user, _ = create_user_from_evecharacter(
            1102,
            permissions=["structures.basic_access", "structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner = create_owner_from_user(user)
        structure = create_upwell_structure(owner=owner, id=1000000000004)
        # when
        owner.update_asset_esi()
        # then
        self.assertTrue(structure.items.filter(id=1300000003001).exists())


class TestOwnerToken(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities([EveCorporationInfo, EveCharacter])
        cls.character = EveCharacter.objects.get(character_id=1001)
        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)

    def test_should_return_str(self):
        # given
        _, character_ownership = create_user_from_evecharacter(
            1001, scopes=Owner.get_esi_scopes()
        )
        owner = Owner.objects.create(corporation=self.corporation)
        owner.add_character(character_ownership)
        # when
        result = str(owner.characters.first())
        # then
        self.assertEqual(result, "Wayne Technologies-Bruce Wayne")

    def test_should_return_valid_token(self):
        # given
        user, character_ownership = create_user_from_evecharacter(
            1001, scopes=Owner.get_esi_scopes()
        )
        owner = Owner.objects.create(corporation=self.corporation)
        owner.add_character(character_ownership)
        # when
        token = owner.characters.first().valid_token()
        # then
        self.assertIsInstance(token, Token)
        self.assertEqual(token.user, user)
        self.assertEqual(token.character_id, 1001)

    def test_should_return_none_if_no_valid_token_found(self):
        # given
        user, character_ownership = create_user_from_evecharacter(
            1001, scopes=Owner.get_esi_scopes()
        )
        owner = Owner.objects.create(corporation=self.corporation)
        owner.add_character(character_ownership)
        user.token_set.first().scopes.clear()
        # when
        token = owner.characters.first().valid_token()
        # then
        self.assertIsNone(token)


class TestOwnerUpdateIsUp(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.owner.is_alliance_main = True
        cls.owner.is_included_in_service_status = True
        cls.owner.save()

    @patch(OWNERS_PATH + ".STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True)
    @patch(OWNERS_PATH + ".Owner.are_all_syncs_ok", True)
    @patch(OWNERS_PATH + ".notify_admins")
    def test_should_do_nothing_when_still_up(self, mock_notify_admins):
        # given
        self.owner.is_up = True
        self.owner.save()
        # when
        result = self.owner.update_is_up()
        # then
        self.assertTrue(result)
        self.assertFalse(mock_notify_admins.called)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_up)
        self.assertTrue(self.owner.is_alliance_main)

    @patch(OWNERS_PATH + ".STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True)
    @patch(OWNERS_PATH + ".Owner.are_all_syncs_ok", False)
    @patch(OWNERS_PATH + ".notify_admins")
    def test_should_report_when_down(self, mock_notify_admins):
        # given
        self.owner.is_up = True
        self.owner.save()
        # when
        result = self.owner.update_is_up()
        # then
        self.assertFalse(result)
        self.assertTrue(mock_notify_admins.called)
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_up)
        self.assertTrue(self.owner.is_alliance_main)

    @patch(OWNERS_PATH + ".STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True)
    @patch(OWNERS_PATH + ".Owner.are_all_syncs_ok", False)
    @patch(OWNERS_PATH + ".notify_admins")
    def test_should_not_report_again_when_still_down(self, mock_notify_admins):
        # given
        self.owner.is_up = False
        self.owner.save()
        # when
        result = self.owner.update_is_up()
        # then
        self.assertFalse(result)
        self.assertFalse(mock_notify_admins.called)
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_up)
        self.assertTrue(self.owner.is_alliance_main)

    @patch(OWNERS_PATH + ".STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True)
    @patch(OWNERS_PATH + ".Owner.are_all_syncs_ok", True)
    @patch(OWNERS_PATH + ".notify_admins")
    def test_should_report_when_up_again(self, mock_notify_admins):
        # given
        self.owner.is_up = False
        self.owner.save()
        # when
        result = self.owner.update_is_up()
        # then
        self.assertTrue(result)
        self.assertTrue(mock_notify_admins.called)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_up)
        self.assertTrue(self.owner.is_alliance_main)

    @patch(OWNERS_PATH + ".STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True)
    @patch(OWNERS_PATH + ".Owner.are_all_syncs_ok", True)
    @patch(OWNERS_PATH + ".notify_admins")
    def test_should_report_when_up_for_the_first_time(self, mock_notify_admins):
        # given
        self.owner.is_up = None
        self.owner.save()
        # when
        result = self.owner.update_is_up()
        # then
        self.assertTrue(result)
        self.assertTrue(mock_notify_admins.called)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_up)
        self.assertTrue(self.owner.is_alliance_main)
