from django.utils import translation

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from app_utils.testing import NoSocketsTestCase

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
)
from ...models.eveuniverse import EveUniverse
from ..testdata import load_entities

MODULE_PATH = "structures.models.eveuniverse"


class TestEveUniverse(NoSocketsTestCase):
    def test_field_names_1(self):
        expected = {"name"}
        self.assertEqual(EveCategory._field_names_not_pk(), expected)

    def test_field_names_2(self):
        expected = {"name", "eve_category"}
        self.assertEqual(EveGroup._field_names_not_pk(), expected)

    def test_field_names_3(self):
        expected = {"name", "eve_constellation", "security_status"}
        self.assertEqual(EveSolarSystem._field_names_not_pk(), expected)

    def test_fk_mappings_1(self):
        expected = {"eve_category": ("category_id", EveCategory)}
        self.assertEqual(EveGroup._fk_mappings(), expected)

    def test_eve_universe_meta_attr_normal(self):
        expected = "type_id"
        self.assertEqual(EveType._eve_universe_meta_attr("esi_pk"), expected)

    def test_eve_universe_meta_attr_key_not_defined(self):
        self.assertIsNone(EveType._eve_universe_meta_attr("not_defined"))

    def test_eve_universe_meta_attr_key_not_defined_but_mandatory(self):
        with self.assertRaises(ValueError):
            EveType._eve_universe_meta_attr("not_defined", is_mandatory=True)

    def test_eve_universe_meta_attr_class_not_defined(self):
        with self.assertRaises(ValueError):
            EveUniverse._eve_universe_meta_attr("esi_pk")

    def test_has_location_true_for_normal_models(self):
        self.assertTrue(EveType.has_esi_localization())

    def test_has_localization_false_if_set_false(self):
        self.assertFalse(EvePlanet.has_esi_localization())


class TestEveUniverseLocalization(NoSocketsTestCase):
    def setUp(self):
        self.obj = EveCategory(
            id=99,
            name="Name",
            name_de="Name_de",
            name_ko="Name_ko",
            name_ru="",
            # name_zh="Name_zh",
        )

    def test_can_localized_name_de_1(self):
        with translation.override("de"):
            expected = "Name_de"
            self.assertEqual(self.obj.name_localized, expected)

    def test_can_localized_name_de_2(self):
        expected = "Name_de"
        self.assertEqual(self.obj.name_localized_for_language("de"), expected)

    def test_can_localized_name_en(self):
        with translation.override("en"):
            expected = "Name"
            self.assertEqual(self.obj.name_localized, expected)

    def test_can_localized_name_ko(self):
        with translation.override("ko"):
            expected = "Name_ko"
            self.assertEqual(self.obj.name_localized, expected)

    """
    def test_can_localized_name_zh(self):
        with translation.override("zh-hans"):
            expected = "Name_zh"
            self.assertEqual(self.obj.name_localized, expected)
    """

    def test_falls_back_to_en_for_missing_translation(self):
        with translation.override("ru"):
            expected = "Name"
            self.assertEqual(self.obj.name_localized, expected)

    def test_falls_back_to_en_for_unknown_codes(self):
        with translation.override("xx"):
            expected = "Name"
            self.assertEqual(self.obj.name_localized, expected)

    def test_set_generated_translations(self):
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
                EvePlanet,
            ]
        )
        obj = EvePlanet.objects.get(id=40161463)
        self.assertEqual(obj.name, "Amamake I")
        self.assertEqual(obj.name_de, "")
        self.assertEqual(obj.name_ko, "")
        self.assertEqual(obj.name_ru, "")
        self.assertEqual(obj.name_zh, "")
        obj.set_generated_translations()
        self.assertEqual(obj.name_de, "Amamake_de I")
        self.assertEqual(obj.name_ko, "Amamake_ko I")
        self.assertEqual(obj.name_ru, "Amamake_ru I")
        # self.assertEqual(obj.name_zh, "Amamake_zh I")


class TestEveType(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
            ]
        )
        cls.type_astrahus = EveType.objects.get(id=35832)
        cls.type_poco = EveType.objects.get(id=2233)
        cls.type_starbase = EveType.objects.get(id=16213)

    def test_str(self):
        expected = "Astrahus"
        self.assertEqual(str(self.type_astrahus), expected)

    def test_repr(self):
        expected = "EveType(id=35832, name='Astrahus')"
        self.assertEqual(repr(self.type_astrahus), expected)

    def test_is_poco(self):
        self.assertFalse(self.type_astrahus.is_poco)
        self.assertTrue(self.type_poco.is_poco)
        self.assertFalse(self.type_starbase.is_poco)

    def test_is_starbase(self):
        self.assertFalse(self.type_astrahus.is_starbase)
        self.assertFalse(self.type_poco.is_starbase)
        self.assertTrue(self.type_starbase.is_starbase)

    def test_is_upwell_structure(self):
        self.assertTrue(self.type_astrahus.is_upwell_structure)
        self.assertFalse(self.type_poco.is_upwell_structure)
        self.assertFalse(self.type_starbase.is_upwell_structure)

    def test_is_upwell_structure_data_error(self):
        # group without a category
        my_group = EveGroup.objects.create(id=299999, name="invalid group")
        my_type = EveType.objects.create(
            id=199999, name="invalid type", eve_group=my_group
        )
        self.assertFalse(my_type.is_upwell_structure)

    def test_generic_icon_url_normal(self):
        self.assertEqual(
            EveType.generic_icon_url(self.type_astrahus.id),
            "https://images.evetech.net/types/35832/icon?size=64",
        )

    def test_generic_icon_url_w_size(self):
        self.assertEqual(
            EveType.generic_icon_url(self.type_astrahus.id, 128),
            "https://images.evetech.net/types/35832/icon?size=128",
        )

    def test_generic_icon_url_invalid_size(self):
        with self.assertRaises(ValueError):
            EveType.generic_icon_url(self.type_astrahus.id, 127)

    def test_icon_url(self):
        self.assertEqual(
            EveType.generic_icon_url(self.type_astrahus.id),
            self.type_astrahus.icon_url(),
        )

    def test_is_fuel_block(self):
        obj = EveType.objects.get(id=16213)
        self.assertFalse(obj.is_fuel_block)

        obj = EveType.objects.get(id=4051)
        self.assertTrue(obj.is_fuel_block)

    def test_starbase_fuel_consumption_per_hour(self):
        # large
        obj = EveType.objects.get(id=16213)
        self.assertEqual(obj.starbase_fuel_per_hour, 40)

        # medium
        obj = EveType.objects.get(id=20061)
        self.assertEqual(obj.starbase_fuel_per_hour, 20)

        # small
        obj = EveType.objects.get(id=20062)
        self.assertEqual(obj.starbase_fuel_per_hour, 10)

        # none
        obj = EveType.objects.get(id=35832)
        self.assertIsNone(obj.starbase_fuel_per_hour)


class TestEveTypeStarBaseSize(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
            ]
        )

    def test_returns_large_for_large_control_tower(self):
        obj = EveType.objects.get(id=16213)
        expected = EveType.STARBASE_LARGE
        self.assertEqual(obj.starbase_size, expected)

    def test_returns_medium_for_medium_control_tower(self):
        obj = EveType.objects.get(id=20061)
        expected = EveType.STARBASE_MEDIUM
        self.assertEqual(obj.starbase_size, expected)

    def test_returns_small_for_small_control_tower(self):
        obj = EveType.objects.get(id=20062)
        expected = EveType.STARBASE_SMALL
        self.assertEqual(obj.starbase_size, expected)

    def test_returns_none_for_non_control_towers(self):
        obj = EveType.objects.get(id=35832)
        self.assertIsNone(obj.starbase_size)


class TestEveSolarSystem(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
                EveSovereigntyMap,
                EveCharacter,
            ]
        )

    def test_get(self):
        obj = EveSolarSystem.objects.get(id=30002537)
        self.assertEqual(obj.name, "Amamake")

    def test_high_sec_system(self):
        obj = EveSolarSystem.objects.get(id=30002506)
        self.assertTrue(obj.is_high_sec)
        self.assertFalse(obj.is_low_sec)
        self.assertFalse(obj.is_null_sec)
        self.assertFalse(obj.is_w_space)

    def test_low_sec_system(self):
        obj = EveSolarSystem.objects.get(id=30002537)
        self.assertFalse(obj.is_high_sec)
        self.assertTrue(obj.is_low_sec)
        self.assertFalse(obj.is_null_sec)
        self.assertFalse(obj.is_w_space)

    def test_null_sec_system(self):
        obj = EveSolarSystem.objects.get(id=30000474)
        self.assertFalse(obj.is_high_sec)
        self.assertFalse(obj.is_low_sec)
        self.assertTrue(obj.is_null_sec)
        self.assertFalse(obj.is_w_space)

    def test_wh_system(self):
        obj = EveSolarSystem.objects.get(id=31000005)
        self.assertFalse(obj.is_high_sec)
        self.assertFalse(obj.is_low_sec)
        self.assertFalse(obj.is_null_sec)
        self.assertTrue(obj.is_w_space)

    def test_space_type_highsec(self):
        obj = EveSolarSystem.objects.get(id=30002506)
        expected = EveSolarSystem.TYPE_HIGHSEC
        self.assertEqual(obj.space_type, expected)

    def test_space_type_lowsec(self):
        obj = EveSolarSystem.objects.get(id=30002537)
        expected = EveSolarSystem.TYPE_LOWSEC
        self.assertEqual(obj.space_type, expected)

    def test_space_type_nullsec(self):
        obj = EveSolarSystem.objects.get(id=30000474)
        expected = EveSolarSystem.TYPE_NULLSEC
        self.assertEqual(obj.space_type, expected)

    def test_space_type_wh_space(self):
        obj = EveSolarSystem.objects.get(id=31000005)
        expected = EveSolarSystem.TYPE_W_SPACE
        self.assertEqual(obj.space_type, expected)

    def test_sov_alliance_id(self):
        # returns alliance ID for sov system in null
        obj = EveSolarSystem.objects.get(id=30000474)
        expected = 3001
        self.assertEqual(obj.sov_alliance_id, expected)

        # returns None if there is not sov info
        obj = EveSolarSystem.objects.get(id=30000476)
        self.assertIsNone(obj.sov_alliance_id)

        # returns None if system is not in Null sec
        obj = EveSolarSystem.objects.get(id=30002537)
        self.assertIsNone(obj.sov_alliance_id)

    def test_corporation_has_sov(self):
        corp = EveCorporationInfo.objects.get(corporation_id=2001)
        # Wayne Tech has sov in 1-PG
        obj = EveSolarSystem.objects.get(id=30000474)
        self.assertTrue(obj.corporation_has_sov(corp))

        # Wayne Tech has no sov in A-C5
        obj = EveSolarSystem.objects.get(id=30000476)
        self.assertFalse(obj.corporation_has_sov(corp))

        # There can't be any sov outside nullsec
        obj = EveSolarSystem.objects.get(id=30002537)
        self.assertIsNone(obj.corporation_has_sov(corp))


class TestEvePlanet(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
                EvePlanet,
            ]
        )

    def test_get(self):
        obj = EvePlanet.objects.get(id=40161463)
        self.assertEqual(obj.name, "Amamake I")
        self.assertEqual(obj.eve_solar_system_id, 30002537)
        self.assertEqual(obj.eve_type_id, 2016)

    def test_name_localized_generated(self):
        obj = EvePlanet.objects.get(id=40161463)
        expected = "Amamake_de I"
        self.assertEqual(obj._name_localized_generated("de"), expected)


class TestEveMoon(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
                EvePlanet,
                EveMoon,
            ]
        )

    def test_get(self):
        obj = EveMoon.objects.get(id=40161465)
        self.assertEqual(obj.name, "Amamake II - Moon 1")
        self.assertEqual(obj.eve_solar_system_id, 30002537)

    def test_name_localized_generated(self):
        obj = EveMoon.objects.get(id=40161465)

        expected = "Amamake_de II - Mond 1"
        self.assertEqual(obj._name_localized_generated("de"), expected)


class TestEveSovereigntyMap(NoSocketsTestCase):
    def test_str(self):
        obj = EveSovereigntyMap(solar_system_id=99)
        expected = "99"
        self.assertEqual(str(obj), expected)

    def test_repr(self):
        obj = EveSovereigntyMap(solar_system_id=99)
        expected = "EveSovereigntyMap(solar_system_id='99')"
        self.assertEqual(repr(obj), expected)
