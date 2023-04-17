import datetime as dt
from copy import deepcopy
from unittest.mock import patch

from pytz import UTC

from django.utils.timezone import now
from eveuniverse.models import EveSolarSystem

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from structures.constants import EveTypeId
from structures.models import (
    EveSovereigntyMap,
    FuelAlertConfig,
    JumpFuelAlertConfig,
    NotificationType,
    PocoDetails,
    Structure,
    StructureItem,
    StructureService,
    StructureTag,
)

from ..testdata.factories import (
    create_owner_from_user,
    create_starbase,
    create_upwell_structure,
)
from ..testdata.factories_2 import (
    JumpGateFactory,
    OwnerFactory,
    PocoFactory,
    StarbaseFactory,
    StructureFactory,
    StructureTagFactory,
)
from ..testdata.helpers import create_structures, load_entities, set_owner_character
from ..testdata.load_eveuniverse import load_eveuniverse

STRUCTURES_PATH = "structures.models.structures"
NOTIFICATIONS_PATH = "structures.models.notifications"

EVE_ID_HELIUM_FUEL_BLOCK = 4247
EVE_ID_NITROGEN_FUEL_BLOCK = 4051


class TestStructureTag(NoSocketsTestCase):
    def test_str(self):
        obj = StructureTag(name="Super cool tag")
        self.assertEqual(str(obj), "Super cool tag")

    def test_repr(self):
        obj = StructureTag.objects.create(name="Super cool tag")
        expected = "StructureTag(name='Super cool tag')"
        self.assertEqual(repr(obj), expected)

    def test_list_sorted(self):
        x1 = StructureTag(name="Alpha")
        x2 = StructureTag(name="charlie")
        x3 = StructureTag(name="bravo")
        tags = [x1, x2, x3]

        self.assertListEqual(StructureTag.sorted(tags), [x1, x3, x2])
        self.assertListEqual(StructureTag.sorted(tags, reverse=True), [x2, x3, x1])

    def test_html_default(self):
        x = StructureTag(name="Super cool tag")
        self.assertEqual(
            x.html, '<span class="label label-default">Super cool tag</span>'
        )

    def test_html_primary(self):
        x = StructureTag(name="Super cool tag", style="primary")
        self.assertEqual(
            x.html, '<span class="label label-primary">Super cool tag</span>'
        )


class TestStructure(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        _, cls.owner = set_owner_character(character_id=1001)

    def test_str_upwell(self):
        obj = Structure.objects.get(id=1000000000001)
        expected = "Amamake - Test Structure Alpha"
        self.assertEqual(str(obj), expected)

    def test_str_poco(self):
        obj = Structure.objects.get(id=1200000000003)
        expected = "Amamake V - Customs Office (Amamake V)"
        self.assertEqual(str(obj), expected)

    def test_str_starbase(self):
        obj = Structure.objects.get(id=1300000000001)
        expected = "Amamake II - Moon 1 - Home Sweat Home"
        self.assertEqual(str(obj), expected)

    def test_repr_upwell(self):
        obj = Structure.objects.get(id=1000000000001)
        expected = (
            "Structure(id=1000000000001, "
            "eve_solar_system='Amamake', "
            "eve_planet='', "
            "eve_moon='', "
            "name='Test Structure Alpha')"
        )
        self.assertEqual(repr(obj), expected)

    def test_repr_poco(self):
        obj = Structure.objects.get(id=1200000000003)
        expected = (
            "Structure(id=1200000000003, "
            "eve_solar_system='Amamake', "
            "eve_planet='Amamake V', "
            "eve_moon='', "
            "name='Customs Office (Amamake V)')"
        )
        self.assertEqual(repr(obj), expected)

    def test_repr_starbase(self):
        obj = Structure.objects.get(id=1300000000001)
        expected = (
            "Structure(id=1300000000001, "
            "eve_solar_system='Amamake', "
            "eve_planet='', "
            "eve_moon='Amamake II - Moon 1', "
            "name='Home Sweat Home')"
        )
        self.assertEqual(repr(obj), expected)

    def test_is_full_power(self):
        structure = Structure.objects.get(id=1000000000001)
        poco = Structure.objects.get(id=1200000000003)

        # true when upwell structure and has fuel that is not expired
        structure.fuel_expires_at = now() + dt.timedelta(hours=1)
        self.assertTrue(structure.is_full_power)

        # false when upwell structure and has fuel, but is expired
        structure.fuel_expires_at = now() - dt.timedelta(hours=1)
        self.assertFalse(structure.is_full_power)

        # False when no fuel info
        structure.fuel_expires_at = None
        self.assertFalse(structure.is_full_power)

        # none when no upwell structure
        poco.fuel_expires_at = now() + dt.timedelta(hours=1)
        self.assertIsNone(poco.is_full_power)

    def test_is_low_power(self):
        structure = Structure.objects.get(id=1000000000001)

        # true if Upwell structure and fuel expired and last online < 7d
        structure.fuel_expires_at = now() - dt.timedelta(seconds=3)
        structure.last_online_at = now() - dt.timedelta(days=3)
        self.assertTrue(structure.is_low_power)

        # True if Upwell structure and no fuel info and last online < 7d
        structure.fuel_expires_at = None
        structure.last_online_at = now() - dt.timedelta(days=3)
        self.assertTrue(structure.is_low_power)

        # false if Upwell structure and it has fuel
        structure.fuel_expires_at = now() + dt.timedelta(days=3)
        self.assertFalse(structure.is_low_power)

        # none if upwell structure, but not online info
        structure.fuel_expires_at = now() - dt.timedelta(seconds=3)
        structure.last_online_at = None
        self.assertFalse(structure.is_low_power)

        structure.fuel_expires_at = None
        structure.last_online_at = None
        self.assertFalse(structure.is_low_power)

        # none for non structures
        starbase = Structure.objects.get(id=1300000000001)
        self.assertIsNone(starbase.is_low_power)

        pos = Structure.objects.get(id=1200000000003)
        self.assertIsNone(pos.is_low_power)

    def test_is_abandoned(self):
        # none for non structures
        starbase = Structure.objects.get(id=1300000000001)  # starbase
        self.assertIsNone(starbase.is_abandoned)

        structure = Structure.objects.get(id=1000000000001)

        # true when upwell structure, online > 7 days
        structure.last_online_at = now() - dt.timedelta(days=7, seconds=1)

        # false when upwell structure, online <= 7 days or none
        structure.last_online_at = now() - dt.timedelta(days=7, seconds=0)
        self.assertFalse(structure.is_abandoned)

        structure.last_online_at = now() - dt.timedelta(days=3)
        self.assertFalse(structure.is_abandoned)

        # none if missing information
        structure.last_online_at = None
        self.assertFalse(structure.is_abandoned)

    def test_structure_service_str(self):
        structure = Structure.objects.get(id=1000000000001)
        obj = StructureService(
            structure=structure, name="Dummy", state=StructureService.State.ONLINE
        )
        self.assertEqual(str(obj), "Amamake - Test Structure Alpha - Dummy")

    def test_extract_name_from_esi_response(self):
        expected = "Alpha"
        self.assertEqual(
            Structure.extract_name_from_esi_response("Super - Alpha"), expected
        )
        self.assertEqual(Structure.extract_name_from_esi_response("Alpha"), expected)

    def test_owner_has_sov(self):
        # Wayne Tech has sov in 1-PG
        pos = Structure.objects.get(id=1300000000003)
        self.assertTrue(pos.owner_has_sov)

        # Wayne Tech has no sov in A-C5TC
        structure = Structure.objects.get(id=1000000000003)
        self.assertFalse(structure.owner_has_sov)

        # Wayne Tech has no sov in Amamake
        structure = Structure.objects.get(id=1000000000001)
        self.assertFalse(structure.owner_has_sov)

    def test_should_return_hours_when_fuel_expires(self):
        # given
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=2)
        # when
        result = structure.hours_fuel_expires
        # then
        self.assertAlmostEqual(result, 2.0, delta=0.1)

    def test_should_return_none_when_not_fuel_info(self):
        # given
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = None
        # when
        result = structure.hours_fuel_expires
        # then
        self.assertIsNone(result)

    def test_should_return_moon_location(self):
        # given
        starbase = Structure.objects.get(id=1300000000001)
        # when/then
        self.assertEqual(starbase.location_name, "Amamake II - Moon 1")

    def test_should_return_planet_location(self):
        # given
        poco = Structure.objects.get(id=1200000000003)
        # when/then
        self.assertEqual(poco.location_name, "Amamake V")

    def test_should_return_solar_system_location(self):
        # given
        structure = Structure.objects.get(id=1000000000001)
        # when/then
        self.assertEqual(structure.location_name, "Amamake")

    def test_is_poco(self):
        # given
        structure = StructureFactory.build()
        poco = PocoFactory.build()
        starbase = StarbaseFactory.build()
        # then
        self.assertFalse(structure.is_poco)
        self.assertTrue(poco.is_poco)
        self.assertFalse(starbase.is_poco)

    def test_is_starbase(self):
        # given
        structure = StructureFactory.build()
        poco = PocoFactory.build()
        starbase = StarbaseFactory.build()
        # then
        self.assertFalse(structure.is_starbase)
        self.assertFalse(poco.is_starbase)
        self.assertTrue(starbase.is_starbase)

    def test_is_upwell_structure(self):
        # given
        structure = StructureFactory.build()
        poco = PocoFactory.build()
        starbase = StarbaseFactory.build()
        # then
        self.assertTrue(structure.is_upwell_structure)
        self.assertFalse(poco.is_upwell_structure)
        self.assertFalse(starbase.is_upwell_structure)

    def test_is_jump_gate(self):
        # given
        normal_structure = Structure.objects.get(id=1000000000001)
        poco = PocoFactory.build()
        starbase = StarbaseFactory.build()
        jump_gate = JumpGateFactory.build()
        # then
        self.assertFalse(normal_structure.is_jump_gate)
        self.assertFalse(poco.is_jump_gate)
        self.assertFalse(starbase.is_jump_gate)
        self.assertTrue(jump_gate.is_jump_gate)

    # TODO: activate
    # def test_is_upwell_structure_data_error(self):
    #     # group without a category
    #     my_group = EveGroup.objects.create(id=299999, name="invalid group")
    #     my_type = EveType.objects.create(
    #         id=199999, name="invalid type", eve_group=my_group
    #     )
    #     self.assertFalse(my_type.is_upwell_structure)

    def test_should_detect_structure_has_position(self):
        # given
        structure = StructureFactory.build()
        # then
        self.assertTrue(structure.has_position)

    def test_should_detect_structure_has_no_position(self):
        # given
        structure = StructureFactory.build(
            position_x=None, position_y=None, position_z=None
        )
        # then
        self.assertFalse(structure.has_position)

    def test_should_return_jump_fuel_quantity(self):
        # given
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
            is_singleton=False,
            quantity=32,
        )
        structure.items.create(
            id=2,
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
            is_singleton=False,
            quantity=10,
        )
        # when
        result = structure.jump_fuel_quantity()
        # then
        self.assertEqual(result, 42)

    def test_should_return_none_for_jump_fuel_1(self):
        # given
        structure = Structure.objects.get(id=1000000000003)
        # when
        result = structure.jump_fuel_quantity()
        # then
        self.assertIsNone(result)

    def test_should_return_none_for_jump_fuel_2(self):
        # given
        structure = Structure.objects.get(id=1200000000005)
        # when
        result = structure.jump_fuel_quantity()
        # then
        self.assertIsNone(result)

    def test_should_remove_fuel_alerts_when_fuel_level_above_threshold(self):
        # given
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
            is_singleton=False,
            quantity=101,
        )
        structure.jump_fuel_alerts.create(config=config)
        # when
        structure.reevaluate_jump_fuel_alerts()
        # then
        self.assertEqual(structure.jump_fuel_alerts.count(), 0)

    def test_should_keep_fuel_alerts_when_fuel_level_below_threshold(self):
        # given
        config = JumpFuelAlertConfig.objects.create(threshold=100)
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=EveTypeId.LIQUID_OZONE,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
            is_singleton=False,
            quantity=99,
        )
        structure.jump_fuel_alerts.create(config=config)
        # when
        structure.reevaluate_jump_fuel_alerts()
        # then
        self.assertEqual(structure.jump_fuel_alerts.count(), 1)

    def test_should_return_fuel_blocks(self):
        # given
        structure = Structure.objects.get(id=1000000000004)
        structure.items.create(
            id=1,
            eve_type_id=EVE_ID_NITROGEN_FUEL_BLOCK,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
            is_singleton=False,
            quantity=250,
        )
        structure.items.create(
            id=2,
            eve_type_id=EVE_ID_HELIUM_FUEL_BLOCK,
            location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
            is_singleton=False,
            quantity=1000,
        )
        structure.items.create(
            id=3,
            eve_type_id=EVE_ID_HELIUM_FUEL_BLOCK,
            location_flag=StructureItem.LocationFlag.CARGO,
            is_singleton=False,
            quantity=500,
        )
        # when
        result = structure.structure_fuel_quantity
        # then
        self.assertEqual(result, 1250)

    def test_should_return_fuel_need(self):
        # given
        structure = Structure.objects.create(
            id=1900000000001,
            owner=self.owner,
            eve_solar_system_id=30002537,
            name="Dummy",
            state=Structure.State.SHIELD_VULNERABLE,
            eve_type_id=35832,
            fuel_expires_at=dt.datetime(2022, 1, 24, 5, 0, tzinfo=UTC),
        )
        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 17, 15, 13, tzinfo=UTC)
            structure.items.create(
                id=1,
                eve_type_id=EVE_ID_NITROGEN_FUEL_BLOCK,
                location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
                is_singleton=False,
                quantity=6309,
            )
        # when
        result = structure.structure_fuel_usage()
        # then
        self.assertEqual(result, 168)

    def test_should_not_break_when_no_fuel_date(self):
        # given
        structure = Structure.objects.create(
            id=1900000000001,
            owner=self.owner,
            eve_solar_system_id=30002537,
            name="Dummy",
            state=Structure.State.SHIELD_VULNERABLE,
            eve_type_id=35832,
            fuel_expires_at=None,
        )
        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = dt.datetime(2021, 12, 17, 15, 13, tzinfo=UTC)
            structure.items.create(
                id=1,
                eve_type_id=EVE_ID_NITROGEN_FUEL_BLOCK,
                location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
                is_singleton=False,
                quantity=6309,
            )
        # when
        result = structure.structure_fuel_usage()
        # then
        self.assertIsNone(result)


class TestStructure3(NoSocketsTestCase):
    """New version of TestStructure using factories to create testdata."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.user, _ = create_user_from_evecharacter(1001)
        cls.owner = create_owner_from_user(cls.user)

    def test_should_not_show_structure_as_reinforced(self):
        # given
        structure = create_upwell_structure(
            owner=self.owner, state=Structure.State.SHIELD_VULNERABLE
        )
        # when/then
        self.assertFalse(structure.is_reinforced)

    def test_should_show_structure_as_reinforced(self):
        for state in [
            Structure.State.ARMOR_REINFORCE,
            Structure.State.HULL_REINFORCE,
            Structure.State.ANCHOR_VULNERABLE,
            Structure.State.HULL_VULNERABLE,
        ]:
            with self.subTest(state=state):
                structure = create_upwell_structure(owner=self.owner, state=state)
                self.assertTrue(structure.is_reinforced)

    def test_should_show_starbase_as_reinforced(self):
        # given
        structure = create_starbase(
            owner=self.owner, state=Structure.State.POS_REINFORCED
        )
        # when/then
        self.assertTrue(structure.is_reinforced)


class TestStructureIsBurningFuel(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        set_owner_character(character_id=1001)

    def test_should_return_true_for_structure(self):
        # given
        structure = Structure.objects.get(id=1000000000001)
        # when/then
        self.assertTrue(structure.is_burning_fuel)

    def test_should_return_false_for_structure(self):
        # given
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = None
        # when/then
        self.assertFalse(structure.is_burning_fuel)

    def test_should_return_true_for_starbase(self):
        # given
        starbase = Structure.objects.get(id=1300000000001)
        for state in [
            Structure.State.POS_ONLINE,
            Structure.State.POS_REINFORCED,
            Structure.State.POS_UNANCHORING,
        ]:
            starbase.state = state
            # when/then
            self.assertTrue(starbase.is_burning_fuel)

    def test_should_return_false_for_starbase(self):
        # given
        starbase = Structure.objects.get(id=1300000000001)
        for state in [Structure.State.POS_OFFLINE, Structure.State.POS_ONLINING]:
            starbase.state = state
            # when/then
            self.assertFalse(starbase.is_burning_fuel)

    def test_should_return_false_for_poco(self):
        # given
        poco = Structure.objects.get(id=1200000000003)
        # when/then
        self.assertFalse(poco.is_burning_fuel)


@patch(STRUCTURES_PATH + ".STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS", True)
@patch(STRUCTURES_PATH + ".Structure.FUEL_DATES_EQUAL_THRESHOLD_UPWELL", 900)
@patch(STRUCTURES_PATH + ".Structure.FUEL_DATES_EQUAL_THRESHOLD_STARBASE", 7200)
class TestStructureFuelLevels(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        set_owner_character(character_id=1001)

    @patch(
        NOTIFICATIONS_PATH + ".Notification.send_to_configured_webhooks",
        lambda *args, **kwargs: None,
    )
    def test_should_reset_fuel_notifications_when_refueled_1(self):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=12)
        structure.save()
        structure.structure_fuel_alerts.create(config=config, hours=12)
        old_instance = deepcopy(structure)
        # when
        structure.fuel_expires_at = now() + dt.timedelta(hours=13)
        structure.handle_fuel_notifications(old_instance)
        # then
        self.assertEqual(structure.structure_fuel_alerts.count(), 0)

    @patch(
        NOTIFICATIONS_PATH + ".Notification.send_to_configured_webhooks",
        lambda *args, **kwargs: None,
    )
    def test_should_reset_fuel_notifications_when_fuel_expires_date_has_changed(self):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=12)
        structure.save()
        old_instance = deepcopy(structure)
        structure.structure_fuel_alerts.create(config=config, hours=12)
        # when
        structure.fuel_expires_at = now() + dt.timedelta(hours=11)
        structure.handle_fuel_notifications(old_instance)
        # then
        self.assertEqual(structure.structure_fuel_alerts.count(), 0)

    @patch(
        NOTIFICATIONS_PATH + ".Notification.send_to_configured_webhooks",
        lambda *args, **kwargs: None,
    )
    def test_should_not_reset_fuel_notifications_when_fuel_expiry_dates_unchanged(self):
        # given
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=12)
        structure.save()
        structure.structure_fuel_alerts.create(config=config, hours=12)
        old_instance = deepcopy(structure)
        # when
        structure.fuel_expires_at = now() + dt.timedelta(hours=12, minutes=5)
        structure.handle_fuel_notifications(old_instance)
        # then
        self.assertEqual(structure.structure_fuel_alerts.count(), 1)

    @patch(NOTIFICATIONS_PATH + ".Notification.create_from_structure")
    def test_should_generate_structure_refueled_notif_when_fuel_level_increased(
        self, mock_create_from_structure
    ):
        # given
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=1)
        structure.save()
        old_instance = deepcopy(structure)
        # when
        structure.fuel_expires_at = now() + dt.timedelta(hours=6)
        structure.handle_fuel_notifications(old_instance)
        # then
        self.assertTrue(mock_create_from_structure.called)
        _, kwargs = mock_create_from_structure.call_args
        self.assertEqual(
            kwargs["notif_type"], NotificationType.STRUCTURE_REFUELED_EXTRA
        )

    @patch(NOTIFICATIONS_PATH + ".Notification.create_from_structure")
    def test_should_generate_tower_refueled_notif_when_fuel_level_increased(
        self, mock_create_from_structure
    ):
        # given
        structure = Structure.objects.get(id=1300000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=1)
        structure.save()
        old_instance = deepcopy(structure)
        # when
        structure.fuel_expires_at = now() + dt.timedelta(hours=4)
        structure.handle_fuel_notifications(old_instance)
        # then
        self.assertTrue(mock_create_from_structure.called)
        _, kwargs = mock_create_from_structure.call_args
        self.assertEqual(kwargs["notif_type"], NotificationType.TOWER_REFUELED_EXTRA)

    @patch(NOTIFICATIONS_PATH + ".Notification.send_to_webhook")
    def test_should_generate_refueled_notif_when_fuel_level_increased(
        self, mock_send_to_webhook
    ):
        # given
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=1)
        structure.save()
        old_instance = deepcopy(structure)
        # when
        structure.fuel_expires_at = now() + dt.timedelta(hours=12)
        structure.handle_fuel_notifications(old_instance)
        # then
        self.assertTrue(mock_send_to_webhook.called)

    @patch(NOTIFICATIONS_PATH + ".Notification.send_to_webhook")
    def test_should_not_generate_refueled_notif_when_fuel_level_almost_unchanged(
        self, mock_send_to_webhook
    ):
        # given
        structure = Structure.objects.get(id=1000000000001)
        target_date_1 = now() + dt.timedelta(hours=2)
        target_date_1 = now() + dt.timedelta(hours=2, minutes=15)
        structure.fuel_expires_at = target_date_1
        structure.save()
        old_instance = deepcopy(structure)
        # when
        structure.fuel_expires_at = target_date_1
        structure.handle_fuel_notifications(old_instance)
        # then
        self.assertFalse(mock_send_to_webhook.called)

    @patch(NOTIFICATIONS_PATH + ".Notification.send_to_webhook")
    def test_should_not_generate_refueled_notif_fuel_level_decreased(
        self, mock_send_to_webhook
    ):
        # given
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=12)
        structure.save()
        old_instance = deepcopy(structure)
        # when
        structure.fuel_expires_at = now() + dt.timedelta(hours=1)
        structure.handle_fuel_notifications(old_instance)
        # then
        self.assertFalse(mock_send_to_webhook.called)

    @patch(NOTIFICATIONS_PATH + ".Notification.send_to_webhook")
    def test_should_not_generate_refueled_notif_fuel_is_removed(
        self, mock_send_to_webhook
    ):
        # given
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=2)
        structure.save()
        old_instance = deepcopy(structure)
        # when
        structure.fuel_expires_at = None
        structure.handle_fuel_notifications(old_instance)
        # then
        self.assertFalse(mock_send_to_webhook.called)


class TestStructurePowerMode(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()

    def test_returns_none_for_non_upwell_structures(self):
        starbase = Structure.objects.get(id=1300000000001)
        self.assertIsNone(starbase.power_mode)

        pos = Structure.objects.get(id=1200000000003)
        self.assertIsNone(pos.power_mode)

        structure = Structure.objects.get(id=1000000000001)
        self.assertIsNotNone(structure.power_mode)

    def test_full_power_mode(self):
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() + dt.timedelta(hours=1)
        self.assertEqual(structure.power_mode, Structure.PowerMode.FULL_POWER)
        self.assertEqual(structure.get_power_mode_display(), "Full Power")

    def test_low_power_mode(self):
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() - dt.timedelta(seconds=3)
        structure.last_online_at = now() - dt.timedelta(days=3)
        self.assertEqual(structure.power_mode, Structure.PowerMode.LOW_POWER)

        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = None
        structure.last_online_at = None
        structure.state = Structure.State.ANCHORING
        self.assertEqual(structure.power_mode, Structure.PowerMode.LOW_POWER)

        structure.fuel_expires_at = None
        structure.last_online_at = now() - dt.timedelta(days=3)
        self.assertEqual(structure.power_mode, Structure.PowerMode.LOW_POWER)
        self.assertEqual(structure.get_power_mode_display(), "Low Power")

    def test_abandoned_mode(self):
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() - dt.timedelta(seconds=3)
        structure.last_online_at = now() - dt.timedelta(days=7, seconds=1)
        self.assertEqual(structure.power_mode, Structure.PowerMode.ABANDONED)

        structure.fuel_expires_at = None
        structure.last_online_at = now() - dt.timedelta(days=7, seconds=1)
        self.assertEqual(structure.power_mode, Structure.PowerMode.ABANDONED)
        self.assertEqual(structure.get_power_mode_display(), "Abandoned")

    def test_low_abandoned_mode(self):
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = now() - dt.timedelta(seconds=3)
        structure.last_online_at = None
        self.assertEqual(structure.power_mode, Structure.PowerMode.LOW_ABANDONED)

        structure.fuel_expires_at = None
        structure.last_online_at = None
        self.assertEqual(structure.power_mode, Structure.PowerMode.LOW_ABANDONED)
        self.assertEqual(structure.get_power_mode_display(), "Abandoned?")


class TestStructure2(NoSocketsTestCase):
    def setUp(self):
        load_eveuniverse()
        load_entities([EveSovereigntyMap])
        create_structures()
        set_owner_character(character_id=1001)

    def test_can_create_generated_tags(self):
        obj = Structure.objects.get(id=1300000000003)
        obj.tags.clear()
        self.assertFalse(obj.tags.exists())
        obj.update_generated_tags()
        null_tag = StructureTag.objects.get(name=StructureTag.NAME_NULLSEC_TAG)
        self.assertIn(null_tag, list(obj.tags.all()))
        sov_tag = StructureTag.objects.get(name=StructureTag.NAME_SOV_TAG)
        self.assertIn(sov_tag, list(obj.tags.all()))

    def test_can_update_generated_tags(self):
        obj = Structure.objects.get(id=1300000000003)
        null_tag = StructureTag.objects.get(name=StructureTag.NAME_NULLSEC_TAG)
        self.assertIn(null_tag, list(obj.tags.all()))
        null_tag.order = 100
        null_tag.style = StructureTag.Style.DARK_BLUE
        null_tag.save()

        sov_tag = StructureTag.objects.get(name=StructureTag.NAME_SOV_TAG)
        self.assertIn(sov_tag, list(obj.tags.all()))
        sov_tag.order = 100
        sov_tag.style = StructureTag.Style.RED
        sov_tag.save()

        obj.update_generated_tags(recreate_tags=True)
        null_tag.refresh_from_db()
        self.assertEqual(null_tag.style, StructureTag.Style.RED)
        self.assertEqual(null_tag.order, 50)
        sov_tag.refresh_from_db()
        self.assertEqual(sov_tag.style, StructureTag.Style.DARK_BLUE)
        self.assertEqual(sov_tag.order, 20)


class TestStructureSave(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities([EveCharacter, EveSovereigntyMap])
        cls.owner = OwnerFactory(
            corporation=EveCorporationInfo.objects.get(corporation_id=2001)
        )

    def test_can_save_tags_low_sec(self):
        obj = StructureFactory(
            owner=self.owner,
            eve_solar_system=EveSolarSystem.objects.get(name="Amamake"),
        )
        lowsec_tag = StructureTag.objects.get(name=StructureTag.NAME_LOWSEC_TAG)
        self.assertIn(lowsec_tag, obj.tags.all())
        self.assertIsNone(
            StructureTag.objects.filter(name=StructureTag.NAME_SOV_TAG).first()
        )

    def test_can_save_tags_null_sec_w_sov(self):
        obj = StructureFactory(
            owner=self.owner,
            eve_solar_system=EveSolarSystem.objects.get(name="1-PGSG"),
        )
        nullsec_tag = StructureTag.objects.get(name=StructureTag.NAME_NULLSEC_TAG)
        self.assertIn(nullsec_tag, obj.tags.all())
        sov_tag = StructureTag.objects.get(name=StructureTag.NAME_SOV_TAG)
        self.assertIn(sov_tag, obj.tags.all())

    def test_should_create_default_tags(self):
        # given
        default_tag = StructureTagFactory(is_default=True)
        # when
        obj = StructureFactory(owner=self.owner)
        # then
        self.assertIn(default_tag, obj.tags.all())

    def test_should_not_create_default_tags(self):
        # given
        default_tag = StructureTagFactory(is_default=True)
        # when
        obj = StructureFactory(owner=self.owner)
        obj.tags.all().delete()
        obj.save()
        # then
        self.assertNotIn(default_tag, obj.tags.all())


class TestStructureNoSetup(NoSocketsTestCase):
    def test_structure_get_matching_state(self):
        self.assertEqual(
            Structure.State.from_esi_name("anchoring"),
            Structure.State.ANCHORING,
        )
        self.assertEqual(
            Structure.State.from_esi_name("not matching name"),
            Structure.State.UNKNOWN,
        )

    def test_structure_service_get_matching_state(self):
        self.assertEqual(
            StructureService.State.from_esi_name("online"),
            StructureService.State.ONLINE,
        )
        self.assertEqual(
            StructureService.State.from_esi_name("offline"),
            StructureService.State.OFFLINE,
        )
        self.assertEqual(
            StructureService.State.from_esi_name("not matching"),
            StructureService.State.OFFLINE,
        )


class TestStructureService(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        set_owner_character(character_id=1001)

    def test_str(self):
        structure = Structure.objects.get(id=1000000000001)
        obj = StructureService.objects.get(structure=structure, name="Clone Bay")
        expected = "Amamake - Test Structure Alpha - Clone Bay"
        self.assertEqual(str(obj), expected)

    def test_repr(self):
        structure = Structure.objects.get(id=1000000000001)
        obj = StructureService.objects.get(structure=structure, name="Clone Bay")
        expected = "StructureService(structure_id=1000000000001, name='Clone Bay')"
        self.assertEqual(repr(obj), expected)


class TestPocoDetails(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        poco = cls.owner.structures.get(id=1200000000003)
        cls.details = PocoDetails.objects.create(
            structure=poco,
            alliance_tax_rate=0.02,
            allow_access_with_standings=True,
            allow_alliance_access=True,
            corporation_tax_rate=0.01,
            reinforce_exit_end=21,
            reinforce_exit_start=18,
        )

    def test_should_return_tax_for_corporation_member(self):
        # given
        my_character = EveCharacter.objects.get(character_id=1001)
        # when
        result = self.details.tax_for_character(my_character)
        # then
        self.assertEqual(result, 0.01)

    def test_should_return_tax_for_alliance_member(self):
        # given
        my_character = EveCharacter.objects.get(character_id=1003)
        # when
        result = self.details.tax_for_character(my_character)
        # then
        self.assertEqual(result, 0.02)

    def test_should_return_tax_for_unknown(self):
        # given
        my_character = EveCharacter.objects.get(character_id=1011)
        # when
        result = self.details.tax_for_character(my_character)
        # then
        self.assertIsNone(result)

    def test_should_return_standing_map_for_neutral_1(self):
        # given
        self.details.standing_level = PocoDetails.StandingLevel.NEUTRAL
        self.details.allow_access_with_standings = True
        # when
        result = self.details.standing_level_access_map()
        # then
        self.assertDictEqual(
            result,
            {
                "NONE": False,
                "TERRIBLE": False,
                "BAD": False,
                "NEUTRAL": True,
                "GOOD": True,
                "EXCELLENT": True,
            },
        )

    def test_should_return_standing_map_for_neutral_2(self):
        # given
        self.details.standing_level = PocoDetails.StandingLevel.NEUTRAL
        self.details.allow_access_with_standings = False
        # when
        result = self.details.standing_level_access_map()
        # then
        self.assertDictEqual(
            result,
            {
                "NONE": False,
                "TERRIBLE": False,
                "BAD": False,
                "NEUTRAL": False,
                "GOOD": False,
                "EXCELLENT": False,
            },
        )

    def test_should_return_standing_map_for_terrible(self):
        # given
        self.details.standing_level = PocoDetails.StandingLevel.TERRIBLE
        self.details.allow_access_with_standings = True
        # when
        result = self.details.standing_level_access_map()
        # then
        self.assertDictEqual(
            result,
            {
                "NONE": False,
                "TERRIBLE": True,
                "BAD": True,
                "NEUTRAL": True,
                "GOOD": True,
                "EXCELLENT": True,
            },
        )
