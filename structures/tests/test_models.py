from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo

from . import set_logger
from .testdata import entities_testdata
from ..models import *


logger = set_logger('structures.views', __file__)

class TestOwner(TestCase):

    def test_to_friendly_error_message(self):
        
        #normal error
        self.assertEqual(
            Owner.to_friendly_error_message(Owner.ERROR_NO_CHARACTER), 
            'No character set for fetching data from ESI'
        )

        #normal error
        self.assertEqual(
            Owner.to_friendly_error_message(0), 
            'No error'
        )

        #undefined error
        self.assertEqual(
            Owner.to_friendly_error_message(9876), 
            'Undefined error'
        )

        #undefined error
        self.assertEqual(
            Owner.to_friendly_error_message(-1), 
            'Undefined error'
        )

    
    @patch('structures.models.STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)
    def test_get_esi_scopes_pocos_off(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                'esi-corporations.read_structures.v1',
                'esi-universe.read_structures.v1',
                'esi-characters.read_notifications.v1'
            }
        )

    @patch('structures.models.STRUCTURES_FEATURE_CUSTOMS_OFFICES', True)
    def test_get_esi_scopes_pocos_on(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                'esi-corporations.read_structures.v1',
                'esi-universe.read_structures.v1',
                'esi-characters.read_notifications.v1',
                'esi-planets.read_customs_offices.v1',
                'esi-assets.read_corporation_assets.v1'
            }
        )
    
        



class TestStructureTag(TestCase):

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


class TestStructure(TestCase):

    def setUp(self):
                  
        entities_def = [
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveMoon,
            EveGroup,
            EveType,
            EveAllianceInfo,
            EveCorporationInfo,
            EveCharacter,    
            EveEntity    
        ]
    
        for EntityClass in entities_def:
            entity_name = EntityClass.__name__
            for x in entities_testdata[entity_name]:
                EntityClass.objects.create(**x)
            assert(len(entities_testdata[entity_name]) == EntityClass.objects.count())
                
        for corporation in EveCorporationInfo.objects.all():
            EveEntity.objects.get_or_create(
                id = corporation.corporation_id,
                defaults={
                    'category': EveEntity.CATEGORY_CORPORATION,
                    'name': corporation.corporation_name
                }
            )
            Owner.objects.create(
                corporation=corporation
            )
            if int(corporation.corporation_id) in [2001, 2002]:
                alliance = EveAllianceInfo.objects.get(alliance_id=3001)
                corporation.alliance = alliance
                corporation.save()


        for character in EveCharacter.objects.all():
            EveEntity.objects.get_or_create(
                id = character.character_id,
                defaults={
                    'category': EveEntity.CATEGORY_CHARACTER,
                    'name': character.character_name
                }
            )
            corporation = EveCorporationInfo.objects.get(
                corporation_id=character.corporation_id
            )
            if corporation.alliance:                
                character.alliance_id = corporation.alliance.alliance_id
                character.alliance_name = corporation.alliance.alliance_name
                character.save()
                       
        # 1 user
        self.character = EveCharacter.objects.get(character_id=1001)
                
        self.corporation = EveCorporationInfo.objects.get(
            corporation_id=self.character.corporation_id
        )
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
        self.user.profile.main_character = self.character
        
        self.owner = Owner.objects.get(
            corporation__corporation_id=self.character.corporation_id
        )
        self.owner.character = self.main_ownership

        # create Structure objects
        for structure in entities_testdata['Structure']:
            x = structure.copy()
            x['owner'] = Owner.objects.get(
                corporation__corporation_id=x['owner_corporation_id']
            )
            del x['owner_corporation_id']
            Structure.objects.create(**x)

        # create StructureTag objects
        StructureTag.objects.all().delete()
        for x in entities_testdata['StructureTag']:
            StructureTag.objects.create(**x)

    def test_is_poco(self):
        x = Structure.objects.get(id=1200000000003)  
        self.assertTrue(x.eve_type.is_poco)
      