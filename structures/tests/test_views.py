from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User, Permission 
from django.test import TestCase, RequestFactory
from django.urls import reverse

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo

from . import set_logger
from .testdata import entities_testdata
from ..models import *
from .. import views

logger = set_logger('structures.views', __file__)



class TestViews(TestCase):
    
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
               
        self.factory = RequestFactory()
        
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

        # user needs basic permission to access the app
        p = Permission.objects.get(
            codename='basic_access', 
            content_type__app_label='structures'
        )
        self.user.user_permissions.add(p)
        self.user.save()

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

    def test_basic_access_main_view(self):
        request = self.factory.get(reverse('structures:index'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
    
    def test_basic_access_own_structures_only(self):
                
        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        structure_ids = { x['structure_id'] for x in data }
        self.assertSetEqual(
            structure_ids, 
            {
                1000000000001, 
                1200000000003, 
                1200000000004, 
                1200000000005
            }
        )
        

        """
        print('\nCorporations')
        print(EveCorporationInfo.objects.all().values())
        print('\nOwners')
        print(Owner.objects.all().values())
        print('\nStructures')
        print(Structure.objects.all().values())
        """

    def test_perm_view_alliance_structures_normal(self):
        
        # user needs permission to access view
        p = Permission.objects.get(
            codename='view_alliance_structures', 
            content_type__app_label='structures'
        )
        self.user.user_permissions.add(p)
        self.user.save()

        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))
        structure_ids = { x['structure_id'] for x in data }
        self.assertSetEqual(
            structure_ids, 
            {
                1000000000001, 
                1000000000002, 
                1200000000003, 
                1200000000004, 
                1200000000005
            }
        )


    def test_perm_view_alliance_structures_no_alliance(self):
        # run with a user that is not a member of an alliance        
        character = EveCharacter.objects.get(character_id=1002)        
        user = User.objects.create_user(
            character.character_name,
            'abc@example.com',
            'password'
        )
        main_ownership = CharacterOwnership.objects.create(
            character=character,
            owner_hash='x2',
            user=user
        )
        user.profile.main_character = character
        
        # user needs permission to access view
        p = Permission.objects.get(
            codename='basic_access', 
            content_type__app_label='structures'
        )
        user.user_permissions.add(p)
        p = Permission.objects.get(
            codename='view_alliance_structures', 
            content_type__app_label='structures'
        )
        user.user_permissions.add(p)
        user.save()

        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))
        structure_ids = { x['structure_id'] for x in data }
        self.assertSetEqual(
            structure_ids, 
            {1000000000003}
        )
            

    def test_perm_view_all_structures(self):
        
        # user needs permission to access view
        p = Permission.objects.get(
            codename='view_all_structures', 
            content_type__app_label='structures'
        )
        self.user.user_permissions.add(p)
        self.user.save()

        request = self.factory.get(reverse('structures:structure_list_data'))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))
        structure_ids = { x['structure_id'] for x in data }
        self.assertSetEqual(
            structure_ids, 
            {
                1000000000001, 
                1000000000002, 
                1000000000003, 
                1200000000003,
                1200000000004, 
                1200000000005
            }
        )


    def test_view_add_structure_owner(self):
        
        # user needs permission to access view
        p = Permission.objects.get(
            codename='add_structure_owner', 
            content_type__app_label='structures'
        )
        self.user.user_permissions.add(p)
        self.user.save()

        request = self.factory.get(reverse('structures:add_structure_owner'))
        request.user = self.user
        response = views.index(request)
        self.assertEqual(response.status_code, 200)


    def test_view_service_status_ok(self):
                
        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 200)

    
    def test_view_service_status_fail(self):
                
        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_UNKNOWN
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_UNKNOWN
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_UNKNOWN
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now() - timedelta(
                minutes=STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES + 1
            )
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()- timedelta(
                minutes=STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES + 1
            )
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)

        for owner in Owner.objects.filter(
            is_included_in_service_status__exact=True
        ):
            owner.structures_last_sync = now()
            owner.structures_last_error = Owner.ERROR_NONE
            owner.notifications_last_sync = now()
            owner.notifications_last_error = Owner.ERROR_NONE
            owner.forwarding_last_sync = now()- timedelta(
                minutes=STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES + 1
            )
            owner.forwarding_last_error = Owner.ERROR_NONE
            owner.save()

        request = self.factory.get(reverse('structures:service_status'))
        response = views.service_status(request)
        self.assertEqual(response.status_code, 500)


    def test_list_filter_by_tag_1(self):        
        # apply tags to structures
        tag_a = StructureTag.objects.get(name='tag_a')
        tag_b = StructureTag.objects.get(name='tag_b')
        x = Structure.objects.get(id=1000000000002)
        x.tags.add(tag_a)
        x.save()
        x = Structure.objects.get(id=1000000000003)
        x.tags.add(tag_a)
        x.tags.add(tag_b)
        x.save()
                
        # user needs permission to access view
        p = Permission.objects.get(
            codename='view_all_structures', 
            content_type__app_label='structures'
        )
        self.user.user_permissions.add(p)
        self.user.save()

        # no filter
        request = self.factory.get('{}'.format(
            reverse('structures:structure_list_data')
        ))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        self.assertSetEqual(
            { x['structure_id'] for x in data }, 
            {
                1000000000001, 
                1000000000002, 
                1000000000003, 
                1200000000003, 
                1200000000004, 
                1200000000005
            }
        )

        # filter for tag_a
        request = self.factory.get('{}?tags=tag_a'.format(
            reverse('structures:structure_list_data')
        ))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        self.assertSetEqual(
            { x['structure_id'] for x in data }, 
            {1000000000002, 1000000000003}
        )

        # filter for tag_b
        request = self.factory.get('{}?tags=tag_b'.format(
            reverse('structures:structure_list_data')
        ))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        self.assertSetEqual(
            { x['structure_id'] for x in data }, 
            {1000000000003}
        )

        # filter for tag_a, tag_b
        request = self.factory.get('{}?tags=tag_a,tag_b'.format(
            reverse('structures:structure_list_data')
        ))
        request.user = self.user
        response = views.structure_list_data(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode('utf-8'))        
        self.assertSetEqual(
            { x['structure_id'] for x in data }, 
            {1000000000002, 1000000000003}
        )