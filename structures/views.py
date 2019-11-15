import calendar

from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, permission_required

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from esi.decorators import token_required

from . import evelinks
from . import tasks
from .models import *
from .utils import messages_plus, DATETIME_FORMAT

@login_required
@permission_required('structures.basic_access')
def index(request):
        
    context = {
        'text': 'Hello, World!'
    }    
    return render(request, 'structures/index.html', context)


@login_required
@permission_required('structures.basic_access')
@token_required(scopes=Owner.get_esi_scopes())
def add_owner(request, token):    
    token_char = EveCharacter.objects.get(character_id=token.character_id)
    
    success = True
    try:
        owned_char = CharacterOwnership.objects.get(
            user=request.user,
            character=token_char
        )        
    except CharacterOwnership.DoesNotExist:
        messages_plus.error(
            request,
            'You can only use your main or alt characters to add '
            + ' corporations. '
            + 'However, character <strong>{}</strong> is neither. '.format(
                token_char.character_name
            )
        )
        success = False
    
    if success:
        try:
            corporation = EveCorporationInfo.objects.get(
                corporation_id=token_char.corporation_id
            )
        except EveCorporationInfo.DoesNotExist:
            corporation = EveCorporationInfo.objects.create_corporation(
                token_char.corporation_id
            )
            corporation.save()

        owner, created = Owner.objects.update_or_create(
            corporation=corporation,
            defaults={
                'character': owned_char
            }
        )          
        tasks.run_structures_sync.delay(            
            force_sync=True,
            # user_pk=request.user.pk
        )        
        messages_plus.success(
            request, 
            'Started adding row for '
            + '<strong>{}</strong> '.format(owner)
            + 'with <strong>{}</strong> as sync character. '.format(
                    owner.character.character.character_name, 
                )                        
            + 'You will receive a report once it is completed.'
        )
    return redirect('structures:index')


@login_required
@permission_required('structures.basic_access')
def structure_list(request):       
    context = {
        'text': 'Hello, World!'
    }    
    return render(request, 'structures/structures.html', context)


@login_required
@permission_required('structures.basic_access')
def structure_list_data(request):
    structures = Structure.objects.all().select_related()    
    structures_data = list()
    for structure in structures:        
        
        row = dict()
        row['is_poco'] = False # Hack !!
        
        # owner
        if not structure.owner.corporation.alliance_id:
            alliance_name = ""
        else: 
            alliance_name = "(tbd)" #structure.owner.corporation.alliance_name
                
        corporation_url = evelinks.get_entity_profile_url_by_name(
            evelinks.ESI_CATEGORY_CORPORATION,
            structure.owner.corporation.corporation_name
        )

        row['owner'] = '<a href="{}">{}</a><br>{}'.format(
            corporation_url,
            structure.owner.corporation.corporation_name,
            alliance_name
        )
        row['alliance_name'] = alliance_name
        row['corporation_name'] = structure.owner.corporation.corporation_name

        # corporation icon
        row['corporation_icon'] = '<img src="{}">'.format(
            structure.owner.corporation.logo_url()
        )
        
        # location        
        solar_system_url = evelinks.get_entity_profile_url_by_name(
            evelinks.ESI_CATEGORY_SOLARSYSTEM,
            structure.eve_solar_system.name
        )
        row['location'] = '<a href="{}">{}</a><br>{}'.format(
            solar_system_url,
            structure.eve_solar_system.name,
            structure.eve_solar_system.eve_constellation.eve_region.name
        )
        row['region_name'] = structure.eve_solar_system.eve_constellation.eve_region.name
        row['solar_system_name'] = structure.eve_solar_system.name

        # type icon
        row['type_icon'] = '<img src="{}"/>'.format(
            evelinks.get_type_image_url(
                structure.eve_type_id,
                32
        ))        
        
        # type name
        type_url = evelinks.get_entity_profile_url_by_id(
            evelinks.ESI_CATEGORY_INVENTORYTYPE,
            structure.eve_type_id
        )        
        row['type'] = '<a href="{}">{}</a>'.format(
            type_url,
            structure.eve_type_id
        )
        row['type_name'] = structure.eve_type.name

        # row name
        row['is_low_power'] = False #structure['is_low_power']
        row['is_low_power_str'] = 'yes' if row['is_low_power'] else 'no'
        row['structure_name_short'] = structure.name #structure['structure_name_short']
        if row['is_low_power']:
            row['structure_name_short'] += '<br>[LOW POWER]'

        # services
        services = ''
        """
        for service in structure['services']:
            if service['state'] == 'offline':
                service_name = '<del>{}</del>'. format(service['name'])
            else:
                service_name = service['name']            
            services += '<p>{}</p>'.format(service_name) 
        """
        row['services'] = services
            
        # add reinforcement infos
        row['is_reinforced'] = False #structure['is_reinforced']
        row['is_reinforced_str'] = 'yes' if row['is_reinforced'] else 'no'
        reinforce_hour_str = str(structure.reinforce_hour) + ":00"
        if structure.reinforce_weekday:            
            reinforce_day_str = calendar.day_name[structure.reinforce_weekday]
        else:
            reinforce_day_str = ""
        if not row['is_poco']:
            row['reinforcement'] = '{}<br>{}'.format(
                reinforce_day_str,
                reinforce_hour_str
            )
        else:
            row['reinforcement'] = reinforce_hour_str

        # add date when fuel runs out
        if structure.fuel_expires:
            row['fuel_expires'] = \
                structure.fuel_expires.strftime(DATETIME_FORMAT)
        else:
            row['fuel_expires'] = 'N/A'
        
        # state
        if row['is_poco']:
            row['state_str'] = 'N/A'
            row['state_details'] = 'N/A'
            
        else:
            row['state_str'] = structure.state_str
            row['state_details'] = row['state_str']
            if structure.state_timer_end:
                row['state_details'] += '<br>{}'.format(                    
                    structure.state_timer_end.strftime(DATETIME_FORMAT)
                )

        structures_data.append(row)
       
    return JsonResponse(structures_data, safe=False)


@login_required
@permission_required('structures.basic_access')
def test(request):
    tasks.run_structures_sync()
    return redirect('structures:index')