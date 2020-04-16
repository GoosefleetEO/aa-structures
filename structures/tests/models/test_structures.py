from datetime import timedelta
from django.utils.timezone import now

from ...models import StructureTag, StructureService, Structure
from ..testdata import create_structures, set_owner_character
from ...utils import set_test_logger, NoSocketsTestCase

MODULE_PATH = 'structures.models.structures'
logger = set_test_logger(MODULE_PATH, __file__)


class TestStructureTag(NoSocketsTestCase):
    
    def test_str(self):        
        obj = StructureTag(name='Super cool tag')
        self.assertEqual(str(obj), 'Super cool tag')

    def test_repr(self):
        obj = StructureTag.objects.create(name='Super cool tag')
        expected = 'StructureTag(name=\'Super cool tag\')'
        self.assertEqual(repr(obj), expected)
    
    def test_list_sorted(self):                
        x1 = StructureTag(name='Alpha')
        x2 = StructureTag(name='charlie')
        x3 = StructureTag(name='bravo')
        tags = [x1, x2, x3]
        
        self.assertListEqual(
            StructureTag.sorted(tags),
            [x1, x3, x2]
        )
        self.assertListEqual(
            StructureTag.sorted(tags, reverse=True),
            [x2, x3, x1]
        )
        
    def test_html_default(self):
        x = StructureTag(
            name='Super cool tag'
        )
        self.assertEqual(
            x.html, 
            '<span class="label label-default">Super cool tag</span>'
        )

    def test_html_primary(self):
        x = StructureTag(
            name='Super cool tag',
            style='primary'
        )
        self.assertEqual(
            x.html, 
            '<span class="label label-primary">Super cool tag</span>'
        )


class TestStructure(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()        
        set_owner_character(character_id=1001)
    
    def test_str(self):
        x = Structure.objects.get(id=1000000000001)
        expected = 'Amamake - Test Structure Alpha'
        self.assertEqual(str(x), expected)

    def test_repr(self):
        x = Structure.objects.get(id=1000000000001)
        expected = (
            'Structure(id=1000000000001, '
            'name=\'Test Structure Alpha\')'
        )
        self.assertEqual(repr(x), expected)

    def test_is_low_power(self):
        obj = Structure.objects.get(id=1000000000001)
        
        # true if Upwell structure and has no fuel
        obj.fuel_expires = None
        self.assertTrue(obj.is_low_power)
        
        # false if Upwell structure and it has fuel
        obj.fuel_expires = now() + timedelta(days=3)
        self.assertFalse(obj.is_low_power)

        # false for non structures
        obj = Structure.objects.get(id=1300000000001)   # starbase
        self.assertFalse(obj.is_low_power)

        obj = Structure.objects.get(id=1200000000003)   # POS
        self.assertFalse(obj.is_low_power)

    def test_is_reinforced(self):
        x = Structure.objects.get(id=1000000000001)

        x.state = Structure.STATE_SHIELD_VULNERABLE
        self.assertFalse(x.is_reinforced)

        for state in [
            Structure.STATE_ARMOR_REINFORCE, 
            Structure.STATE_HULL_REINFORCE,
            Structure.STATE_ANCHOR_VULNERABLE,
            Structure.STATE_HULL_VULNERABLE
        ]:
            x.state = state
            self.assertTrue(x.is_reinforced)

    def test_structure_service_str(self):
        structure = Structure.objects.get(id=1000000000001)
        x = StructureService(
            structure=structure,
            name='Dummy',
            state=StructureService.STATE_ONLINE
        )
        self.assertEqual(str(x), 'Amamake - Test Structure Alpha - Dummy')

    def test_extract_name_from_esi_respose(self):
        expected = 'Alpha'
        self.assertEqual(
            Structure.extract_name_from_esi_respose('Super - Alpha'), expected
        )        
        self.assertEqual(
            Structure.extract_name_from_esi_respose('Alpha'), expected
        )

    def test_owner_has_sov(self):
        # Wayne Tech has sov in 1-PG
        obj = Structure.objects.get(id=1300000000003)
        self.assertTrue(obj.owner_has_sov)

        # Wayne Tech has no sov in A-C5TC
        obj = Structure.objects.get(id=1000000000003)
        self.assertFalse(obj.owner_has_sov)

        # Wayne Tech has no sov in Amamake
        obj = Structure.objects.get(id=1000000000001)
        self.assertFalse(obj.owner_has_sov)


class TestStructure2(NoSocketsTestCase):
    
    def setUp(self):                
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
        null_tag.style = StructureTag.STYLE_DARK_BLUE
        null_tag.save()

        sov_tag = StructureTag.objects.get(name=StructureTag.NAME_SOV_TAG)
        self.assertIn(sov_tag, list(obj.tags.all()))
        sov_tag.order = 100
        sov_tag.style = StructureTag.STYLE_RED
        sov_tag.save()

        obj.update_generated_tags(recreate_tags=True)
        null_tag.refresh_from_db()
        self.assertEqual(null_tag.style, StructureTag.STYLE_RED)
        self.assertEqual(null_tag.order, 50)
        sov_tag.refresh_from_db()
        self.assertEqual(sov_tag.style, StructureTag.STYLE_DARK_BLUE)
        self.assertEqual(sov_tag.order, 20)
        

class TestStructureSave(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()        
        _, cls.owner = set_owner_character(character_id=1001)
        Structure.objects.all().delete()
        StructureTag.objects.all().delete()

    def test_can_save_tags_low_sec(self):
        obj = Structure.objects.create(
            id=1300000000003,
            owner=self.owner,
            eve_solar_system_id=30002537,
            name='Dummy',
            state=Structure.STATE_SHIELD_VULNERABLE,
            eve_type_id=35832,
        )
        lowsec_tag = StructureTag.objects.get(name=StructureTag.NAME_LOWSEC_TAG)
        self.assertIn(lowsec_tag, obj.tags.all())
        self.assertIsNone(
            StructureTag.objects.filter(name=StructureTag.NAME_SOV_TAG).first()
        )
        
    def test_can_save_tags_null_sec_w_sov(self):
        obj = Structure.objects.create(
            id=1300000000003,
            owner=self.owner,
            eve_solar_system_id=30000474,
            name='Dummy',
            state=Structure.STATE_SHIELD_VULNERABLE,
            eve_type_id=35832,
        )
        nullsec_tag = StructureTag.objects.get(name=StructureTag.NAME_NULLSEC_TAG)
        self.assertIn(nullsec_tag, obj.tags.all())
        sov_tag = StructureTag.objects.get(name=StructureTag.NAME_SOV_TAG)
        self.assertIn(sov_tag, obj.tags.all())


class TestStructureNoSetup(NoSocketsTestCase):
    
    def test_structure_get_matching_state(self):
        self.assertEqual(
            Structure.get_matching_state_for_esi_state('anchoring'), 
            Structure.STATE_ANCHORING
        )
        self.assertEqual(
            Structure.get_matching_state_for_esi_state('not matching name'), 
            Structure.STATE_UNKNOWN
        )
    
    def test_structure_service_get_matching_state(self):
        self.assertEqual(
            StructureService.get_matching_state_for_esi_state('online'), 
            StructureService.STATE_ONLINE
        )
        self.assertEqual(
            StructureService.get_matching_state_for_esi_state('offline'), 
            StructureService.STATE_OFFLINE
        )
        self.assertEqual(
            StructureService.get_matching_state_for_esi_state('not matching'), 
            StructureService.STATE_OFFLINE
        )


class TestStructureService(NoSocketsTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()          
        create_structures()        
        set_owner_character(character_id=1001)

    def test_str(self):
        structure = Structure.objects.get(id=1000000000001)
        obj = StructureService.objects.get(
            structure=structure, name='Clone Bay'
        )
        expected = 'Amamake - Test Structure Alpha - Clone Bay'
        self.assertEqual(str(obj), expected)

    def test_repr(self):
        structure = Structure.objects.get(id=1000000000001)
        obj = StructureService.objects.get(
            structure=structure, name='Clone Bay'
        )
        expected = (
            'StructureService(structure_id=1000000000001, name=\'Clone Bay\')'
        )
        self.assertEqual(repr(obj), expected)
