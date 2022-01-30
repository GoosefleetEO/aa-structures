from datetime import datetime, timedelta
from unittest.mock import patch

from bravado.exception import HTTPForbidden, HTTPInternalServerError

from django.utils.timezone import now, utc

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from app_utils.testing import (
    BravadoResponseStub,
    NoSocketsTestCase,
    create_user_from_evecharacter,
)

from ...models import (
    EveCategory,
    EveConstellation,
    EveEntity,
    EveGroup,
    EveMoon,
    EvePlanet,
    EveRegion,
    EveSolarSystem,
    EveSovereigntyMap,
    EveType,
    FuelAlertConfig,
    NotificationType,
    Owner,
    PocoDetails,
    Structure,
    StructureService,
    StructureTag,
    Webhook,
)
from .. import to_json
from ..testdata import entities_testdata, load_entities
from ..testdata.esi_client_stub import (
    EsiEndpointCallback,
    esi_client_stub,
    generate_esi_client_stub,
)
from ..testdata.factories import (
    create_owner_from_user,
    create_poco,
    create_starbase,
    create_structure_service,
    create_upwell_structure,
)
from ..testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "structures.models.owners"


@patch(MODULE_PATH + ".esi")
class TestUpdateStructuresEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # given (global)
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
                EveSovereigntyMap,
                EvePlanet,
                EveMoon,
                EveCorporationInfo,
                EveCharacter,
                EveEntity,
            ]
        )
        load_eveuniverse()
        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        cls.user, cls.main_ownership = create_user_from_evecharacter(
            1001,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        for x in entities_testdata["StructureTag"]:
            StructureTag.objects.create(**x)

    # def setUp(self):
    #     # reset data that might be overridden
    #     esi_get_corporations_corporation_id_structures.override_data = None
    #     esi_get_corporations_corporation_id_starbases.override_data = None
    #     esi_get_corporations_corporation_id_customs_offices.override_data = None

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_can_sync_upwell_structures(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)
        self.assertAlmostEqual(
            owner.structures_last_update_at, now(), delta=timedelta(seconds=30)
        )

        # must contain all expected structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

        # verify attributes for structure
        structure = Structure.objects.get(id=1000000000001)
        self.assertEqual(structure.name, "Test Structure Alpha")
        self.assertEqual(structure.position_x, 55028384780.0)
        self.assertEqual(structure.position_y, 7310316270.0)
        self.assertEqual(structure.position_z, -163686684205.0)
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(structure.eve_type_id, 35832)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.state, Structure.State.SHIELD_VULNERABLE)
        self.assertEqual(structure.reinforce_hour, 18)
        self.assertEqual(
            structure.fuel_expires_at, datetime(2020, 3, 5, 5, 0, 0, tzinfo=utc)
        )
        self.assertEqual(
            structure.state_timer_start, datetime(2020, 4, 5, 6, 30, 0, tzinfo=utc)
        )
        self.assertEqual(
            structure.state_timer_end, datetime(2020, 4, 5, 7, 0, 0, tzinfo=utc)
        )
        self.assertEqual(
            structure.unanchors_at, datetime(2020, 5, 5, 6, 30, 0, tzinfo=utc)
        )

        # must have created services with localizations
        # structure 1000000000001
        expected = {
            to_json(
                {
                    "name": "Clone Bay",
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": "Clone Bay_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
            to_json(
                {
                    "name": "Market Hub",
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": "Market Hub_zh",
                    "state": StructureService.State.OFFLINE,
                }
            ),
        }
        structure = Structure.objects.get(id=1000000000001)
        services = {
            to_json(
                {
                    "name": x.name,
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": x.name_zh,
                    "state": x.state,
                }
            )
            for x in structure.services.all()
        }
        self.assertEqual(services, expected)

        # must have created services with localizations
        # structure 1000000000002
        expected = {
            to_json(
                {
                    "name": "Reprocessing",
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": "Reprocessing_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
            to_json(
                {
                    "name": "Moon Drilling",
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": "Moon Drilling_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
        }
        structure = Structure.objects.get(id=1000000000002)
        services = {
            to_json(
                {
                    "name": x.name,
                    "name_de": "",
                    "name_ko": "",
                    "name_ru": "",
                    # "name_zh": x.name_zh,
                    "state": x.state,
                }
            )
            for x in structure.services.all()
        }
        self.assertEqual(services, expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_sync_pocos(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()

        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)

        # must contain all expected structures
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1200000000099,
        }
        self.assertSetEqual(owner.structures.ids(), expected)
        self.assertSetEqual(
            set(PocoDetails.objects.values_list("structure_id", flat=True)),
            {1200000000003, 1200000000004, 1200000000005, 1200000000006, 1200000000099},
        )

        # verify attributes for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "Planet (Barren)")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 2233)
        self.assertEqual(structure.reinforce_hour, 20)
        self.assertEqual(structure.state, Structure.State.UNKNOWN)
        self.assertEqual(structure.eve_planet_id, 40161472)

        # verify attributes for POCO details
        details = structure.poco_details
        self.assertEqual(details.alliance_tax_rate, 0.02)
        self.assertTrue(details.allow_access_with_standings)
        self.assertTrue(details.allow_alliance_access)
        self.assertEqual(details.bad_standing_tax_rate, 0.3)
        self.assertEqual(details.corporation_tax_rate, 0.02)
        self.assertEqual(details.excellent_standing_tax_rate, 0.02)
        self.assertEqual(details.good_standing_tax_rate, 0.02)
        self.assertEqual(details.neutral_standing_tax_rate, 0.02)
        self.assertEqual(details.reinforce_exit_end, 21)
        self.assertEqual(details.reinforce_exit_start, 19)
        self.assertEqual(details.standing_level, PocoDetails.StandingLevel.TERRIBLE)
        self.assertEqual(details.terrible_standing_tax_rate, 0.5)

        # empty name for POCO with no asset data
        structure = Structure.objects.get(id=1200000000099)
        self.assertEqual(structure.name, "")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_can_sync_starbases(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()

        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)

        # must contain all expected structures
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

        # verify attributes for POS
        structure = Structure.objects.get(id=1300000000001)
        self.assertEqual(structure.name, "Home Sweat Home")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 16213)
        self.assertEqual(structure.state, Structure.State.POS_ONLINE)
        self.assertEqual(structure.eve_moon_id, 40161465)
        self.assertEqual(
            structure.state_timer_end, datetime(2020, 4, 5, 7, 0, 0, tzinfo=utc)
        )
        self.assertAlmostEqual(
            structure.fuel_expires_at,
            now() + timedelta(hours=24),
            delta=timedelta(seconds=30),
        )

        structure = Structure.objects.get(id=1300000000002)
        self.assertEqual(structure.name, "Bat cave")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 20061)
        self.assertEqual(structure.state, Structure.State.POS_OFFLINE)
        self.assertEqual(structure.eve_moon_id, 40161466)
        self.assertEqual(
            structure.unanchors_at, datetime(2020, 5, 5, 7, 0, 0, tzinfo=utc)
        )
        self.assertIsNone(structure.fuel_expires_at)

        structure = Structure.objects.get(id=1300000000003)
        self.assertEqual(structure.name, "Panic Room")
        self.assertEqual(structure.eve_solar_system_id, 30000474)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 20062)
        self.assertEqual(structure.state, Structure.State.POS_ONLINE)
        self.assertEqual(structure.eve_moon_id, 40029527)
        # self.assertGreaterEqual(
        #     structure.fuel_expires_at,
        #     now() + timedelta(hours=133) - timedelta(seconds=10),
        # )
        # self.assertLessEqual(
        #     structure.fuel_expires_at,
        #     now() + timedelta(hours=133) + timedelta(seconds=10),
        # )
        self.assertAlmostEqual(
            structure.fuel_expires_at,
            now() + timedelta(hours=133, minutes=20),
            delta=timedelta(seconds=30),
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    @patch(MODULE_PATH + ".notify", spec=True)
    def test_can_sync_all_structures_and_notify_user(self, mock_notify, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)

        # when
        owner.update_structures_esi(user=self.user)

        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)

        # must contain all expected structures
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1200000000099,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

        # user report has been sent
        self.assertTrue(mock_notify.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_handle_owner_without_structures(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        user, _ = create_user_from_evecharacter(
            1005,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner = create_owner_from_user(user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)
        self.assertSetEqual(owner.structures.ids(), set())

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_break_when_endpoint_for_fetching_upwell_structures_is_down(
        self, mock_esi
    ):
        # given
        def my_callback(**kwargs):
            raise HTTPInternalServerError(
                response=BravadoResponseStub(500, "Test exception")
            )

        callbacks = [
            EsiEndpointCallback(
                "Corporation",
                "get_corporations_corporation_id_structures",
                callback=my_callback,
            )
        ]
        mock_esi.client = generate_esi_client_stub(callbacks=callbacks)
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = {
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1200000000099,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_break_on_http_error_when_fetching_custom_offices(
        self, mock_esi
    ):
        # given
        def my_callback(**kwargs):
            raise HTTPInternalServerError(
                response=BravadoResponseStub(500, "Test exception")
            )

        callbacks = [
            EsiEndpointCallback(
                "Planetary_Interaction",
                "get_corporations_corporation_id_customs_offices",
                callback=my_callback,
            )
        ]
        mock_esi.client = generate_esi_client_stub(callbacks=callbacks)
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        structure_ids = {x["id"] for x in owner.structures.values("id")}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_not_break_on_http_error_when_fetching_star_bases(self, mock_esi):
        # given
        def my_callback(**kwargs):
            raise HTTPInternalServerError(
                response=BravadoResponseStub(500, "Test exception")
            )

        callbacks = [
            EsiEndpointCallback(
                "Corporation",
                "get_corporations_corporation_id_starbases",
                callback=my_callback,
            )
        ]
        mock_esi.client = generate_esi_client_stub(callbacks=callbacks)
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(MODULE_PATH + ".notify", spec=True)
    def test_should_remove_character_if_not_director_when_updating_starbases(
        self, mock_notify, mock_esi
    ):
        # given
        def my_callback(**kwargs):
            raise HTTPForbidden(BravadoResponseStub(status_code=403, reason="Test"))

        callbacks = [
            EsiEndpointCallback(
                "Corporation",
                "get_corporations_corporation_id_starbases",
                callback=my_callback,
            )
        ]
        mock_esi.client = generate_esi_client_stub(callbacks=callbacks)
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        self.assertTrue(mock_notify)
        self.assertEqual(owner.characters.count(), 0)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_update_will_not_break_on_http_error_from_structure_info(self, mock_esi):
        # given
        def my_callback(**kwargs):
            raise HTTPInternalServerError(
                BravadoResponseStub(status_code=500, reason="Test")
            )

        callbacks = [
            EsiEndpointCallback(
                "Universe",
                "get_universe_structures_structure_id",
                callback=my_callback,
            )
        ]
        mock_esi.client = generate_esi_client_stub(callbacks=callbacks)
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.is_structure_sync_fresh)
        structure = Structure.objects.get(id=1000000000002)
        self.assertEqual(structure.name, "(no data)")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_remove_old_upwell_structures(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000004, name="delete-me")
        # when
        owner.update_structures_esi()
        # then
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_remove_old_pocos(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)
        create_poco(owner=owner, id=1000000000004, name="delete-me")
        # when
        owner.update_structures_esi()
        # then
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1200000000099,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_remove_old_starbases(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)
        create_starbase(owner=owner, id=1300000000099, name="delete-me")
        # when
        owner.update_structures_esi()
        # then
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_tags_are_not_modified_by_update(self, mock_esi):
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)

        # run update task with all structures
        owner.update_structures_esi()
        # should contain the right structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

        # adding tags
        tag_a = StructureTag.objects.get(name="tag_a")
        s = Structure.objects.get(id=1000000000001)
        s.tags.add(tag_a)
        s.save()

        # run update task 2nd time
        owner.update_structures_esi()

        # should still contain alls structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

        # should still contain the tag
        s_new = Structure.objects.get(id=1000000000001)
        self.assertEqual(s_new.tags.get(name="tag_a"), tag_a)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_not_delete_existing_upwell_structures_when_update_failed(
        self, mock_esi
    ):
        # given
        def my_callback(**kwargs):
            raise HTTPInternalServerError(
                BravadoResponseStub(status_code=500, reason="Test")
            )

        callbacks = [
            EsiEndpointCallback(
                "Corporation",
                "get_corporations_corporation_id_structures",
                callback=my_callback,
            )
        ]
        mock_esi.client = generate_esi_client_stub(callbacks=callbacks)
        owner = create_owner_from_user(self.user)
        create_upwell_structure(owner=owner, id=1000000000001)
        create_upwell_structure(owner=owner, id=1000000000002)
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = {1000000000001, 1000000000002}
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_delete_existing_pocos_when_update_failed(self, mock_esi):
        # given
        def my_callback(**kwargs):
            raise HTTPInternalServerError(
                BravadoResponseStub(status_code=500, reason="Test")
            )

        callbacks = [
            EsiEndpointCallback(
                "Planetary_Interaction",
                "get_corporations_corporation_id_customs_offices",
                callback=my_callback,
            ),
        ]
        mock_esi.client = generate_esi_client_stub(callbacks=callbacks)
        owner = create_owner_from_user(self.user)
        create_poco(owner=owner, id=1200000000003)
        create_poco(owner=owner, id=1200000000004)
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_not_delete_existing_starbases_when_update_failed(self, mock_esi):
        # given
        def my_callback(**kwargs):
            raise HTTPInternalServerError(
                BravadoResponseStub(status_code=500, reason="Test")
            )

        callbacks = [
            EsiEndpointCallback(
                "Corporation",
                "get_corporations_corporation_id_starbases",
                callback=my_callback,
            )
        ]
        mock_esi.client = generate_esi_client_stub(callbacks=callbacks)
        owner = create_owner_from_user(self.user)
        create_starbase(owner=owner, id=1300000000001)
        create_starbase(owner=owner, id=1300000000002)
        # when
        owner.update_structures_esi()
        # then
        # self.assertFalse(owner.is_structure_sync_fresh)
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_should_remove_outdated_services(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)
        structure = create_upwell_structure(owner=owner, id=1000000000002)
        create_structure_service(structure=structure, name="Clone Bay")
        # when
        owner.update_structures_esi()
        # then
        structure.refresh_from_db()
        services = {
            obj.name for obj in StructureService.objects.filter(structure=structure)
        }
        self.assertEqual(services, {"Moon Drilling", "Reprocessing"})

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_have_empty_name_if_not_match_with_planets(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)
        EvePlanet.objects.all().delete()
        # when
        owner.update_structures_esi()
        # then
        self.assertTrue(owner.is_structure_sync_fresh)
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_define_poco_name_from_planet_type_if_found(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, "Planet (Barren)")

    @patch(MODULE_PATH + ".STRUCTURES_DEFAULT_LANGUAGE", "de")
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_define_poco_name_from_planet_type_localized(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        owner = create_owner_from_user(self.user)
        # when
        owner.update_structures_esi()
        # then
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, "Planet (Barren)_de")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(
        "structures.models.structures.STRUCTURES_FEATURE_REFUELED_NOTIFICIATIONS", True
    )
    @patch("structures.models.notifications.Webhook.send_message")
    def test_should_send_refueled_notification_when_fuel_level_increased(
        self, mock_send_message, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        webhook = Webhook.objects.create(
            name="Webhook 1",
            url="webhook-1",
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA],
            is_active=True,
        )
        owner = create_owner_from_user(self.user)
        owner.webhooks.add(webhook)
        owner.update_structures_esi()
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = datetime(2020, 3, 3, 0, 0, tzinfo=utc)
        structure.save()
        # when
        with patch("structures.models.structures.now") as now:
            now.return_value = datetime(2020, 3, 2, 0, 0, tzinfo=utc)
            owner.update_structures_esi()
        # then
        self.assertTrue(mock_send_message.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(
        "structures.models.structures.STRUCTURES_FEATURE_REFUELED_NOTIFICIATIONS", True
    )
    @patch("structures.models.notifications.Webhook.send_message")
    def test_should_not_send_refueled_notification_when_fuel_level_unchanged(
        self, mock_send_message, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        webhook = Webhook.objects.create(
            name="Webhook 1",
            url="webhook-1",
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA],
            is_active=True,
        )
        owner = create_owner_from_user(self.user)
        owner.webhooks.add(webhook)
        with patch("structures.models.structures.now") as now:
            now.return_value = datetime(2020, 3, 2, 0, 0, tzinfo=utc)
            owner.update_structures_esi()
            # when
            owner.update_structures_esi()
        # then
        self.assertFalse(mock_send_message.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch("structures.models.notifications.Webhook.send_message")
    def test_should_remove_outdated_fuel_alerts_when_fuel_level_changed(
        self, mock_send_message, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        webhook = Webhook.objects.create(
            name="Webhook 1",
            url="webhook-1",
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA],
            is_active=True,
        )
        owner = create_owner_from_user(self.user)
        owner.webhooks.add(webhook)
        owner.update_structures_esi()
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = datetime(2020, 3, 3, 0, 0, tzinfo=utc)
        structure.save()
        config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure.structure_fuel_alerts.create(config=config, hours=12)
        # when
        with patch("structures.models.structures.now") as now:
            now.return_value = datetime(2020, 3, 2, 0, 0, tzinfo=utc)
            owner.update_structures_esi()
        # then
        self.assertEqual(structure.structure_fuel_alerts.count(), 0)

    # @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    # @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    # def test_should_notify_admins_when_service_is_restored(
    #     self, mock_esi_client
    # ):
    #     # given
    #     mock_esi_client.side_effect = esi_mock_client
    #     owner = create_owner_from_user(self.user)
    #     owner.is_structure_sync_fresh = False
    #     owner.save()
    #     # when
    #     owner.update_structures_esi()
    #     # then
    #     owner.refresh_from_db()
    #     self.assertTrue(owner.is_structure_sync_fresh)
