from django.utils import translation

from ...models import (
    EveCategory, 
    EveGroup, 
    EveType, 
    EveRegion, 
    EveConstellation, 
    EveSolarSystem, 
    EvePlanet,
    EveMoon
)
from ...models.eveuniverse import EveUniverse
from ..testdata import load_entities
from ...utils import set_test_logger, NoSocketsTestCase

MODULE_PATH = 'structures.models.eveuniverse'
logger = set_test_logger(MODULE_PATH, __file__)


class TestEveUniverse(NoSocketsTestCase):
                
    def test_field_names_1(self):
        expected = {'name'}
        self.assertEqual(EveCategory._field_names_not_pk(), expected)

    def test_field_names_2(self):
        expected = {'name', 'eve_category'}
        self.assertEqual(EveGroup._field_names_not_pk(), expected)

    def test_field_names_3(self):
        expected = {'name', 'eve_constellation', 'security_status'}
        self.assertEqual(EveSolarSystem._field_names_not_pk(), expected)

    def test_fk_mappings_1(self):
        expected = {
            'eve_category': ('category_id', EveCategory)
        }
        self.assertEqual(EveGroup._fk_mappings(), expected)

    def test_eve_universe_meta_attr_normal(self):
        expected = 'type_id'
        self.assertEqual(
            EveType._eve_universe_meta_attr('esi_pk'), expected
        )
    
    def test_eve_universe_meta_attr_key_not_defined(self):                
        self.assertIsNone(EveType._eve_universe_meta_attr('not_defined'))

    def test_eve_universe_meta_attr_key_not_defined_but_mandatory(self):        
        with self.assertRaises(ValueError):
            EveType._eve_universe_meta_attr(
                'not_defined', is_mandatory=True
            )
    
    def test_eve_universe_meta_attr_class_not_defined(self):                
        with self.assertRaises(ValueError):
            EveUniverse._eve_universe_meta_attr('esi_pk')

    def test_has_location_true_for_normal_models(self):
        self.assertTrue(EveType.has_esi_localization())

    def test_has_localization_false_if_set_false(self):
        self.assertFalse(EvePlanet.has_esi_localization())


class TestEveUniverseLocalization(NoSocketsTestCase):

    def setUp(self):
        self.obj = EveCategory(
            id=99,
            name='Name',
            name_de='Name_de',            
            name_ko='Name_ko',
            name_ru='',
            name_zh='Name_zh',
        )

    def test_can_localized_name_de_1(self):
        with translation.override('de'):
            expected = 'Name_de'        
            self.assertEqual(self.obj.name_localized, expected)

    def test_can_localized_name_de_2(self):        
        expected = 'Name_de'        
        self.assertEqual(self.obj.name_localized_for_language('de'), expected)

    def test_can_localized_name_en(self):
        with translation.override('en'):
            expected = 'Name'        
            self.assertEqual(self.obj.name_localized, expected)

    def test_can_localized_name_ko(self):
        with translation.override('ko'):
            expected = 'Name_ko'
            self.assertEqual(self.obj.name_localized, expected)

    def test_can_localized_name_zh(self):
        with translation.override('zh-hans'):
            expected = 'Name_zh'
            self.assertEqual(self.obj.name_localized, expected)

    def test_falls_back_to_en_for_missing_translation(self):
        with translation.override('ru'):
            expected = 'Name'
            self.assertEqual(self.obj.name_localized, expected)

    def test_falls_back_to_en_for_unknown_codes(self):
        with translation.override('xx'):
            expected = 'Name'
            self.assertEqual(self.obj.name_localized, expected)

    def test_set_generated_translations(self):
        load_entities([
            EveCategory,
            EveGroup,
            EveType,  
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EvePlanet
        ])
        obj = EvePlanet.objects.get(id=40161463)
        self.assertEqual(obj.name, 'Amamake I')
        self.assertEqual(obj.name_de, '')
        self.assertEqual(obj.name_ko, '')
        self.assertEqual(obj.name_ru, '')
        self.assertEqual(obj.name_zh, '')
        obj.set_generated_translations()
        self.assertEqual(obj.name_de, 'Amamake_de I')
        self.assertEqual(obj.name_ko, 'Amamake_ko I')
        self.assertEqual(obj.name_ru, 'Amamake_ru I')
        self.assertEqual(obj.name_zh, 'Amamake_zh I')
    

class TestEveType(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()    
        load_entities([
            EveCategory,
            EveGroup,
            EveType,          
        ])
        cls.type_astrahus = EveType.objects.get(id=35832)
        cls.type_poco = EveType.objects.get(id=2233)
        cls.type_starbase = EveType.objects.get(id=16213)

    def test_str(self):
        expected = 'Astrahus'
        self.assertEqual(str(self.type_astrahus), expected)

    def test_repr(self):
        expected = 'EveType(id=35832, name=\'Astrahus\')'
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

    def test_generic_icon_url_normal(self):
        self.assertEqual(
            EveType.generic_icon_url(self.type_astrahus.id),
            'https://images.evetech.net/types/35832/icon?size=64'
        )

    def test_generic_icon_url_w_size(self):
        self.assertEqual(
            EveType.generic_icon_url(self.type_astrahus.id, 128),
            'https://images.evetech.net/types/35832/icon?size=128'
        )

    def test_generic_icon_url_invalid_size(self):
        with self.assertRaises(ValueError):
            EveType.generic_icon_url(self.type_astrahus.id, 127)
            
    def test_icon_url(self):
        self.assertEqual(
            EveType.generic_icon_url(self.type_astrahus.id),
            self.type_astrahus.icon_url()
        )


class TestEvePlanet(NoSocketsTestCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([
            EveCategory,
            EveGroup,
            EveType,  
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EvePlanet
        ])

    def test_get(self):        
        obj = EvePlanet.objects.get(id=40161463)
        self.assertEqual(obj.name, 'Amamake I')
        self.assertEqual(obj.eve_solar_system_id, 30002537)
        self.assertEqual(obj.eve_type_id, 2016)

    def test_name_localized_generated(self):
        obj = EvePlanet.objects.get(id=40161463)        
        expected = 'Amamake_de I'
        self.assertEqual(obj._name_localized_generated('de'), expected)


class TestEveMoon(NoSocketsTestCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([
            EveCategory,
            EveGroup,
            EveType,  
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EvePlanet,
            EveMoon
        ])

    def test_get(self):        
        obj = EveMoon.objects.get(id=40161465)
        self.assertEqual(obj.name, 'Amamake II - Moon 1')
        self.assertEqual(obj.eve_solar_system_id, 30002537)        

    def test_name_localized_generated(self):
        obj = EveMoon.objects.get(id=40161465)
        
        expected = 'Amamake_de II - Mond 1'
        self.assertEqual(obj._name_localized_generated('de'), expected)
