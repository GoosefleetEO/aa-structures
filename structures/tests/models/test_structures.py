from datetime import timedelta
from django.utils.timezone import now

from ...models import StructureTag, StructureService, Structure
from ..testdata import create_structures, set_owner_character
from ...utils import set_test_logger, NoSocketsTestCase

MODULE_PATH = 'structures.models.structures'
logger = set_test_logger(MODULE_PATH, __file__)


class TestStructureTag(NoSocketsTestCase):
    
    def test_str(self):        
        x = StructureTag(
            name='Super cool tag'
        )
        self.assertEqual(str(x), 'Super cool tag')

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

    def setUp(self):                  
        create_structures()        
        set_owner_character(character_id=1001)
        
    def test_state_str(self):
        x = Structure.objects.get(id=1000000000001)
        x.state = Structure.STATE_ANCHORING
        self.assertEqual(x.state_str, 'anchoring')

    def test_is_low_power(self):
        x = Structure.objects.get(id=1000000000001)
        
        x.fuel_expires = None
        self.assertTrue(x.is_low_power)
        
        x.fuel_expires = now() + timedelta(days=3)
        self.assertFalse(x.is_low_power)

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

    def test_str(self):
        x = Structure.objects.get(id=1000000000001)
        self.assertEqual(str(x), 'Amamake - Test Structure Alpha')

    def test_structure_service_str(self):
        structure = Structure.objects.get(id=1000000000001)
        x = StructureService(
            structure=structure,
            name='Dummy',
            state=StructureService.STATE_ONLINE
        )
        self.assertEqual(str(x), 'Amamake - Test Structure Alpha - Dummy')


class TestStructureNoSetup(NoSocketsTestCase):
    
    def test_structure_get_matching_state(self):
        self.assertEqual(
            Structure.get_matching_state('anchoring'), 
            Structure.STATE_ANCHORING
        )
        self.assertEqual(
            Structure.get_matching_state('not matching name'), 
            Structure.STATE_UNKNOWN
        )
    
    def test_structure_service_get_matching_state(self):
        self.assertEqual(
            StructureService.get_matching_state('online'), 
            StructureService.STATE_ONLINE
        )
        self.assertEqual(
            StructureService.get_matching_state('offline'), 
            StructureService.STATE_OFFLINE
        )
        self.assertEqual(
            StructureService.get_matching_state('not matching'), 
            StructureService.STATE_OFFLINE
        )
