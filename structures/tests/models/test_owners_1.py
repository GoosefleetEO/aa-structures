import datetime as dt
from datetime import datetime, timedelta
from unittest.mock import patch

from django.utils.timezone import now, utc
from esi.errors import TokenError
from esi.models import Token
from eveuniverse.models import EveSolarSystem

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from ...models import Owner, OwnerCharacter
from ..testdata.factories import create_owner_from_user
from ..testdata.helpers import create_structures, load_entities, set_owner_character
from ..testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "structures.models.owners"


class TestOwner(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
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
        owner_2103 = Owner.objects.get(corporation__corporation_id=2103)
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


class TestOwnerHasSov(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        user, _ = create_user_from_evecharacter(
            1001, permissions=["structures.add_structure_owner"]
        )
        cls.owner = create_owner_from_user(user=user)

    def test_should_return_true_when_owner_has_sov(self):
        # given
        system = EveSolarSystem.objects.get(name="1-PGSG")
        # when/then
        self.assertTrue(self.owner.has_sov(system))

    def test_should_return_false_when_owner_has_no_sov(self):
        # given
        system = EveSolarSystem.objects.get(name="A-C5TC")
        # when/then
        self.assertFalse(self.owner.has_sov(system))

    def test_should_return_false_when_owner_is_outside_nullsec(self):
        # given
        system = EveSolarSystem.objects.get(name="Amamake")
        # when/then
        self.assertFalse(self.owner.has_sov(system))


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


class TestOwnerCharacters(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)

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


@patch(MODULE_PATH + ".notify", spec=True)
@patch(MODULE_PATH + ".notify_admins", spec=True)
class TestOwnerDeleteCharacter(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([EveCorporationInfo, EveCharacter])
        load_eveuniverse()
        cls.character = EveCharacter.objects.get(character_id=1001)
        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)

    def test_should_delete_character_and_notify(self, mock_notify_admins, mock_notify):
        # given
        user, character_ownership = create_user_from_evecharacter(
            1001,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner = Owner.objects.create(corporation=self.corporation)
        character = owner.add_character(character_ownership)
        # when
        owner.delete_character(character=character, error="dummy error")
        # then
        self.assertEqual(owner.characters.count(), 0)
        self.assertTrue(mock_notify_admins.called)
        _, kwargs = mock_notify_admins.call_args
        self.assertIn("dummy error", kwargs["message"])
        self.assertEqual(kwargs["level"], "danger")
        self.assertTrue(mock_notify.called)
        _, kwargs = mock_notify.call_args
        self.assertIn("dummy error", kwargs["message"])
        self.assertEqual(kwargs["user"], user)
        self.assertEqual(kwargs["level"], "warning")

    def test_should_not_delete_when_errors_are_allowed(
        self, mock_notify_admins, mock_notify
    ):
        # given
        _, character_ownership = create_user_from_evecharacter(
            1001,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner = Owner.objects.create(corporation=self.corporation)
        character = owner.add_character(character_ownership)
        # when
        owner.delete_character(
            character=character, error="dummy error", max_allowed_errors=1
        )
        # then
        character.refresh_from_db()
        self.assertEqual(character.error_count, 1)
        self.assertFalse(mock_notify_admins.called)
        self.assertFalse(mock_notify.called)
