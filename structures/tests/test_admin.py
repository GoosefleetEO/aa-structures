import datetime as dt
from unittest.mock import patch

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.timezone import now
from eveuniverse.models import EveEntity

from allianceauth.eveonline.models import EveCorporationInfo

from structures.admin import (
    NotificationAdmin,
    OwnerAdmin,
    OwnerAllianceFilter,
    OwnerCorporationsFilter,
    StructureAdmin,
    StructureFuelAlertConfigAdmin,
    WebhookAdmin,
)
from structures.models import (
    FuelAlertConfig,
    Notification,
    Owner,
    Structure,
    StructureTag,
    Webhook,
)

from .testdata.factories_2 import (
    FuelAlertConfigFactory,
    NotificationFactory,
    OwnerFactory,
    StructureFactory,
)
from .testdata.helpers import (
    create_structures,
    create_user,
    load_entities,
    load_notification_entities,
    set_owner_character,
)
from .testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "structures.admin"


class MockRequest(object):
    def __init__(self, user=None):
        self.user = user


class TestFuelNotificationConfigAdminView(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.defaults = {
            "is_enabled": True,
            "channel_ping_type": Webhook.PingType.HERE,
            "color": Webhook.Color.WARNING,
        }
        cls.user = User.objects.create_superuser("Clark Kent")
        load_eveuniverse()

    def test_should_create_new_config(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.post(
            reverse("admin:structures_fuelalertconfig_add"),
            data={**self.defaults, **{"start": 12, "end": 5, "repeat": 2}},
        )
        # then
        self.assertRedirects(
            response, reverse("admin:structures_fuelalertconfig_changelist")
        )
        self.assertEqual(FuelAlertConfig.objects.count(), 1)

    def test_should_update_existing_config(self):
        # given
        self.client.force_login(self.user)
        config = FuelAlertConfigFactory(start=48, end=24, repeat=12)
        # when
        response = self.client.post(
            reverse("admin:structures_fuelalertconfig_change", args=[config.pk]),
            data={**self.defaults, **{"start": 48, "end": 0, "repeat": 2}},
        )
        # then
        self.assertRedirects(
            response, reverse("admin:structures_fuelalertconfig_changelist")
        )
        self.assertEqual(FuelAlertConfig.objects.count(), 1)

    def test_should_remove_existing_fuel_notifications_when_timing_changed(self):
        # given
        self.client.force_login(self.user)
        config = FuelAlertConfigFactory(start=48, end=24, repeat=12)
        structure = StructureFactory()
        structure.structure_fuel_alerts.create(
            config=config, structure=structure, hours=5
        )
        # when
        response = self.client.post(
            reverse("admin:structures_fuelalertconfig_change", args=[config.pk]),
            data={**self.defaults, **{"start": 48, "end": 0, "repeat": 2}},
        )
        # then
        self.assertRedirects(
            response, reverse("admin:structures_fuelalertconfig_changelist")
        )
        self.assertEqual(structure.structure_fuel_alerts.count(), 0)

    def test_should_not_remove_existing_fuel_notifications_on_other_changes(self):
        # given
        self.client.force_login(self.user)
        config = FuelAlertConfigFactory(start=48, end=24, repeat=12)
        structure = StructureFactory()
        structure.structure_fuel_alerts.create(
            config=config, structure=structure, hours=5
        )
        # when
        response = self.client.post(
            reverse("admin:structures_fuelalertconfig_change", args=[config.pk]),
            data={
                **self.defaults,
                **{"start": 48, "end": 24, "repeat": 12, "is_enabled": False},
            },
        )
        # then
        self.assertRedirects(
            response, reverse("admin:structures_fuelalertconfig_changelist")
        )
        self.assertEqual(structure.structure_fuel_alerts.count(), 1)

    def test_should_not_allow_end_before_start(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.post(
            reverse("admin:structures_fuelalertconfig_add"),
            data={**self.defaults, **{"start": 1, "end": 2, "repeat": 1}},
        )
        # then
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errornote")
        self.assertEqual(FuelAlertConfig.objects.count(), 0)

    def test_should_not_allow_invalid_frequency(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.post(
            reverse("admin:structures_fuelalertconfig_add"),
            data={**self.defaults, **{"start": 48, "end": 24, "repeat": 36}},
        )
        # then
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errornote")
        self.assertEqual(FuelAlertConfig.objects.count(), 0)

    def test_should_not_allow_creating_overlapping(self):
        # given
        self.client.force_login(self.user)
        FuelAlertConfigFactory(start=48, end=24, repeat=12)
        # when
        response = self.client.post(
            reverse("admin:structures_fuelalertconfig_add"),
            data={**self.defaults, **{"start": 36, "end": 0, "repeat": 8}},
        )
        # then
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errornote")
        self.assertEqual(FuelAlertConfig.objects.count(), 1)

    def test_should_work_with_empty_end_field(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.post(
            reverse("admin:structures_fuelalertconfig_add"),
            data={**self.defaults, **{"start": 36, "repeat": 8}},
        )
        # then
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errornote")
        self.assertEqual(FuelAlertConfig.objects.count(), 0)

    def test_should_work_with_empty_start_field(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.post(
            reverse("admin:structures_fuelalertconfig_add"),
            data={**self.defaults, **{"start": 36, "end": 8}},
        )
        # then
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errornote")
        self.assertEqual(FuelAlertConfig.objects.count(), 0)

    def test_should_work_with_empty_repeat_field(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.post(
            reverse("admin:structures_fuelalertconfig_add"),
            data={**self.defaults, **{"start": 36, "end": 8}},
        )
        # then
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errornote")
        self.assertEqual(FuelAlertConfig.objects.count(), 0)


class TestStructureFuelAlertAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.modeladmin = StructureFuelAlertConfigAdmin(
            model=FuelAlertConfig, admin_site=AdminSite()
        )
        load_eveuniverse()

    @patch(MODULE_PATH + ".StructureFuelAlertConfigAdmin.message_user", spec=True)
    @patch(MODULE_PATH + ".tasks", spec=True)
    def test_should_send_fuel_notifications(self, mock_tasks, mock_message_user):
        # given
        config = FuelAlertConfigFactory()
        request = MockRequest()
        queryset = FuelAlertConfig.objects.filter(pk=config.pk)
        # when
        self.modeladmin.send_fuel_notifications(request, queryset)
        # then
        self.assertTrue(mock_tasks.send_queued_messages_for_webhooks.called)
        self.assertTrue(mock_message_user.called)


class TestNotificationAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.modeladmin = NotificationAdmin(model=Notification, admin_site=AdminSite())
        load_eveuniverse()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        load_notification_entities(cls.owner)
        cls.obj = Notification.objects.get(notification_id=1000000404)
        cls.obj_qs = Notification.objects.filter(
            notification_id__in=[1000000404, 1000000405]
        )

    def test_structures_1(self):
        # given
        notif = Notification.objects.get(notification_id=1000000404)
        # when
        result = self.modeladmin._structures(notif)
        self.assertEqual(result, "?")

    def test_structures_2(self):
        # given
        notif = Notification.objects.get(notification_id=1000000202)
        # when
        result = self.modeladmin._structures(notif)
        self.assertIsNone(result)

    # FixMe: Does not seam to work with special prefetch list
    # def test_webhooks(self):
    #     self.owner.webhooks.add(Webhook.objects.get(name="Test Webhook 2"))
    #     self.assertEqual(
    #         self.modeladmin._webhooks(self.obj), "Test Webhook 1, Test Webhook 2"
    #     )

    @patch(MODULE_PATH + ".NotificationAdmin.message_user", autospec=True)
    def test_action_mark_as_sent(self, mock_message_user):
        for obj in self.obj_qs:
            obj.is_sent = False
            obj.save()
        self.modeladmin.mark_as_sent(MockRequest(self.user), self.obj_qs)
        for obj in self.obj_qs:
            self.assertTrue(obj.is_sent)
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + ".NotificationAdmin.message_user", autospec=True)
    def test_action_mark_as_unsent(self, mock_message_user):
        for obj in self.obj_qs:
            obj.is_sent = True
            obj.save()
        self.modeladmin.mark_as_unsent(MockRequest(self.user), self.obj_qs)
        for obj in self.obj_qs:
            self.assertFalse(obj.is_sent)
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + ".NotificationAdmin.message_user", autospec=True)
    @patch(MODULE_PATH + ".tasks.send_queued_messages_for_webhooks")
    def test_action_send_to_webhook(self, mock_task, mock_message_user):
        self.modeladmin.send_to_configured_webhooks(MockRequest(self.user), self.obj_qs)
        self.assertEqual(mock_task.call_count, 1)
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + ".NotificationAdmin.message_user", autospec=True)
    @patch(MODULE_PATH + ".Notification.add_or_remove_timer")
    def test_action_process_for_timerboard(
        self, mock_process_for_timerboard, mock_message_user
    ):
        self.modeladmin.add_or_remove_timer(MockRequest(self.user), self.obj_qs)
        self.assertEqual(mock_process_for_timerboard.call_count, 2)
        self.assertTrue(mock_message_user.called)


class TestOwnerAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.modeladmin = OwnerAdmin(model=Owner, admin_site=AdminSite())
        load_eveuniverse()
        create_structures()
        cls.user, cls.obj = set_owner_character(character_id=1001)

    def test_corporation(self):
        self.assertEqual(self.modeladmin._corporation(self.obj), "Wayne Technologies")

    def test_alliance_normal(self):
        self.assertEqual(self.modeladmin._alliance(self.obj), "Wayne Enterprises")

    def test_alliance_none(self):
        my_owner = Owner.objects.get(corporation__corporation_id=2102)
        self.assertIsNone(self.modeladmin._alliance(my_owner))

    def test_webhooks(self):
        self.obj.webhooks.add(Webhook.objects.get(name="Test Webhook 2"))
        self.assertEqual(
            self.modeladmin._webhooks(self.obj), "Test Webhook 1<br>Test Webhook 2"
        )

    @patch(MODULE_PATH + ".OwnerAdmin.message_user", autospec=True)
    @patch(MODULE_PATH + ".tasks.update_structures_for_owner")
    def test_action_update_structures(self, mock_task, mock_message_user):
        owner_qs = Owner.objects.filter(corporation__corporation_id__in=[2001, 2002])
        self.modeladmin.update_structures(MockRequest(self.user), owner_qs)
        self.assertEqual(mock_task.delay.call_count, 2)
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + ".OwnerAdmin.message_user", autospec=True)
    @patch(MODULE_PATH + ".tasks.process_notifications_for_owner")
    def test_action_fetch_notifications(self, mock_task, mock_message_user):
        owner_qs = Owner.objects.filter(corporation__corporation_id__in=[2001, 2002])
        self.modeladmin.fetch_notifications(MockRequest(self.user), owner_qs)
        self.assertEqual(mock_task.delay.call_count, 2)
        self.assertTrue(mock_message_user.called)

    def test_should_return_empty_turnaround_times(self):
        # given
        my_owner = Owner.objects.get(corporation__corporation_id=2001)
        # when
        result = self.modeladmin._avg_turnaround_time(my_owner)
        # then
        self.assertEqual(result, "- | - | -")

    @patch(MODULE_PATH + ".app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_SHORT", 5)
    @patch(MODULE_PATH + ".app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_MEDIUM", 15)
    @patch(MODULE_PATH + ".app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_LONG", 50)
    @patch(
        MODULE_PATH + ".app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_MAX_VALID", 3600
    )
    def test_should_return_correct_turnaround_times(self):
        # given
        my_owner = OwnerFactory()
        my_sender = EveEntity.objects.get(id=1001)
        my_now = now()
        NotificationFactory(
            owner=my_owner,
            notification_id=1,
            sender=my_sender,
            last_updated=my_now,
            timestamp=my_now,
            created=my_now + dt.timedelta(seconds=3601),
        )
        for i in range(50):
            timestamp = my_now + dt.timedelta(minutes=i)
            NotificationFactory(
                owner=my_owner,
                notification_id=2 + i,
                sender=my_sender,
                last_updated=my_now,
                timestamp=timestamp,
                created=timestamp + dt.timedelta(seconds=2),
            )
        # when
        result = self.modeladmin._avg_turnaround_time(my_owner)
        # then
        self.assertEqual(result, "2 | 2 | 2")


class TestStructureAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.modeladmin = StructureAdmin(model=Structure, admin_site=AdminSite())
        load_eveuniverse()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.obj = Structure.objects.get(id=1000000000001)
        cls.obj_qs = Structure.objects.filter(id__in=[1000000000001, 1000000000002])

    def test_owner(self):
        self.assertEqual(
            self.modeladmin._owner(self.obj), "Wayne Technologies<br>Wayne Enterprises"
        )

    def test_location(self):
        self.assertEqual(self.modeladmin._location(self.obj), "Amamake<br>Heimatar")
        poco = Structure.objects.get(id=1200000000003)
        self.assertEqual(self.modeladmin._location(poco), "Amamake V<br>Heimatar")
        starbase = Structure.objects.get(id=1300000000001)
        self.assertEqual(
            self.modeladmin._location(starbase), "Amamake II - Moon 1<br>Heimatar"
        )

    def test_type(self):
        self.assertEqual(self.modeladmin._type(self.obj), "Astrahus<br>Citadel")

    def test_tags_1(self):
        self.assertSetEqual(set(self.modeladmin._tags(self.obj)), {"lowsec", "tag_a"})

    def test_tags_2(self):
        self.obj.tags.clear()
        self.assertListEqual(self.modeladmin._tags(self.obj), [])

    @patch(MODULE_PATH + ".StructureAdmin.message_user", autospec=True)
    def test_action_add_default_tags(self, mock_message_user):
        for obj in self.obj_qs:
            obj.tags.clear()
        self.modeladmin.add_default_tags(MockRequest(self.user), self.obj_qs)
        default_tags = StructureTag.objects.filter(is_default=True)
        for obj in self.obj_qs:
            self.assertSetEqual(set(obj.tags.all()), set(default_tags))
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + ".StructureAdmin.message_user", autospec=True)
    def test_action_remove_user_tags(self, mock_message_user):
        self.modeladmin.remove_user_tags(MockRequest(self.user), self.obj_qs)
        for obj in self.obj_qs:
            self.assertFalse(obj.tags.filter(is_user_managed=True).exists())
        self.assertTrue(mock_message_user.called)

    def test_owner_corporations_status_filter(self):
        class StructureAdminTest(admin.ModelAdmin):
            list_filter = (OwnerCorporationsFilter,)

        Owner.objects.all().delete()
        owner_2001 = OwnerFactory(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        OwnerFactory(corporation=EveCorporationInfo.objects.get(corporation_id=2002))
        my_modeladmin = StructureAdminTest(Structure, AdminSite())

        # Make sure the lookups are correct
        request = self.factory.get("/")
        request.user = self.user
        changelist = my_modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [(2002, "Wayne Foods"), (2001, "Wayne Technologies")]
        self.assertEqual(filterspec.lookup_choices, expected)

        # Make sure the correct queryset is returned
        request = self.factory.get("/", {"owner_corporation_id__exact": 2001})
        request.user = self.user
        changelist = my_modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        expected = Structure.objects.filter(owner=owner_2001)
        self.assertSetEqual(set(queryset), set(expected))

    def test_owner_alliance_status_filter(self):
        class StructureAdminTest(admin.ModelAdmin):
            list_filter = (OwnerAllianceFilter,)

        Owner.objects.all().delete()
        owner_2001 = OwnerFactory(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )
        owner_2002 = OwnerFactory(
            corporation=EveCorporationInfo.objects.get(corporation_id=2002)
        )
        OwnerFactory(corporation=EveCorporationInfo.objects.get(corporation_id=2102))
        modeladmin = StructureAdminTest(Structure, AdminSite())

        # Make sure the lookups are correct
        request = self.factory.get("/")
        request.user = self.user
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [(3001, "Wayne Enterprises")]
        self.assertEqual(filterspec.lookup_choices, expected)

        # Make sure the correct queryset is returned
        request = self.factory.get("/", {"owner_alliance_id__exact": 3001})
        request.user = self.user
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        expected = Structure.objects.filter(owner__in=[owner_2001, owner_2002])
        self.assertSetEqual(set(queryset), set(expected))


class TestWebhookAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.modeladmin = WebhookAdmin(model=Webhook, admin_site=AdminSite())
        load_entities([Webhook])
        cls.user = create_user(character_id=1001, load_data=True)
        cls.obj_qs = Webhook.objects.all()

    @patch(MODULE_PATH + ".WebhookAdmin.message_user", autospec=True)
    @patch(MODULE_PATH + ".tasks.send_test_notifications_to_webhook")
    def test_action_test_notification(self, mock_task, mock_message_user):
        self.modeladmin.test_notification(MockRequest(self.user), self.obj_qs)
        self.assertEqual(mock_task.delay.call_count, 2)
        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + ".WebhookAdmin.message_user", autospec=True)
    def test_action_activate(self, mock_message_user):
        for obj in self.obj_qs:
            obj.is_active = False
            obj.save()
        self.modeladmin.activate(MockRequest(self.user), self.obj_qs)
        for obj in self.obj_qs:
            self.assertTrue(obj.is_active)

        self.assertTrue(mock_message_user.called)

    @patch(MODULE_PATH + ".WebhookAdmin.message_user", autospec=True)
    def test_action_deactivate(self, mock_message_user):
        for obj in self.obj_qs:
            obj.is_active = True
            obj.save()
        self.modeladmin.deactivate(MockRequest(self.user), self.obj_qs)
        for obj in self.obj_qs:
            self.assertFalse(obj.is_active)

        self.assertTrue(mock_message_user.called)
