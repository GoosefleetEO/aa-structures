import logging
import urllib

from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse, HttpResponseServerError
from django.shortcuts import render, redirect, reverse
from django.utils.html import format_html, mark_safe, escape
from django.utils.translation import ngettext_lazy
from django.utils.timesince import timeuntil

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from esi.decorators import token_required

from . import evelinks, tasks, __title__
from .app_settings import (
    STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED,
    STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE,
    STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED
)
from .forms import TagsFilterForm
from .models import Owner, Structure, StructureTag, StructureService, Webhook
from .utils import messages_plus, DATETIME_FORMAT, notify_admins, LoggerAddTag


logger = LoggerAddTag(logging.getLogger(__name__), __package__)
STRUCTURE_LIST_ICON_RENDER_SIZE = 64
STRUCTURE_LIST_ICON_OUTPUT_SIZE = 32
QUERY_PARAM_TAGS = 'tags'

TIME_STRINGS = {
    'year': ngettext_lazy('%d y', '%d y'),
    'month': ngettext_lazy('%d m', '%d m'),
    'week': ngettext_lazy('%d w', '%d w'),
    'day': ngettext_lazy('%d d', '%d d'),
    'hour': ngettext_lazy('%d h', '%d h'),
    'minute': ngettext_lazy('%d m', '%d m'),
}


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
        'page_title': 'Alliance Structures',
        'active_tags': active_tags,
        'tags_filter_form': form,
        'tags_exist': StructureTag.objects.exists()
    }
    return render(request, 'structures/structure_list.html', context)


@login_required
@permission_required('structures.basic_access')
def structure_list_data(request):
    """returns structure list in JSON for AJAX call in structure_list view"""

    def add_no_wrap_html(text: str) -> str:
        """add no-wrap HTML to text"""
        return format_html(
            '<span style="white-space: nowrap;">{}</span>',
            mark_safe(text)
        )

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

    structures_data = list()
    for structure in structures_query:
        row = {
            'structure_id': structure.id,
            'is_poco': structure.eve_type.is_poco
        }

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

        row['owner'] = format_html(
            '<a href="{}">{}</a><br>{}',
            corporation_url,
            corporation.corporation_name,
            alliance_name
        )
        row['alliance_name'] = alliance_name
        row['corporation_name'] = corporation.corporation_name

        # corporation icon
        row['corporation_icon'] = format_html(
            '<img src="{}" width="{}" height="{}"/>',
            corporation.logo_url(size=STRUCTURE_LIST_ICON_RENDER_SIZE),
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
        )

        # location
        row['region_name'] = \
            structure.eve_solar_system.eve_constellation.eve_region.name
        row['solar_system_name'] = structure.eve_solar_system.name
        solar_system_url = evelinks.get_entity_profile_url_by_name(
            evelinks.ESI_CATEGORY_SOLARSYSTEM,
            structure.eve_solar_system.name
        )
        if structure.eve_moon:
            location_name = structure.eve_moon.name
        elif structure.eve_planet:
            location_name = structure.eve_planet.name
        else:
            location_name = structure.eve_solar_system.name

        row['location'] = format_html(
            '<a href="{}">{}</a><br>{}',
            solar_system_url,
            add_no_wrap_html(location_name),
            add_no_wrap_html(row['region_name'])
        )

        # category
        my_group = structure.eve_type.eve_group
        row['group_name'] = my_group.name
        if my_group.eve_category:
            my_category = my_group.eve_category
            row['category_name'] = my_category.name
            row['is_starbase'] = my_category.is_starbase
        else:
            row['category_name'] = ''
            row['is_starbase'] = None

        # type icon
        row['type_icon'] = format_html(
            '<img src="{}" width="{}" height="{}"/>',
            structure.eve_type.icon_url(size=STRUCTURE_LIST_ICON_RENDER_SIZE),
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
        )

        # type name
        row['type_name'] = structure.eve_type.name
        row['type'] = format_html(
            '{}<br>{}',
            add_no_wrap_html(row['type_name']),
            add_no_wrap_html(row['group_name'])
        )

        # structure name
        row['structure_name'] = escape(structure.name)
        if structure.tags:
            row['structure_name'] += format_html(
                '<br>{}',
                mark_safe(' '.join([
                    x.html
                    for x in structure.tags.all().order_by('name')
                ]))
            )

        # services
        if row['is_poco'] or row['is_starbase']:
            row['services'] = 'N/A'
        else:
            services = list()
            services_qs = structure.structureservice_set.all().order_by('name')
            for service in services_qs:
                if service.state == StructureService.STATE_OFFLINE:
                    service_name = format_html('<del>{}</del>', service.name)
                else:
                    service_name = service.name
                services.append(service_name)
            row['services'] = '<br>'.join(services)

        # add reinforcement infos
        row['is_reinforced'] = structure.is_reinforced
        row['is_reinforced_str'] = 'yes' if structure.is_reinforced else 'no'

        if structure.reinforce_hour:
            row['reinforcement'] = '{:02d}:00'.format(
                structure.reinforce_hour
            )
        else:
            row['reinforcement'] = ''

        # low power state
        row['is_low_power'] = structure.is_low_power
        row['is_low_power_str'] = 'yes' if structure.is_low_power else 'no'

        # add low power label or date when fuel runs out
        if row['is_poco'] or row['is_starbase']:
            fuel_expires_display = 'N/A'
            fuel_expires_timestamp = None
        else:
            if row['is_low_power']:
                fuel_expires_display = \
                    '<span class="label label-default">Low Power</span>'
                fuel_expires_timestamp = None
            elif structure.fuel_expires:
                fuel_expires_timestamp = structure.fuel_expires.isoformat()
                if STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE:
                    fuel_expires_display = timeuntil(
                        structure.fuel_expires,
                        time_strings=TIME_STRINGS
                    )
                else:
                    fuel_expires_display = \
                        structure.fuel_expires.strftime(DATETIME_FORMAT)
            else:
                fuel_expires_display = '?'
                fuel_expires_timestamp = None

        row['fuel_expires'] = {
            'display': fuel_expires_display,
            'timestamp': fuel_expires_timestamp
        }
        # state
        row['state_str'] = structure.state_str
        row['state_details'] = row['state_str']
        if structure.state_timer_end:
            row['state_details'] += format_html(
                '<br>{}',
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
            format_html(
                'You can only use your main or alt characters '
                'to add corporations. '
                'However, character <strong>{}</strong> is neither. ',
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

        with transaction.atomic():
            owner, created = Owner.objects.update_or_create(
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
            owner_pk=owner.pk,
            force_sync=True,
            user_pk=request.user.pk
        )
        messages_plus.info(
            request,
            format_html(
                '<strong>{}</strong> has been added with <strong>{}</strong> '
                'as sync character. '
                'We have started fetching structures for this corporation. '
                'You will receive a report once the process is finished.',
                owner,
                owner.character.character.character_name
            )
        )
        if STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED:
            notify_admins(
                message='{} was added as new structure owner by {}.'.format(
                    owner.corporation.corporation_name,
                    request.user.username
                ),
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
    ok = True
    for owner in Owner.objects.filter(is_included_in_service_status=True):
        ok = ok and owner.is_all_syncs_ok()

    if ok:
        return HttpResponse('service is up')
    else:
        return HttpResponseServerError('service is down')
