import calendar

from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, permission_required

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo, EveAllianceInfo
from esi.decorators import token_required

from . import evelinks
from . import tasks
from .models import *
from .utils import messages_plus, DATETIME_FORMAT

STRUCTURE_LIST_ICON_RENDER_SIZE = 64
STRUCTURE_LIST_ICON_OUTPUT_SIZE = 40

@login_required
@permission_required('structures.basic_access')
def index(request):       
    """main view showing the structure list"""
    context = {
        'page_title': 'Alliance Structures'
    }    
    return render(request, 'structures/index.html', context)


@login_required
@permission_required('structures.basic_access')
def structure_list_data(request):
    """returns structure list in JSON for AJAX call in index view"""
    if request.user.has_perm('structures.view_all_structures'):
        structures = Structure.objects.all().select_related()
    else:
        if request.user.has_perm('structures.view_alliance_structures'):
            alliance = EveAllianceInfo.objects.get(
                alliance_id=request.user.profile.main_character.alliance_id
            )
            corporations = alliance.evecorporationinfo_set.all()          
        else:
            corporations = [
                EveCorporationInfo.objects.get(
                    corporation_id=x.character.corporation_id
                )
                for x in request.user.character_ownerships.all()
            ]
        structures = Structure.objects\
            .filter(owner__corporation__in=corporations) \
            .select_related()

    structures_data = list()
    for structure in structures:        
        
        row = dict()
        row['is_poco'] = structure.eve_type.is_poco
        
        # owner
        corporation = structure.owner.corporation
        if corporation.alliance:
            alliance_name = corporation.alliance.alliance_name            
        else: 
            alliance_name = ""            
                
        corporation_url = evelinks.get_entity_profile_url_by_name(
            evelinks.ESI_CATEGORY_CORPORATION,
            corporation.corporation_name
        )

        row['owner'] = '<a href="{}">{}</a><br>{}'.format(
            corporation_url,
            corporation.corporation_name,
            alliance_name
        )
        row['alliance_name'] = alliance_name
        row['corporation_name'] = corporation.corporation_name

        # corporation icon
        row['corporation_icon'] = '<img src="{}" width="{}" height="{}"/>'\
            .format(
                corporation.logo_url(size=STRUCTURE_LIST_ICON_RENDER_SIZE),
                STRUCTURE_LIST_ICON_OUTPUT_SIZE,
                STRUCTURE_LIST_ICON_OUTPUT_SIZE,
            )
        
        # location        
        row['solar_system_name'] = structure.eve_solar_system.name
        solar_system_url = evelinks.get_entity_profile_url_by_name(
            evelinks.ESI_CATEGORY_SOLARSYSTEM,
            row['solar_system_name']
        )
        row['region_name'] = structure.eve_solar_system.eve_constellation.eve_region.name
        row['location'] = '<a href="{}">{}</a><br>{}'.format(
            solar_system_url,
            structure.eve_solar_system.name,
            row['region_name']
        )        
        
        # type icon
        row['type_icon'] = '<img src="{}" width="{}" height="{}"/>'.format(
            structure.eve_type.icon_url(size=STRUCTURE_LIST_ICON_RENDER_SIZE),
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
        )        
        
        # type name              
        row['type_name'] = structure.eve_type.name
        row['type'] = row['type_name']

        # row name
        row['is_low_power'] = structure.is_low_power
        row['is_low_power_str'] = 'yes' if structure.is_low_power else 'no'
        row['structure_name'] = structure.name
        if structure.is_low_power:
            row['structure_name'] += '<br>[LOW POWER]'

        # services
        services = ''        
        for service in structure.structureservice_set.all().order_by('name'):
            if service.state == StructureService.STATE_OFFLINE:
                service_name = '<del>{}</del>'. format(service.name)
            else:
                service_name = service.name
            services += '<p>{}</p>'.format(service_name)
        row['services'] = services
            
        # add reinforcement infos
        row['is_reinforced'] = structure.is_reinforced
        row['is_reinforced_str'] = 'yes' if structure.is_reinforced else 'no'
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
@permission_required('structures.add_structure_owner')
@token_required(scopes=Owner.get_esi_scopes())
def add_structure_owner(request, token):    
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
            'You can only use your main or alt characters to add corporations.'
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
        
        default_webhook = Webhook.objects\
            .filter(is_default__exact=True)\
            .first()
        
        owner, created = Owner.objects.update_or_create(
            corporation=corporation,
            defaults={
                'character': owned_char,
                'webhook': default_webhook
            }
        )          
        tasks.update_structures_for_owner.delay(            
            owner_pk=owner.pk,
            force_sync=True,
            user_pk=request.user.pk
        )
        tasks.fetch_notifications_for_owner.delay(            
            owner_pk=owner.pk,
            force_sync=True,
            user_pk=request.user.pk
        )
        messages_plus.success(
            request,             
            '<strong>{}</strong> has been added '.format(owner)
            + 'with <strong>{}</strong> as sync character. '.format(
                    owner.character.character.character_name, 
                )                        
            + 'We have started fetching structures and notifications for this corporation. '
            + 'You will receive a reports for both once completed.'
        )
    return redirect('structures:index')


@login_required
@permission_required('structures.basic_access')
def test(request):
    tasks.update_structures_for_owner()
    return redirect('structures:index')


