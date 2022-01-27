from unittest.mock import Mock, patch

from bravado.exception import HTTPBadGateway, HTTPInternalServerError

from django.test import override_settings
from esi.models import Token

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.django import app_labels
from app_utils.testing import (
    BravadoResponseStub,
    NoSocketsTestCase,
    create_user_from_evecharacter,
    queryset_pks,
)

from ...constants import EveTypeId
from ...models import (
    EveMoon,
    JumpFuelAlertConfig,
    Notification,
    Owner,
    Structure,
    StructureItem,
    Webhook,
)
from ...models.notifications import NotificationType
from .. import to_json
from ..testdata import (
    create_structures,
    entities_testdata,
    esi_mock_client,
    load_entities,
    load_notification_entities,
    set_owner_character,
)
from ..testdata.factories import create_owner_from_user, create_webhook

if "timerboard" in app_labels():
    from allianceauth.timerboard.models import Timer as AuthTimer

    has_auth_timers = True

else:
    has_auth_timers = False


MODULE_PATH = "structures.models.owners"
MODELS_NOTIFICATIONS = "structures.models.notifications"
MODULE_PATH_ESI_FETCH = "structures.helpers.esi_fetch"


class TestUpdateStructuresEsiWithLocalization(NoSocketsTestCase):
    def setUp(self):
        self.default_lang = "en-us"
        self.structures_w_lang = {
            "en-us": [
                {
                    "structure_id": 1001,
                    "services": [
                        {"name": "alpha", "state": "online"},
                        {"name": "bravo", "state": "online"},
                    ],
                },
                {
                    "structure_id": 1002,
                    "services": [{"name": "bravo", "state": "offline"}],
                },
            ],
            "ko": [
                {
                    "structure_id": 1001,
                    "services": [
                        {"name": "alpha_ko", "state": "online"},
                        {"name": "bravo_ko", "state": "online"},
                    ],
                },
                {
                    "structure_id": 1002,
                    "services": [{"name": "bravo_ko", "state": "offline"}],
                },
            ],
            "de": [
                {
                    "structure_id": 1001,
                    "services": [
                        {"name": "alpha_de", "state": "online"},
                        {"name": "bravo_de", "state": "online"},
                    ],
                },
                {
                    "structure_id": 1002,
                    "services": [{"name": "bravo_de", "state": "offline"}],
                },
            ],
        }

    def test_collect_services_with_localizations(self):
        structures_services = Owner._collect_services_with_localizations(
            self.structures_w_lang, self.default_lang
        )
        expected = {
            1001: {"de": ["alpha_de", "bravo_de"], "ko": ["alpha_ko", "bravo_ko"]},
            1002: {"de": ["bravo_de"], "ko": ["bravo_ko"]},
        }
        self.maxDiff = None
        self.assertEqual(to_json(structures_services), to_json(expected))

    def test_condense_services_localizations_into_structures(self):
        structures_services = {
            1001: {"de": ["alpha_de", "bravo_de"], "ko": ["alpha_ko", "bravo_ko"]},
            1002: {"de": ["bravo_de"], "ko": ["bravo_ko"]},
        }
        structures = Owner._condense_services_localizations_into_structures(
            self.structures_w_lang, self.default_lang, structures_services
        )
        excepted = [
            {
                "structure_id": 1001,
                "services": [
                    {
                        "name": "alpha",
                        "name_de": "alpha_de",
                        "name_ko": "alpha_ko",
                        "state": "online",
                    },
                    {
                        "name": "bravo",
                        "name_de": "bravo_de",
                        "name_ko": "bravo_ko",
                        "state": "online",
                    },
                ],
            },
            {
                "structure_id": 1002,
                "services": [
                    {
                        "name": "bravo",
                        "name_de": "bravo_de",
                        "name_ko": "bravo_ko",
                        "state": "offline",
                    }
                ],
            },
        ]
        self.maxDiff = None
        self.assertEqual(to_json(structures), to_json(excepted))

    def test_condense_services_localizations_into_structures_2(self):
        structures_services = {
            1001: {"de": ["alpha_de", "bravo_de"]},
            1002: {"de": ["bravo_de"]},
        }
        structures = Owner._condense_services_localizations_into_structures(
            self.structures_w_lang, self.default_lang, structures_services
        )
        excepted = [
            {
                "structure_id": 1001,
                "services": [
                    {"name": "alpha", "name_de": "alpha_de", "state": "online"},
                    {"name": "bravo", "name_de": "bravo_de", "state": "online"},
                ],
            },
            {
                "structure_id": 1002,
                "services": [
                    {"name": "bravo", "name_de": "bravo_de", "state": "offline"}
                ],
            },
        ]
        self.maxDiff = None
        self.assertEqual(to_json(structures), to_json(excepted))


@patch("structures.helpers.esi_fetch._esi_client")
class TestFetchNotificationsEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.owner.is_alliance_main = True
        cls.owner.save()

    @patch(MODELS_NOTIFICATIONS + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", False)
    @patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", True)
    def test_should_create_notifications_and_timers_from_scratch(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        # when
        if "structuretimers" in app_labels():
            from ..testdata.load_eveuniverse import load_eveuniverse

            load_eveuniverse()
            with patch(
                "structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False
            ), patch(
                "structuretimers.models._task_calc_timer_distances_for_all_staging_systems",
                lambda: Mock(),
            ):
                self.owner.fetch_notifications_esi()
        else:
            self.owner.fetch_notifications_esi()

        # then
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_notification_sync_fresh)
        # should only contain the right notifications
        notif_ids_current = set(
            Notification.objects.values_list("notification_id", flat=True)
        )
        notif_ids_testdata = {
            x["notification_id"] for x in entities_testdata["Notification"]
        }
        self.assertSetEqual(notif_ids_current, notif_ids_testdata)

        if has_auth_timers:
            # should have added timers
            self.assertEqual(AuthTimer.objects.count(), 4)

            # run sync again
            self.owner.fetch_notifications_esi()
            self.assertTrue(self.owner.is_notification_sync_fresh)

            # should not have more timers
            self.assertEqual(AuthTimer.objects.count(), 4)

    @patch(MODELS_NOTIFICATIONS + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", False)
    @patch(MODULE_PATH + ".notify", spec=True)
    @patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", True)
    def test_should_inform_user_about_successful_update(
        self, mock_notify, mock_esi_client
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        # when
        if "structuretimers" in app_labels():
            from ..testdata.load_eveuniverse import load_eveuniverse

            load_eveuniverse()
            with patch(
                "structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False
            ), patch(
                "structuretimers.models._task_calc_timer_distances_for_all_staging_systems",
                lambda: Mock(),
            ):
                self.owner.fetch_notifications_esi(user=self.user)
        else:
            self.owner.fetch_notifications_esi(user=self.user)

        # then
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_notification_sync_fresh)
        self.assertTrue(mock_notify.called)

    @patch(MODELS_NOTIFICATIONS + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", False)
    @patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", True)
    def test_should_create_new_notifications_only(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        load_notification_entities(self.owner)
        Notification.objects.get(notification_id=1000000803).delete()
        Notification.objects.all().update(created=None)
        # when
        if "structuretimers" in app_labels():
            from ..testdata.load_eveuniverse import load_eveuniverse

            load_eveuniverse()
            with patch(
                "structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False
            ), patch(
                "structuretimers.models._task_calc_timer_distances_for_all_staging_systems",
                lambda: Mock(),
            ):
                self.owner.fetch_notifications_esi()
        else:
            self.owner.fetch_notifications_esi()
        # then
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_notification_sync_fresh)
        # should only contain the right notifications
        notif_ids_current = set(
            Notification.objects.values_list("notification_id", flat=True)
        )
        notif_ids_testdata = {
            x["notification_id"] for x in entities_testdata["Notification"]
        }
        self.assertSetEqual(notif_ids_current, notif_ids_testdata)
        # should only have created one notification
        created_ids = set(
            Notification.objects.filter(created__isnull=False).values_list(
                "notification_id", flat=True
            )
        )
        self.assertSetEqual(created_ids, {1000000803})

    @patch(MODELS_NOTIFICATIONS + ".STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", False)
    @patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", False)
    def test_should_set_moon_for_structure_if_missing(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        load_notification_entities(self.owner)
        Notification.objects.get(notification_id=1000000803).delete()
        Notification.objects.all().update(created=None)
        # when
        if "structuretimers" in app_labels():
            from ..testdata.load_eveuniverse import load_eveuniverse

            load_eveuniverse()
            with patch(
                "structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False
            ), patch(
                "structuretimers.models._task_calc_timer_distances_for_all_staging_systems",
                lambda: Mock(),
            ):
                self.owner.fetch_notifications_esi()
        else:
            self.owner.fetch_notifications_esi()
        # then
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_notification_sync_fresh)
        structure = Structure.objects.get(id=1000000000002)
        self.assertEqual(structure.eve_moon, EveMoon.objects.get(id=40161465))

    @patch("structures.helpers.esi_fetch.ESI_RETRY_SLEEP_SECS", 0)
    @patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", False)
    def test_report_error_when_esi_returns_error_during_sync(self, mock_esi_client):
        # given
        def get_characters_character_id_notifications_error(*args, **kwargs):
            raise HTTPBadGateway(
                BravadoResponseStub(status_code=502, reason="Test Exception")
            )

        mock_esi_client.return_value.Character.get_characters_character_id_notifications.side_effect = (
            get_characters_character_id_notifications_error
        )
        AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        # when
        with self.assertRaises(HTTPBadGateway):
            self.owner.fetch_notifications_esi()
        # then
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_notification_sync_fresh)


@override_settings(DEBUG=True)
@patch(MODELS_NOTIFICATIONS + ".Webhook.send_message", spec=True)
class TestSendNewNotifications1(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.owner.is_alliance_main = True
        cls.owner.save()
        load_notification_entities(cls.owner)
        my_webhook = create_webhook(notification_types=NotificationType.values)
        cls.owner.webhooks.add(my_webhook)

    # TODO: Temporarily disabled
    # @patch(
    #     MODELS_NOTIFICATIONS + ".STRUCTURES_NOTIFICATION_DISABLE_ESI_FUEL_ALERTS", False
    # )
    def test_should_send_all_notifications(self, mock_send_message):
        # given
        mock_send_message.return_value = True
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
            self.owner.notifications.filter(
                notif_type__in=NotificationType.values
            ).values_list("notification_id", flat=True)
        )
        self.assertSetEqual(notifications_processed, notifications_expected)

    # TODO: temporary disabled
    # @patch(
    #     MODELS_NOTIFICATIONS + ".STRUCTURES_NOTIFICATION_DISABLE_ESI_FUEL_ALERTS", True
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
        mock_send_message.return_value = True
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
            owner.notifications.filter(
                notif_type__in=NotificationType.values
            ).values_list("notification_id", flat=True)
        )
        self.assertSetEqual(notifications_processed, notifications_expected)

    def test_should_only_send_selected_notification_types(self, mock_send_message):
        # given
        mock_send_message.return_value = True
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        webhook = create_webhook(
            notification_types=[
                NotificationType.ORBITAL_ATTACKED,
                NotificationType.STRUCTURE_DESTROYED,
            ]
        )
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
                notif_type__in=[
                    NotificationType.ORBITAL_ATTACKED,
                    NotificationType.STRUCTURE_DESTROYED,
                ]
            ).values_list("notification_id", flat=True)
        )
        self.assertSetEqual(notifications_processed, notifications_expected)


class TestSendNewNotifications2(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        user, _ = create_user_from_evecharacter(
            1001, permissions=["structures.add_structure_owner"]
        )
        cls.owner = create_owner_from_user(user=user, is_alliance_main=True)
        Webhook.objects.all().delete()
        load_notification_entities(cls.owner)

    @patch(MODULE_PATH + ".Notification.send_to_configured_webhooks", autospec=True)
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

    # @patch(MODULE_PATH + ".Token", spec=True)
    # @patch("structures.helpers.esi_fetch._esi_client")
    # @patch(
    #     MODELS_NOTIFICATIONS + ".Notification.send_to_webhook", autospec=True
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


@patch("structures.helpers.esi_fetch._esi_client")
@patch("structures.helpers.esi_fetch.sleep", lambda x: None)
class TestOwnerUpdateAssetEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", cls.user
        )

    def test_should_update_assets_for_owner(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.get(corporation__corporation_id=2001)
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

    @patch(MODULE_PATH + ".notify", spec=True)
    def test_should_inform_user_about_successful_update(
        self, mock_notify, mock_esi_client
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.get(corporation__corporation_id=2001)
        # when
        owner.update_asset_esi(user=self.user)
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_assets_sync_fresh)
        self.assertTrue(mock_notify.called)

    def test_should_raise_exception_if_esi_has_error(self, mock_esi_client):
        # given
        mock_esi_client.return_value.Assets.get_corporations_corporation_id_assets.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        owner = Owner.objects.get(corporation__corporation_id=2001)
        # when
        with self.assertRaises(HTTPInternalServerError):
            owner.update_asset_esi()
        # then
        owner.refresh_from_db()
        self.assertIsNone(owner.is_assets_sync_fresh)

    def test_should_remove_assets_that_no_longer_exist_for_existing_structure(
        self, mock_esi_client
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.get(corporation__corporation_id=2001)
        structure = Structure.objects.get(id=1000000000001)
        structure.items.create(
            id=42,
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag="Cargo",
            is_singleton=False,
            quantity=5000,
        )
        # when
        owner.update_asset_esi()
        # then
        self.assertFalse(structure.items.filter(id=42).exists())

    def test_should_remove_assets_that_no_longer_exist_for_removed_structure(
        self, mock_esi_client
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.get(corporation__corporation_id=2001)
        structure = Structure.objects.create(
            id=1000000000666,
            owner=owner,
            eve_type_id=EveTypeId.JUMP_GATE,
            name="Zombie",
            eve_solar_system_id=30000476,
        )
        structure.items.create(
            id=42,
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag="Cargo",
            is_singleton=False,
            quantity=5000,
        )
        # when
        owner.update_asset_esi()
        # then
        self.assertFalse(structure.items.filter(id=42).exists())

    def test_should_remove_outdated_jump_fuel_alerts(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        _, owner = set_owner_character(character_id=1011)
        structure = Structure.objects.get(id=1000000000004)
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure.jump_fuel_alerts.create(structure=structure, config=config)
        # when
        owner.update_asset_esi()
        # then
        self.assertEqual(structure.jump_fuel_alerts.count(), 0)

    def test_should_handle_asset_moved_to_another_structure(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.get(corporation__corporation_id=2001)
        structure_1 = Structure.objects.get(id=1000000000001)
        structure_2 = Structure.objects.get(id=1000000000002)
        structure_2.items.create(
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

    def test_should_not_delete_assets_from_other_owners(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1300000003001,
            eve_type_id=16273,
            location_flag="StructureFuel",
            is_singleton=False,
            quantity=5000,
        )
        owner_2001 = Owner.objects.get(corporation__corporation_id=2001)
        # when
        owner_2001.update_asset_esi()
        # then
        self.assertSetEqual(
            queryset_pks(StructureItem.objects.all()),
            {1300000001001, 1300000001002, 1300000002001, 1300000003001},
        )

    # TODO: Add tests for error cases


class TestOwnerToken(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.owner.is_alliance_main = True
        cls.owner.is_included_in_service_status = True
        cls.owner.save()

    @patch(MODULE_PATH + ".STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True)
    @patch(MODULE_PATH + ".Owner.are_all_syncs_ok", True)
    @patch(MODULE_PATH + ".notify_admins")
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

    @patch(MODULE_PATH + ".STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True)
    @patch(MODULE_PATH + ".Owner.are_all_syncs_ok", False)
    @patch(MODULE_PATH + ".notify_admins")
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

    @patch(MODULE_PATH + ".STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True)
    @patch(MODULE_PATH + ".Owner.are_all_syncs_ok", False)
    @patch(MODULE_PATH + ".notify_admins")
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

    @patch(MODULE_PATH + ".STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True)
    @patch(MODULE_PATH + ".Owner.are_all_syncs_ok", True)
    @patch(MODULE_PATH + ".notify_admins")
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

    @patch(MODULE_PATH + ".STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True)
    @patch(MODULE_PATH + ".Owner.are_all_syncs_ok", True)
    @patch(MODULE_PATH + ".notify_admins")
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
