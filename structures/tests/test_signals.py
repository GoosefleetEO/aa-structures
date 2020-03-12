from django.test import TestCase

from ..utils import set_test_logger
from ..models import Structure
from .testdata import create_structures


MODULE_PATH = 'structures.signals'
logger = set_test_logger(MODULE_PATH, __file__)


class TestSignals(TestCase):

    def setUp(self):        
        create_structures()
        
    def test_add_default_tags_to_new_structures(self):                
        obj = Structure.objects.get(id=1000000000001)
        self.assertSetEqual(
            {x.name for x in obj.tags.all()},
            {'tag_a'}
        )
