import logging
import urllib

from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse, HttpResponseServerError
from django.shortcuts import render, redirect, reverse
from django.utils.html import format_html, mark_safe, escape
from django.utils.timezone import now
from django.utils.translation import gettext_lazy

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.eveonline.evelinks import dotlan
from esi.decorators import token_required

from . import tasks, __title__
from .app_settings import (
    STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED,
    STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE,
    STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED
)
from .forms import TagsFilterForm
from .models import Owner, Structure, StructureTag, StructureService, Webhook
from .utils import (
    format_html_lazy, 
    messages_plus, 
    DATETIME_FORMAT, 
    notify_admins, 
    LoggerAddTag,
    timeuntil_str,
    add_no_wrap_html,
    yesno_str
)


logger = LoggerAddTag(logging.getLogger(__name__), __title__)
STRUCTURE_LIST_ICON_RENDER_SIZE = 64
STRUCTURE_LIST_ICON_OUTPUT_SIZE = 32
QUERY_PARAM_TAGS = 'tags'


@login_required
@permission_required('structures.basic_access')
def index(request):
    url = reverse('structures:structure_list')
    if STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED:
        params = {
            QUERY_PARAM_TAGS: ','.join([
                x.name
                for x in StructureTag.objects.filter(is_default=True)
            ])
        }
        url += '?{}'.format(urllib.parse.urlencode(params))
    return redirect(url)


@login_required
@permission_required('structures.basic_access')
def structure_list(request):
    """main view showing the structure list"""

    active_tags = list()
    if request.method == 'POST':
        form = TagsFilterForm(data=request.POST)
        if form.is_valid():
            for name, activated in form.cleaned_data.items():
                if activated:
                    active_tags.append(StructureTag.objects.get(name=name))

            url = reverse('structures:structure_list')
            if active_tags:
                params = {
                    QUERY_PARAM_TAGS: ','.join([x.name for x in active_tags])
                }
                url += '?{}'.format(urllib.parse.urlencode(params))
            return redirect(url)
    else:
        tags_raw = request.GET.get(QUERY_PARAM_TAGS)
        if tags_raw:
            tags_parsed = tags_raw.split(',')
            active_tags = [
                x for x in StructureTag.objects.all().order_by('name')
                if x.name in tags_parsed
            ]

        form = TagsFilterForm(initial={x.name: True for x in active_tags})

    context = {
        'page_title': gettext_lazy(__title__),
        'active_tags': active_tags,
        'tags_filter_form': form,
        'tags_exist': StructureTag.objects.exists()
    }
    return render(request, 'structures/structure_list.html', context)


class StructuresRowConverter:
    """This class converts structure objects into rows for an HTML table"""
    def __init__(self):
        self._row = None
        self._structure = None
    
    def convert(self, structure) -> dict:
        self._row = {
            'structure_id': structure.id,
            'is_poco': structure.eve_type.is_poco
        }
        self._structure = structure
        self._convert_owner()
        self._convert_location()
        self._convert_type()
        self._convert_name()
        self._convert_services()
        self._convert_reinforcement_infos()
        self._convert_fuel_infos()
        self._convert_state()
        return self._row

    def _convert_owner(self):
        corporation = self._structure.owner.corporation
        if corporation.alliance:
            alliance_name = corporation.alliance.alliance_name
        else:
            alliance_name = ""

        self._row['owner'] = format_html(
            '<a href="{}">{}</a><br>{}',
            dotlan.corporation_url(corporation.corporation_name),
            corporation.corporation_name,
            alliance_name
        )
        self._row['corporation_icon'] = format_html(
            '<img src="{}" width="{}" height="{}"/>',
            corporation.logo_url(size=STRUCTURE_LIST_ICON_RENDER_SIZE),
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
        )
        self._row['alliance_name'] = alliance_name
        self._row['corporation_name'] = corporation.corporation_name
        
    def _convert_location(self):
        self._row['region_name'] = \
            self._structure.eve_solar_system.eve_constellation\
            .eve_region.name_localized
        self._row['solar_system_name'] = \
            self._structure.eve_solar_system.name_localized
        solar_system_url = dotlan.solar_system_url(
            self._structure.eve_solar_system.name
        )
        if self._structure.eve_moon:
            location_name = self._structure.eve_moon.name_localized
        elif self._structure.eve_planet:
            location_name = self._structure.eve_planet.name_localized
        else:
            location_name = self._row['solar_system_name']

        self._row['location'] = format_html(
            '<a href="{}">{}</a><br>{}',
            solar_system_url,
            add_no_wrap_html(location_name),
            add_no_wrap_html(self._row['region_name'])
        )

    def _convert_type(self):
        # category
        my_group = self._structure.eve_type.eve_group
        self._row['group_name'] = my_group.name_localized
        if my_group.eve_category:
            my_category = my_group.eve_category
            self._row['category_name'] = my_category.name_localized
            self._row['is_starbase'] = my_category.is_starbase
        else:
            self._row['category_name'] = ''
            self._row['is_starbase'] = None

        # type icon
        self._row['type_icon'] = format_html(
            '<img src="{}" width="{}" height="{}"/>',
            self._structure.eve_type.icon_url(
                size=STRUCTURE_LIST_ICON_RENDER_SIZE
            ),
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
        )

        # type name
        self._row['type_name'] = self._structure.eve_type.name_localized
        self._row['type'] = format_html(
            '{}<br>{}',
            add_no_wrap_html(self._row['type_name']),
            add_no_wrap_html(self._row['group_name'])
        )

    def _convert_name(self):
        self._row['structure_name'] = escape(self._structure.name)
        if self._structure.tags:
            self._row['structure_name'] += format_html(
                '<br>{}',
                mark_safe(' '.join([
                    x.html for x in self._structure.tags.all().order_by('name')
                ]))
            )

    def _convert_services(self):
        if self._row['is_poco'] or self._row['is_starbase']:
            self._row['services'] = gettext_lazy('N/A')
        else:
            services = list()
            services_qs = \
                self._structure.structureservice_set.all().order_by('name')
            for service in services_qs:
                service_name = add_no_wrap_html(format_html(
                    '<small>{}</small>', service.name_localized
                ))
                if service.state == StructureService.STATE_OFFLINE:
                    service_name = format_html('<del>{}</del>', service_name)
                
                services.append(service_name)
            self._row['services'] = '<br>'.join(services)

    def _convert_reinforcement_infos(self):
        self._row['is_reinforced'] = self._structure.is_reinforced
        self._row['is_reinforced_str'] = \
            yesno_str(self._structure.is_reinforced)

        if self._row['is_starbase']:
            self._row['reinforcement'] = gettext_lazy('N/A')
        else:
            if self._structure.reinforce_hour:
                self._row['reinforcement'] = '{:02d}:00'.format(
                    self._structure.reinforce_hour
                )
            else:
                self._row['reinforcement'] = ''

    def _convert_fuel_infos(self):
        self._row['is_low_power'] = self._structure.is_low_power
        self._row['is_low_power_str'] = yesno_str(self._structure.is_low_power)

        if self._row['is_poco'] or self._row['is_starbase']:
            fuel_expires_display = gettext_lazy('N/A')
            fuel_expires_timestamp = None
        else:
            if self._row['is_low_power']:
                fuel_expires_display = format_html_lazy(
                    '<span class="label label-default">{}</span>',
                    gettext_lazy('Low Power')
                )                    
                fuel_expires_timestamp = None
            elif self._structure.fuel_expires:
                fuel_expires_timestamp = self._structure.fuel_expires.isoformat()
                if STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE:
                    fuel_expires_display = timeuntil_str(
                        self._structure.fuel_expires - now()
                    )
                    if not fuel_expires_display:
                        fuel_expires_display = '?'
                        fuel_expires_timestamp = None
                else:
                    fuel_expires_display = \
                        self._structure.fuel_expires.strftime(DATETIME_FORMAT)
            else:
                fuel_expires_display = '?'
                fuel_expires_timestamp = None

        self._row['fuel_expires'] = {
            'display': add_no_wrap_html(fuel_expires_display),
            'timestamp': fuel_expires_timestamp
        }

    def _convert_state(self):
        self._row['state_str'] = self._structure.get_state_display()
        self._row['state_details'] = self._row['state_str']
        if self._structure.state_timer_end:
            self._row['state_details'] += format_html(
                '<br>{}',
                add_no_wrap_html(
                    self._structure.state_timer_end.strftime(DATETIME_FORMAT)
                )
            )


@login_required
@permission_required('structures.basic_access')
def structure_list_data(request):
    """returns structure list in JSON for AJAX call in structure_list view"""

    structure_rows = list()
    row_converter = StructuresRowConverter()
    for structure in _structures_query_for_user(request):        
        structure_rows.append(row_converter.convert(structure))

    return JsonResponse(structure_rows, safe=False)


def _structures_query_for_user(request):
    """returns query according to users permissions and current tags"""
    tags_raw = request.GET.get(QUERY_PARAM_TAGS)
    if tags_raw:
        tags = tags_raw.split(',')
    else:
        tags = None

    if request.user.has_perm('structures.view_all_structures'):
        structures_query = Structure.objects.all().select_related()
        if tags:
            structures_query = structures_query\
                .filter(tags__name__in=tags)\
                .distinct()

    else:
        corporation_ids = {
            character.character.corporation_id
            for character in request.user.character_ownerships.all()
        }
        corporations = list(
            EveCorporationInfo.objects.filter(
                corporation_id__in=corporation_ids
            )
        )
        if request.user.has_perm('structures.view_alliance_structures'):
            alliances = {
                corporation.alliance
                for corporation in corporations if corporation.alliance
            }
            for alliance in alliances:
                corporations += alliance.evecorporationinfo_set.all()

            corporations = list(set(corporations))

        structures_query = Structure.objects\
            .filter(owner__corporation__in=corporations) \
            .select_related()

    return structures_query


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
            format_html(
                gettext_lazy(
                    'You can only use your main or alt characters '
                    'to add corporations. '
                    'However, character %s is neither. '
                ) % format_html(
                    '<strong>{}</strong>', token_char.character_name
                )
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

        with transaction.atomic():
            owner, _ = Owner.objects.update_or_create(
                corporation=corporation,
                defaults={
                    'character': owned_char
                }
            )
            default_webhooks = Webhook.objects.filter(is_default=True)
            if default_webhooks:
                for webhook in default_webhooks:
                    owner.webhooks.add(webhook)
                owner.save()

        tasks.update_structures_for_owner.delay(
            owner_pk=owner.pk, user_pk=request.user.pk
        )
        messages_plus.info(
            request,            
            format_html(                
                gettext_lazy(
                    '%(corporation)s has been added with %(character)s '
                    'as sync character. We have started fetching structures '
                    'for this corporation. You will receive a report once '
                    'the process is finished.'
                ) % {
                    'corporation': format_html(
                        '<strong>{}</strong>', owner
                    ),
                    'character': format_html(
                        '<strong>{}</strong>', 
                        owner.character.character.character_name
                    )
                }
            )
        )
        if STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED:
            notify_admins(                
                message=gettext_lazy(
                    '%(corporation)s was added as new '
                    'structure owner by %(user)s.') % {                    
                        'corporation': owner.corporation.corporation_name,
                        'user': request.user.username
                },
                title='{}: Structure owner added: {}'.format(
                    __title__,
                    owner.corporation.corporation_name
                )
            )
    return redirect('structures:index')


def service_status(request):
    """public view to 3rd party monitoring

    This is view allows running a 3rd party monitoring on the status
    of this services. Service will be reported as down if any of the
    configured structure or notifications syncs fails or is delayed
    """
    status_ok = True
    for owner in Owner.objects.filter(is_included_in_service_status=True):
        status_ok = status_ok and owner.are_all_syncs_ok

    if status_ok:
        return HttpResponse(gettext_lazy('service is up'))
    else:
        return HttpResponseServerError(gettext_lazy('service is down'))
