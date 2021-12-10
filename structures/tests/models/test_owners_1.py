import datetime as dt
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

from bravado.exception import HTTPForbidden, HTTPInternalServerError

from django.utils.timezone import now, utc
from esi.errors import TokenError
from esi.models import Token

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from app_utils.testing import (
    BravadoResponseStub,
    NoSocketsTestCase,
    create_user_from_evecharacter,
)

from ...models import (
    EveCategory,
    EveConstellation,
    EveGroup,
    EveMoon,
    EvePlanet,
    EveRegion,
    EveSolarSystem,
    EveSovereigntyMap,
    EveType,
    StructureFuelAlertConfig,
    NotificationType,
    Owner,
    OwnerCharacter,
    PocoDetails,
    Structure,
    StructureService,
    StructureTag,
    Webhook,
)
from .. import to_json
from ..testdata import (
    create_structures,
    entities_testdata,
    esi_corp_structures_data,
    esi_data,
    esi_get_corporations_corporation_id_customs_offices,
    esi_get_corporations_corporation_id_starbases,
    esi_get_corporations_corporation_id_starbases_starbase_id,
    esi_get_corporations_corporation_id_structures,
    esi_get_universe_structures_structure_id,
    esi_mock_client,
    esi_post_corporations_corporation_id_assets_locations,
    esi_post_corporations_corporation_id_assets_names,
    load_entities,
    set_owner_character,
)
from ..testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "structures.models.owners"


def create_owner(
    corporation: EveCorporationInfo, character_ownership: CharacterOwnership
):
    owner = Owner.objects.create(corporation=corporation)
    owner.add_character(character_ownership)
    return owner


class TestOwner(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)

    def setUp(self) -> None:
        self.owner.is_alliance_main = True
        self.owner.save()

    def test_str(self):
        # when
        result = str(self.owner)
        # then
        self.assertEqual(result, "Wayne Technologies")

    def test_repr(self):
        # when
        result = repr(self.owner)
        # then
        self.assertEqual(
            result, f"Owner(pk={self.owner.pk}, corporation='Wayne Technologies')"
        )

    @patch(MODULE_PATH + ".STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES", 30)
    def test_is_structure_sync_fresh(self):
        # no errors and recent sync
        self.owner.structures_last_update_at = now()
        self.assertTrue(self.owner.is_structure_sync_fresh)

        # no errors and sync within grace period
        self.owner.structures_last_update_at = now() - timedelta(minutes=29)
        self.assertTrue(self.owner.is_structure_sync_fresh)

        # no error, but no sync within grace period
        self.owner.structures_last_update_at = now() - timedelta(minutes=31)
        self.assertFalse(self.owner.is_structure_sync_fresh)

    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 30)
    def test_is_notification_sync_fresh(self):
        # no errors and recent sync
        self.owner.notifications_last_update_at = now()
        self.assertTrue(self.owner.is_notification_sync_fresh)

        # no errors and sync within grace period
        self.owner.notifications_last_update_at = now() - timedelta(minutes=29)
        self.assertTrue(self.owner.is_notification_sync_fresh)

        # no error, but no sync within grace period
        self.owner.notifications_last_update_at = now() - timedelta(minutes=31)
        self.assertFalse(self.owner.is_notification_sync_fresh)

    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 30)
    def test_is_forwarding_sync_fresh(self):
        # no errors and recent sync
        self.owner.forwarding_last_update_at = now()
        self.assertTrue(self.owner.is_forwarding_sync_fresh)

        # no errors and sync within grace period
        self.owner.forwarding_last_update_at = now() - timedelta(minutes=29)
        self.assertTrue(self.owner.is_forwarding_sync_fresh)

        # no error, but no sync within grace period
        self.owner.forwarding_last_update_at = now() - timedelta(minutes=31)
        self.assertFalse(self.owner.is_forwarding_sync_fresh)

    @patch(MODULE_PATH + ".STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES", 30)
    def test_is_assets_sync_fresh(self):
        # no errors and recent sync
        self.owner.assets_last_update_at = now()
        self.assertTrue(self.owner.is_assets_sync_fresh)

        # no errors and sync within grace period
        self.owner.assets_last_update_at = now() - timedelta(minutes=29)
        self.assertTrue(self.owner.is_assets_sync_fresh)

        # no error, but no sync within grace period
        self.owner.assets_last_update_at = now() - timedelta(minutes=31)
        self.assertFalse(self.owner.is_assets_sync_fresh)

    @patch(MODULE_PATH + ".STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES", 30)
    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 30)
    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 30)
    def test_is_all_syncs_ok(self):
        self.owner.structures_last_update_at = now()
        self.owner.notifications_last_update_at = now()
        self.owner.forwarding_last_update_at = now()
        self.owner.assets_last_update_at = now()
        self.assertTrue(self.owner.are_all_syncs_ok)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    def test_get_esi_scopes_pocos_off(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                "esi-corporations.read_structures.v1",
                "esi-universe.read_structures.v1",
                "esi-characters.read_notifications.v1",
                "esi-assets.read_corporation_assets.v1",
            },
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    def test_get_esi_scopes_pocos_on(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                "esi-corporations.read_structures.v1",
                "esi-universe.read_structures.v1",
                "esi-characters.read_notifications.v1",
                "esi-planets.read_customs_offices.v1",
                "esi-assets.read_corporation_assets.v1",
            },
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    def test_get_esi_scopes_starbases_on(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                "esi-corporations.read_structures.v1",
                "esi-universe.read_structures.v1",
                "esi-characters.read_notifications.v1",
                "esi-corporations.read_starbases.v1",
                "esi-assets.read_corporation_assets.v1",
            },
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    def test_get_esi_scopes_starbases_and_custom_offices(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                "esi-corporations.read_structures.v1",
                "esi-universe.read_structures.v1",
                "esi-characters.read_notifications.v1",
                "esi-corporations.read_starbases.v1",
                "esi-planets.read_customs_offices.v1",
                "esi-assets.read_corporation_assets.v1",
            },
        )

    def test_should_add_new_character(self):
        # given
        owner = Owner.objects.get(corporation__corporation_id=2002)
        _, character_ownership = create_user_from_evecharacter(
            1003,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        # when
        result = owner.add_character(character_ownership)
        # then
        self.assertIsInstance(result, OwnerCharacter)
        self.assertEqual(result.owner, owner)
        self.assertEqual(result.character_ownership, character_ownership)
        self.assertIsNone(result.notifications_last_used_at)

    def test_should_not_overwrite_existing_characters(self):
        # given
        character = self.owner.characters.first()
        my_dt = datetime(year=2021, month=2, day=11, hour=12, tzinfo=utc)
        character.notifications_last_used_at = my_dt
        character.save()
        # when
        result = self.owner.add_character(character.character_ownership)
        # then
        self.assertIsInstance(result, OwnerCharacter)
        self.assertEqual(result.owner, self.owner)
        self.assertEqual(result.character_ownership, character.character_ownership)
        self.assertEqual(result.notifications_last_used_at, my_dt)

    def test_should_prevent_adding_character_from_other_corporation(self):
        # given
        _, character_ownership = create_user_from_evecharacter(
            1003,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        # when
        with self.assertRaises(ValueError):
            self.owner.add_character(character_ownership)

    def test_should_add_character_to_existing_set(self):
        # given
        owner = Owner.objects.get(corporation__corporation_id=2102)
        _, character_ownership_1011 = create_user_from_evecharacter(
            1011,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner.add_character(character_ownership_1011)
        _, character_ownership_1102 = create_user_from_evecharacter(
            1102,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        # when
        owner.add_character(character_ownership_1102)
        # then
        owner_character_pks = set(
            owner.characters.values_list("character_ownership__pk", flat=True)
        )
        expected_pks = {character_ownership_1011.pk, character_ownership_1102.pk}
        self.assertSetEqual(owner_character_pks, expected_pks)

    def test_should_count_characters(self):
        # given
        owner = Owner.objects.get(corporation__corporation_id=2102)
        _, character_ownership_1011 = create_user_from_evecharacter(
            1011,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner.add_character(character_ownership_1011)
        _, character_ownership_1102 = create_user_from_evecharacter(
            1102,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner.add_character(character_ownership_1102)
        # when
        result = owner.characters_count()
        # then
        self.assertEqual(result, 2)

    def test_should_count_characters_when_empty(self):
        # given
        owner = Owner.objects.get(corporation__corporation_id=2102)
        # when
        result = owner.characters_count()
        # then
        self.assertEqual(result, 0)

    def test_should_ensure_only_one_owner_is_alliance_main_1(self):
        # given
        self.assertTrue(self.owner.is_alliance_main)
        owner = Owner.objects.get(corporation__corporation_id=2002)
        # when
        owner.is_alliance_main = True
        owner.save()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_alliance_main)
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_alliance_main)

    def test_should_ensure_only_one_owner_is_alliance_main_2(self):
        # given
        self.assertTrue(self.owner.is_alliance_main)
        owner = Owner.objects.get(corporation__corporation_id=2007)
        # when
        owner.is_alliance_main = True
        owner.save()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_alliance_main)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_alliance_main)

    def test_should_ensure_only_one_owner_is_alliance_main_3(self):
        # given
        self.assertTrue(self.owner.is_alliance_main)
        owner_2103 = Owner.objects.get(corporation__corporation_id=2102)
        owner_2103.is_alliance_main = True
        owner_2103.save()
        owner_2102 = Owner.objects.get(corporation__corporation_id=2102)
        # when
        owner_2102.is_alliance_main = True
        owner_2102.save()
        # then
        owner_2102.refresh_from_db()
        self.assertTrue(owner_2102.is_alliance_main)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_alliance_main)
        owner_2103.refresh_from_db()
        self.assertTrue(owner_2103.is_alliance_main)


@patch(MODULE_PATH + ".notify")
@patch(MODULE_PATH + ".notify_admins")
class TestOwnerFetchToken(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([EveCorporationInfo, EveCharacter])
        load_eveuniverse()
        cls.character = EveCharacter.objects.get(character_id=1001)
        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)

    def test_should_return_correct_token(self, mock_notify_admins, mock_notify):
        # given
        user, character_ownership = create_user_from_evecharacter(
            1001,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner = Owner.objects.create(corporation=self.corporation)
        owner.add_character(character_ownership)
        # when
        token = owner.fetch_token()
        # then
        self.assertIsInstance(token, Token)
        self.assertEqual(token.user, user)
        self.assertEqual(token.character_id, 1001)
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            set(token.scopes.values_list("name", flat=True)),
        )
        self.assertFalse(mock_notify_admins.called)
        self.assertFalse(mock_notify.called)
        self.assertEqual(owner.characters.count(), 1)

    def test_raise_error_when_no_sync_char_defined(
        self, mock_notify_admins, mock_notify
    ):
        # given
        owner = Owner.objects.create(corporation=self.corporation)
        # when/then
        with self.assertRaises(TokenError):
            owner.fetch_token()
        self.assertFalse(mock_notify_admins.called)
        self.assertFalse(mock_notify.called)

    def test_raise_error_when_user_has_no_permission_and_delete_character(
        self, mock_notify_admins, mock_notify
    ):
        # given
        _, character_ownership = create_user_from_evecharacter(
            1001, scopes=Owner.get_esi_scopes()
        )
        owner = Owner.objects.create(corporation=self.corporation)
        owner.add_character(character_ownership)
        # when/then
        with self.assertRaises(TokenError):
            owner.fetch_token()
        self.assertTrue(mock_notify_admins.called)
        self.assertTrue(mock_notify.called)
        self.assertEqual(owner.characters.count(), 0)

    def test_raise_error_when_token_not_found_and_delete_character(
        self, mock_notify_admins, mock_notify
    ):
        # given
        with patch(MODULE_PATH + ".Token.objects.filter") as my_mock:
            my_mock.return_value = None
            user, character_ownership = create_user_from_evecharacter(
                1001,
                permissions=["structures.add_structure_owner"],
                scopes=Owner.get_esi_scopes(),
            )
        owner = Owner.objects.create(corporation=self.corporation)
        owner.add_character(character_ownership)
        user.token_set.first().scopes.clear()
        # when/then
        with self.assertRaises(TokenError):
            owner.fetch_token()
        self.assertTrue(mock_notify_admins.called)
        self.assertTrue(mock_notify.called)
        self.assertEqual(owner.characters.count(), 0)

    def test_raise_error_when_character_no_longer_a_corporation_member_and_delete_it(
        self, mock_notify_admins, mock_notify
    ):
        # given
        _, character_ownership = create_user_from_evecharacter(
            1011,
            scopes=Owner.get_esi_scopes(),
            permissions=["structures.add_structure_owner"],
        )
        owner = Owner.objects.create(corporation=self.corporation)
        owner.characters.create(character_ownership=character_ownership)
        # when/then
        with self.assertRaises(TokenError):
            owner.fetch_token()
        self.assertTrue(mock_notify_admins.called)
        self.assertTrue(mock_notify.called)
        self.assertEqual(owner.characters.count(), 0)

    def test_should_delete_invalid_characters_and_return_token_from_valid_char(
        self, mock_notify_admins, mock_notify
    ):
        # given
        owner = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2102)
        )
        user, character_ownership_1011 = create_user_from_evecharacter(
            1011,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        my_character = owner.add_character(character_ownership_1011)
        my_character.notifications_last_used_at = dt.datetime(
            2021, 1, 1, 1, 2, tzinfo=utc
        )
        my_character.save()
        _, character_ownership_1102 = create_user_from_evecharacter(
            1102, scopes=Owner.get_esi_scopes()
        )
        my_character = owner.add_character(character_ownership_1102)
        my_character.notifications_last_used_at = dt.datetime(
            2021, 1, 1, 1, 1, tzinfo=utc
        )
        my_character.save()
        # when
        token = owner.fetch_token()
        # then
        self.assertIsInstance(token, Token)
        self.assertEqual(token.user, user)
        self.assertTrue(mock_notify_admins.called)
        self.assertTrue(mock_notify.called)
        self.assertEqual(owner.characters.count(), 1)

    def test_should_rotate_through_characters_for_notification(
        self, mock_notify_admins, mock_notify
    ):
        # given
        owner = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2102)
        )
        _, character_ownership_1011 = create_user_from_evecharacter(
            1011,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        my_character = owner.add_character(character_ownership_1011)
        my_character.notifications_last_used_at = dt.datetime(
            2021, 1, 1, 0, 5, tzinfo=utc
        )
        my_character.save()
        _, character_ownership_1102 = create_user_from_evecharacter(
            1102,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        my_character = owner.add_character(character_ownership_1102)
        my_character.notifications_last_used_at = dt.datetime(
            2021, 1, 1, 0, 0, tzinfo=utc
        )
        my_character.save()
        tokens_received = list()
        # when
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.NOTIFICATIONS,
                ignore_schedule=True,
            ).character_id
        )
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.NOTIFICATIONS,
                ignore_schedule=True,
            ).character_id
        )
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.NOTIFICATIONS,
                ignore_schedule=True,
            ).character_id
        )
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.NOTIFICATIONS,
                ignore_schedule=True,
            ).character_id
        )
        # then
        self.assertListEqual(tokens_received, [1102, 1011, 1102, 1011])

    def test_should_rotate_through_characters_for_structures(
        self, mock_notify_admins, mock_notify
    ):
        # given
        owner = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2102)
        )
        _, character_ownership_1011 = create_user_from_evecharacter(
            1011,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        my_character = owner.add_character(character_ownership_1011)
        my_character.structures_last_used_at = dt.datetime(2021, 1, 1, 0, 5, tzinfo=utc)
        my_character.save()
        _, character_ownership_1102 = create_user_from_evecharacter(
            1102,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        my_character = owner.add_character(character_ownership_1102)
        my_character.structures_last_used_at = dt.datetime(2021, 1, 1, 0, 0, tzinfo=utc)
        my_character.save()
        tokens_received = list()
        # when
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.STRUCTURES,
                ignore_schedule=True,
            ).character_id
        )
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.STRUCTURES,
                ignore_schedule=True,
            ).character_id
        )
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.STRUCTURES,
                ignore_schedule=True,
            ).character_id
        )
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.STRUCTURES,
                ignore_schedule=True,
            ).character_id
        )
        # then
        self.assertListEqual(tokens_received, [1102, 1011, 1102, 1011])

    def test_should_rotate_through_characters_based_on_schedule(
        self, mock_notify_admins, mock_notify
    ):
        # given
        owner = Owner.objects.create(
            corporation=EveCorporationInfo.objects.get(corporation_id=2102)
        )
        _, character_ownership_1011 = create_user_from_evecharacter(
            1011,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        my_character = owner.add_character(character_ownership_1011)
        my_character.notifications_last_used_at = dt.datetime(
            2021, 1, 1, 0, 1, tzinfo=utc
        )
        my_character.save()
        _, character_ownership_1102 = create_user_from_evecharacter(
            1102,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        my_character = owner.add_character(character_ownership_1102)
        my_character.notifications_last_used_at = dt.datetime(
            2021, 1, 1, 0, 0, tzinfo=utc
        )
        my_character.save()
        tokens_received = list()
        # when
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.NOTIFICATIONS
            ).character_id
        )
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.NOTIFICATIONS
            ).character_id
        )
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.NOTIFICATIONS
            ).character_id
        )
        tokens_received.append(
            owner.fetch_token(
                rotate_characters=Owner.RotateCharactersType.NOTIFICATIONS
            ).character_id
        )
        # then
        self.assertListEqual(tokens_received, [1102, 1011, 1102, 1102])


@patch("structures.helpers.esi_fetch._esi_client")
@patch("structures.helpers.esi_fetch.sleep", lambda x: None)
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

    def setUp(self):
        # reset data that might be overridden
        esi_get_corporations_corporation_id_structures.override_data = None
        esi_get_corporations_corporation_id_starbases.override_data = None
        esi_get_corporations_corporation_id_customs_offices.override_data = None

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_can_sync_upwell_structures(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)
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
                    "name_de": "Clone Bay_de",
                    "name_ko": "Clone Bay_ko",
                    "name_ru": "Clone Bay_ru",
                    # "name_zh": "Clone Bay_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
            to_json(
                {
                    "name": "Market Hub",
                    "name_de": "Market Hub_de",
                    "name_ko": "Market Hub_ko",
                    "name_ru": "Market Hub_ru",
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
                    "name_de": x.name_de,
                    "name_ko": x.name_ko,
                    "name_ru": x.name_ru,
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
                    "name_de": "Reprocessing_de",
                    "name_ko": "Reprocessing_ko",
                    "name_ru": "Reprocessing_ru",
                    # "name_zh": "Reprocessing_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
            to_json(
                {
                    "name": "Moon Drilling",
                    "name_de": "Moon Drilling_de",
                    "name_ko": "Moon Drilling_ko",
                    "name_ru": "Moon Drilling_ru",
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
                    "name_de": x.name_de,
                    "name_ko": x.name_ko,
                    "name_ru": x.name_ru,
                    # "name_zh": x.name_zh,
                    "state": x.state,
                }
            )
            for x in structure.services.all()
        }
        self.assertEqual(services, expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_sync_pocos(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)
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
        }
        self.assertSetEqual(owner.structures.ids(), expected)
        self.assertSetEqual(
            set(PocoDetails.objects.values_list("structure_id", flat=True)),
            {
                1200000000003,
                1200000000004,
                1200000000005,
                1200000000006,
            },
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

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(MODULE_PATH + "._esi_client", name="esi_client_2")
    def test_can_sync_starbases(self, mock_esi_client_2, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        mock_esi_client_2.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)
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
    @patch(MODULE_PATH + "._esi_client", name="esi_client_2")
    @patch(MODULE_PATH + ".notify", spec=True)
    def test_can_sync_all_structures_and_notify_user(
        self, mock_notify, mock_esi_client_2, mock_esi_client
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        mock_esi_client_2.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)

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
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

        # user report has been sent
        self.assertTrue(mock_notify.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_handle_owner_without_structures(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        _, my_main_ownership = create_user_from_evecharacter(
            1005,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        my_corporation = EveCorporationInfo.objects.get(corporation_id=2005)
        owner = create_owner(my_corporation, my_main_ownership)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)
        self.assertSetEqual(owner.structures.ids(), set())

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_break_on_http_error_when_fetching_upwell_structures(
        self, mock_esi_client
    ):
        # given
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_locations = (
            esi_post_corporations_corporation_id_assets_locations
        )
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_names = (
            esi_post_corporations_corporation_id_assets_names
        )
        mock_esi_client.return_value.Planetary_Interaction.get_corporations_corporation_id_customs_offices = (
            esi_get_corporations_corporation_id_customs_offices
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_structures.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases.side_effect = (
            esi_get_corporations_corporation_id_starbases
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases_starbase_id.side_effect = (
            esi_get_corporations_corporation_id_starbases_starbase_id
        )
        mock_esi_client.return_value.Universe.get_universe_structures_structure_id.side_effect = (
            esi_get_universe_structures_structure_id
        )
        owner = create_owner(self.corporation, self.main_ownership)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = {1200000000003, 1200000000004, 1200000000005, 1200000000006}
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_break_on_http_error_when_fetching_custom_offices(
        self, mock_esi_client
    ):
        # given
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_locations = (
            esi_post_corporations_corporation_id_assets_locations
        )
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_names = (
            esi_post_corporations_corporation_id_assets_names
        )
        mock_esi_client.return_value.Planetary_Interaction.get_corporations_corporation_id_customs_offices.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_structures.side_effect = (
            esi_get_corporations_corporation_id_structures
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases.side_effect = (
            esi_get_corporations_corporation_id_starbases
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases_starbase_id.side_effect = (
            esi_get_corporations_corporation_id_starbases_starbase_id
        )
        mock_esi_client.return_value.Universe.get_universe_structures_structure_id.side_effect = (
            esi_get_universe_structures_structure_id
        )
        owner = create_owner(self.corporation, self.main_ownership)
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
    @patch(MODULE_PATH + "._esi_client", name="esi_client_2")
    def test_should_not_break_on_http_error_when_fetching_star_bases(
        self, mock_esi_client_2, mock_esi_client
    ):
        # given
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_locations = (
            esi_post_corporations_corporation_id_assets_locations
        )
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_names = (
            esi_post_corporations_corporation_id_assets_names
        )
        mock_esi_client.return_value.Planetary_Interaction.get_corporations_corporation_id_customs_offices = (
            esi_get_corporations_corporation_id_customs_offices
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_structures.side_effect = (
            esi_get_corporations_corporation_id_structures
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        mock_esi_client_2.return_value.Corporation.get_corporations_corporation_id_starbases_starbase_id.side_effect = (
            esi_get_corporations_corporation_id_starbases_starbase_id
        )
        mock_esi_client.return_value.Universe.get_universe_structures_structure_id.side_effect = (
            esi_get_universe_structures_structure_id
        )
        owner = create_owner(self.corporation, self.main_ownership)
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
    @patch(MODULE_PATH + "._esi_client", name="esi_client_2")
    def test_should_remove_character_if_not_director_when_updating_starbases(
        self, mock_esi_client_2, mock_notify, mock_esi_client
    ):
        # given
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_locations = (
            esi_post_corporations_corporation_id_assets_locations
        )
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_names = (
            esi_post_corporations_corporation_id_assets_names
        )
        mock_esi_client.return_value.Planetary_Interaction.get_corporations_corporation_id_customs_offices = (
            esi_get_corporations_corporation_id_customs_offices
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_structures.side_effect = (
            esi_get_corporations_corporation_id_structures
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases.side_effect = HTTPForbidden(
            BravadoResponseStub(status_code=403, reason="Test")
        )
        mock_esi_client_2.return_value.Corporation.get_corporations_corporation_id_starbases_starbase_id.side_effect = (
            esi_get_corporations_corporation_id_starbases_starbase_id
        )
        mock_esi_client.return_value.Universe.get_universe_structures_structure_id.side_effect = (
            esi_get_universe_structures_structure_id
        )
        owner = create_owner(self.corporation, self.main_ownership)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.is_structure_sync_fresh)
        self.assertTrue(mock_notify)
        self.assertEqual(owner.characters.count(), 0)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_update_will_not_break_on_http_error_from_structure_info(
        self, mock_esi_client
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        # remove info data for structure with ID 1000000000002
        data = deepcopy(esi_data["Universe"]["get_universe_structures_structure_id"])
        del data["1000000000002"]
        esi_get_universe_structures_structure_id.override_data = data
        owner = create_owner(self.corporation, self.main_ownership)
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.is_structure_sync_fresh)
        esi_get_universe_structures_structure_id.override_data = None
        structure = Structure.objects.get(id=1000000000002)
        self.assertEqual(structure.name, "(no data)")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_removes_old_structures(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)

        # run update task with all structures
        owner.update_structures_esi()

        # should contain the right structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

        # run update task 2nd time with one less structure
        my_corp_structures_data = deepcopy(esi_corp_structures_data)
        del my_corp_structures_data["2001"][1]
        esi_get_corporations_corporation_id_structures.override_data = (
            my_corp_structures_data
        )
        owner.update_structures_esi()

        # should contain only the remaining structures
        expected = {1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_tags_are_not_modified_by_update(self, mock_esi_client):
        mock_esi_client.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)

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

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    @patch(MODULE_PATH + "._esi_client", name="esi_client_2")
    def test_should_remove_structures_not_returned_from_esi(
        self, mock_esi_client_2, mock_esi_client
    ):
        # given
        esi_get_corporations_corporation_id_structures.override_data = {"2001": []}
        esi_get_corporations_corporation_id_starbases.override_data = {"2001": []}
        esi_get_corporations_corporation_id_customs_offices.override_data = {"2001": []}
        mock_esi_client.side_effect = esi_mock_client
        mock_esi_client_2.side_effect = esi_mock_client
        create_structures(dont_load_entities=True)
        owner = Owner.objects.get(corporation__corporation_id=2001)
        owner.add_character(self.main_ownership)
        self.assertGreater(owner.structures.count(), 0)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.is_structure_sync_fresh)
        self.assertEqual(owner.structures.count(), 0)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_delete_existing_structures_when_update_failed_with_http_error(
        self, mock_esi_client
    ):
        # given
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_structures.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        mock_esi_client.return_value.Planetary_Interaction.get_corporations_corporation_id_customs_offices.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        create_structures(dont_load_entities=True)
        owner = Owner.objects.get(corporation__corporation_id=2001)
        owner.add_character(self.main_ownership)
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.is_structure_sync_fresh)
        expected = expected = {
            1000000000001,
            1000000000002,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_removes_outdated_services(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)

        # run update task with all structures
        owner.update_structures_esi()
        structure = Structure.objects.get(id=1000000000002)
        self.assertEqual(
            {x.name for x in StructureService.objects.filter(structure=structure)},
            {"Reprocessing", "Moon Drilling"},
        )

        # run update task 2nd time after removing a service
        my_corp_structures_data = deepcopy(esi_corp_structures_data)
        del my_corp_structures_data["2001"][0]["services"][0]
        esi_get_corporations_corporation_id_structures.override_data = (
            my_corp_structures_data
        )
        owner.update_structures_esi()
        # should contain only the remaining service
        structure.refresh_from_db()
        self.assertEqual(
            {x.name for x in StructureService.objects.filter(structure=structure)},
            {"Moon Drilling"},
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_have_empty_name_if_not_match_with_planets(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)
        EvePlanet.objects.all().delete()
        # when
        owner.update_structures_esi()
        # then
        self.assertTrue(owner.is_structure_sync_fresh)
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_define_poco_name_from_planet_type_if_found(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)
        # when
        owner.update_structures_esi()
        # then
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, "Planet (Barren)")

    @patch(MODULE_PATH + ".STRUCTURES_DEFAULT_LANGUAGE", "de")
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_define_poco_name_from_planet_type_localized(self, mock_esi_client):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)
        # when
        owner.update_structures_esi()
        # then
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, "Planet (Barren)_de")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_update_pocos_no_asset_name_match(self, mock_esi_client):
        # given
        esi_post_corporations_corporation_id_assets_names.override_data = {"2001": []}
        mock_esi_client.side_effect = esi_mock_client
        owner = create_owner(self.corporation, self.main_ownership)
        EvePlanet.objects.all().delete()
        # when
        owner.update_structures_esi()
        # then
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "")
        esi_post_corporations_corporation_id_assets_names.override_data = None

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(
        "structures.models.structures.STRUCTURES_FEATURE_REFUELED_NOTIFICIATIONS", True
    )
    @patch("structures.models.notifications.Webhook.send_message")
    def test_should_send_refueled_notification_when_fuel_level_increased(
        self, mock_send_message, mock_esi_client
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        webhook = Webhook.objects.create(
            name="Webhook 1",
            url="webhook-1",
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA],
            is_active=True,
        )
        owner = create_owner(self.corporation, self.main_ownership)
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
        self, mock_send_message, mock_esi_client
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        webhook = Webhook.objects.create(
            name="Webhook 1",
            url="webhook-1",
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA],
            is_active=True,
        )
        owner = create_owner(self.corporation, self.main_ownership)
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
        self, mock_send_message, mock_esi_client
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        webhook = Webhook.objects.create(
            name="Webhook 1",
            url="webhook-1",
            notification_types=[NotificationType.STRUCTURE_REFUELED_EXTRA],
            is_active=True,
        )
        owner = create_owner(self.corporation, self.main_ownership)
        owner.webhooks.add(webhook)
        owner.update_structures_esi()
        structure = Structure.objects.get(id=1000000000001)
        structure.fuel_expires_at = datetime(2020, 3, 3, 0, 0, tzinfo=utc)
        structure.save()
        config = StructureFuelAlertConfig.objects.create(start=48, end=0, repeat=12)
        structure.fuel_alerts.create(config=config, hours=12)
        # when
        with patch("structures.models.structures.now") as now:
            now.return_value = datetime(2020, 3, 2, 0, 0, tzinfo=utc)
            owner.update_structures_esi()
        # then
        self.assertEqual(structure.fuel_alerts.count(), 0)

    # @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    # @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    # def test_should_notify_admins_when_service_is_restored(
    #     self, mock_esi_client
    # ):
    #     # given
    #     mock_esi_client.side_effect = esi_mock_client
    #     owner = create_owner(self.corporation, self.main_ownership)
    #     owner.is_structure_sync_fresh = False
    #     owner.save()
    #     # when
    #     owner.update_structures_esi()
    #     # then
    #     owner.refresh_from_db()
    #     self.assertTrue(owner.is_structure_sync_fresh)
