import logging
import inspect
import json
import math
import os
import sys
from unittest.mock import Mock, patch

from django.contrib.auth.models import User, Permission 
from django.urls import reverse
from django.test import TestCase
from django.test.client import Client

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.authentication.models import CharacterOwnership
from esi.models import Token, Scope
from esi.errors import TokenExpiredError, TokenInvalidError

from . import tasks
from .app_settings import *
from .models import *


# reconfigure logger so we get logging from tasks to console during test
c_handler = logging.StreamHandler(sys.stdout)
logger = logging.getLogger('structures.tasks')
logger.level = logging.DEBUG
logger.addHandler(c_handler)


class TestTasksStructureUpdate(TestCase):
    
    # note: setup is making calls to ESI to get full info for entities
    # all ESI calls in the tested module are mocked though


    @classmethod
    def setUpClass(cls):
        super(TestTasksStructureUpdate, cls).setUpClass()

        # load test data
        currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
            inspect.currentframe()
        )))

        # ESI corp structures        
        with open(
            currentdir + '/testdata/corp_structures.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            cls.corp_structures = json.load(f)

        # ESI universe structures
        with open(
            currentdir + '/testdata/universe_structures.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            cls.universe_structures = json.load(f)

        # entities
        with open(
            currentdir + '/testdata/entities.json', 
            'r', 
            encoding='utf-8'
        ) as f:
            entities = json.load(f)

        entities_def = [
            EveRegion,
            EveConstellation,
            EveSolarSystem,
            EveGroup,
            EveType,
            EveCorporationInfo,
            EveCharacter
        ]
    
        for EntityClass in entities_def:
            entity_name = EntityClass.__name__
            for x in entities[entity_name]:
                EntityClass.objects.create(**x)
            assert(len(entities[entity_name]) == EntityClass.objects.count())
        
        # 1 user
        cls.character = EveCharacter.objects.get(character_id=1001)
                
        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        cls.user = User.objects.create_user(
            cls.character.character_name,
            'abc@example.com',
            'password'
        )

        cls.main_ownership = CharacterOwnership.objects.create(
            character=cls.character,
            owner_hash='x1',
            user=cls.user
        )        


    # run without char        
    def test_run_no_sync_char(self):
        owner = Owner.objects.create(
            corporation=self.corporation            
        )
        self.assertFalse(
            tasks.update_structures_for_owner(owner_pk=owner.pk)
        )
        owner.refresh_from_db()
        self.assertEqual(
            owner.last_error, 
            Owner.ERROR_NO_CHARACTER
        )

       
    # test expired token    
    @patch('structures.tasks.Token')    
    def test_check_expired_token(
            self,             
            mock_Token
        ):                
        
        mock_Token.objects.filter.side_effect = TokenExpiredError()        
                        
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )
        
        # run update task
        self.assertFalse(
            tasks.update_structures_for_owner(owner_pk=owner.pk)
        )

        owner.refresh_from_db()
        self.assertEqual(
            owner.last_error, 
            Owner.ERROR_TOKEN_EXPIRED            
        )

    
    
    # test invalid token    
    @patch('structures.tasks.Token')
    def test_check_invalid_token(
            self,             
            mock_Token
        ):                
        
        mock_Token.objects.filter.side_effect = TokenInvalidError()
                        
        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )
        
        # run update task
        self.assertFalse(
            tasks.update_structures_for_owner(owner_pk=owner.pk)
        )

        owner.refresh_from_db()
        self.assertEqual(
            owner.last_error, 
            Owner.ERROR_TOKEN_INVALID            
        )
    
    # normal synch of new structures, mode my_alliance            
    @patch('structures.tasks.Token', autospec=True)
    @patch('structures.tasks.esi_client_factory')
    def test_update_structures_for_owner_normal(
            self, 
            mock_esi_client_factory,             
            mock_Token
        ):
        
        # create mocks
        def get_corp_structures_page(*args, **kwargs):
            #returns single page for operation.result(), first with header
            page_size = 2
            mock_calls_count = len(mock_operation.mock_calls)
            start = (mock_calls_count - 1) * page_size
            stop = start + page_size
            pages_count = int(math.ceil(len(self.corp_structures) / page_size))
            if mock_calls_count == 1:
                mock_response = Mock()
                mock_response.headers = {'x-pages': pages_count}
                return [self.corp_structures[start:stop], mock_response]
            else:
                return self.corp_structures[start:stop]

        def get_universe_structure(structure_id, *args, **kwargs):
            if str(structure_id) in self.universe_structures:
                x = Mock()
                x.result.return_value = \
                    self.universe_structures[str(structure_id)]
                return x
            else:
                raise RuntimeError(
                    'Can not find structure for {}'.format(structure_id)
                )

        # mock_Token.objects.filter.side_effect = [Token()]
        
        mock_client = Mock()
        mock_operation = Mock()
        mock_operation.result.side_effect = get_corp_structures_page        
        mock_client.Corporation.get_corporations_corporation_id_structures =\
            Mock(return_value=mock_operation)
        mock_client.Universe.get_universe_structures_structure_id.side_effect =\
            get_universe_structure
        mock_esi_client_factory.return_value = mock_client

        # create test data
        p = Permission.objects.filter(            
            codename='add_structure_owner'
        ).first()
        self.user.user_permissions.add(p)
        self.user.save()
        owner = Owner.objects.create(
            corporation=self.corporation,
            character=self.main_ownership
        )
        
        # run update task
        self.assertTrue(
            tasks.update_structures_for_owner(owner_pk=owner.pk)
        )

        owner.refresh_from_db()
        self.assertEqual(
            owner.last_error, 
            Owner.ERROR_NONE            
        )
        
        # should have tried to fetch structures
        self.assertEqual(mock_operation.result.call_count, 1)
        
        # should only contain the right structures
        structure_ids = [
            x['id'] for x in Structure.objects.values('id')
        ]
        self.assertCountEqual(
            structure_ids,
            [1031369432897, 1028151259819]
        )

