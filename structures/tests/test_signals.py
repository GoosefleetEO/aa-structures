from django.contrib.auth.models import User
from django.test import TestCase

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from . import set_logger
from ..models import *
from .testdata import entities_testdata, load_entities, create_structures,\
    set_owner_character

class TestSignals(TestCase):

    def setUp(self):        
        create_structures()
        

    def test_add_default_tags_to_new_structures(self):                
        obj = Structure.objects.get(id=1000000000001)
        self.assertSetEqual(
            {x.name for x in obj.tags.all()},
            {'tag_a'}
        )