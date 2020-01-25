from django.contrib.auth.models import User
from django.test import TestCase

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from . import set_logger
from ..models import *
from .testdata import entities_testdata, load_entities

class TestSignals(TestCase):

    def setUp(self):
        
        load_entities([
            EveGroup,
            EveType,
            EveRegion,
            EveConstellation,
            EveSolarSystem,            
            EveCorporationInfo,
            EveCharacter
        ])
            
        # 1 user
        self.character = EveCharacter.objects.get(character_id=1001)
                
        self.corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        self.user = User.objects.create_user(
            self.character.character_name,
            'abc@example.com',
            'password'
        )

        self.main_ownership = CharacterOwnership.objects.create(
            character=self.character,
            owner_hash='x1',
            user=self.user
        )

        Owner.objects.all().delete()
        Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )        
        
        Structure.objects.all().delete()
        
        # create StructureTag objects
        StructureTag.objects.all().delete()
        for x in entities_testdata['StructureTag']:
            StructureTag.objects.create(**x)


    def test_add_default_tags_to_new_structures(self):
        for structure in entities_testdata['Structure']:            
            x = structure.copy()
            if x['id'] == 1000000000001:
                x['owner'] = Owner.objects.get(
                    corporation__corporation_id=x['owner_corporation_id']
                )            
                del(x['owner_corporation_id'])
                Structure.objects.create(**x)
        
        obj = Structure.objects.get(id=1000000000001)
        self.assertSetEqual(
            {x.name for x in obj.tags.all()},
            {'tag_a'}
        )