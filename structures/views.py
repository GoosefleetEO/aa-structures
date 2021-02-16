import urllib

from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse, HttpResponseServerError
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext_lazy

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.eveonline.evelinks import dotlan
from allianceauth.services.hooks import get_extension_logger

from app_utils.allianceauth import notify_admins
from app_utils.datetime import DATETIME_FORMAT, timeuntil_str
from app_utils.logging import LoggerAddTag
from app_utils.messages import messages_plus
from app_utils.views import (
    format_html_lazy,
    no_wrap_html,
    yesno_str,
    bootstrap_label_html,
)

from esi.decorators import token_required

from . import tasks, __title__
from .app_settings import (
    STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED,
    STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE,
    STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED,
    STRUCTURES_DEFAULT_PAGE_LENGTH,
    STRUCTURES_PAGING_ENABLED,
)
from .forms import TagsFilterForm
from .models import Owner, Structure, StructureTag, StructureService, Webhook


logger = LoggerAddTag(get_extension_logger(__name__), __title__)
STRUCTURE_LIST_ICON_RENDER_SIZE = 64
STRUCTURE_LIST_ICON_OUTPUT_SIZE = 32
QUERY_PARAM_TAGS = "tags"


@login_required
@permission_required("structures.basic_access")
def index(request):
    url = reverse("structures:structure_list")
    if STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED:
        params = {
            QUERY_PARAM_TAGS: ",".join(
                [x.name for x in StructureTag.objects.filter(is_default=True)]
            )
        }
        url += "?{}".format(urllib.parse.urlencode(params))
    return redirect(url)


@login_required
@permission_required("structures.basic_access")
def structure_list(request):
    """main view showing the structure list"""

    active_tags = list()
    if request.method == "POST":
        form = TagsFilterForm(data=request.POST)
        if form.is_valid():
            for name, activated in form.cleaned_data.items():
                if activated:
                    active_tags.append(StructureTag.objects.get(name=name))

            url = reverse("structures:structure_list")
            if active_tags:
                params = {QUERY_PARAM_TAGS: ",".join([x.name for x in active_tags])}
                url += "?{}".format(urllib.parse.urlencode(params))
            return redirect(url)
    else:
        tags_raw = request.GET.get(QUERY_PARAM_TAGS)
        if tags_raw:
            tags_parsed = tags_raw.split(",")
            active_tags = [
                x for x in StructureTag.objects.all() if x.name in tags_parsed
            ]

        form = TagsFilterForm(initial={x.name: True for x in active_tags})

    context = {
        "page_title": gettext_lazy(__title__),
        "active_tags": active_tags,
        "tags_filter_form": form,
        "tags_exist": StructureTag.objects.exists(),
        "data_tables_page_length": STRUCTURES_DEFAULT_PAGE_LENGTH,
        "data_tables_paging": STRUCTURES_PAGING_ENABLED,
    }
    return render(request, "structures/structure_list.html", context)


class StructuresRowBuilder:
    """This class build the HTML table rows from structure objects"""

    def __init__(self, request):
        self._row = None
        self._structure = None
        self._request = request

    def convert(self, structure) -> dict:
        self._row = {"structure_id": structure.id}
        self._structure = structure
        self._build_owner()
        self._build_location()
        self._build_type()
        self._build_name()
        self._build_services()
        self._build_reinforcement_infos()
        self._build_fuel_infos()
        self._build_online_infos()
        self._build_state()
        return self._row

    def _build_owner(self):
        corporation = self._structure.owner.corporation
        if corporation.alliance:
            alliance_name = corporation.alliance.alliance_name
        else:
            alliance_name = ""

        self._row["owner"] = format_html(
            '<a href="{}">{}</a><br>{}',
            dotlan.corporation_url(corporation.corporation_name),
            corporation.corporation_name,
            alliance_name,
        )
        self._row["corporation_icon"] = format_html(
            '<img src="{}" width="{}" height="{}"/>',
            corporation.logo_url(size=STRUCTURE_LIST_ICON_RENDER_SIZE),
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
        )
        self._row["alliance_name"] = alliance_name
        self._row["corporation_name"] = corporation.corporation_name

    def _build_location(self):
        solar_system = self._structure.eve_solar_system

        # location
        self._row[
            "region_name"
        ] = solar_system.eve_constellation.eve_region.name_localized
        self._row["solar_system_name"] = solar_system.name_localized
        solar_system_url = dotlan.solar_system_url(solar_system.name)
        if self._structure.eve_moon:
            location_name = self._structure.eve_moon.name_localized
        elif self._structure.eve_planet:
            location_name = self._structure.eve_planet.name_localized
        else:
            location_name = self._row["solar_system_name"]

        self._row["location"] = format_html(
            '<a href="{}">{}</a><br><em>{}</em>',
            solar_system_url,
            no_wrap_html(location_name),
            no_wrap_html(self._row["region_name"]),
        )

    def _build_type(self):
        structure_type = self._structure.eve_type
        # category
        my_group = structure_type.eve_group
        self._row["group_name"] = my_group.name_localized
        if my_group.eve_category:
            my_category = my_group.eve_category
            self._row["category_name"] = my_category.name_localized
            self._row["is_starbase"] = my_category.is_starbase
        else:
            self._row["category_name"] = ""
            self._row["is_starbase"] = None

        # type icon
        self._row["type_icon"] = format_html(
            '<img src="{}" width="{}" height="{}"/>',
            structure_type.icon_url(size=STRUCTURE_LIST_ICON_RENDER_SIZE),
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
        )

        # type name
        self._row["type_name"] = structure_type.name_localized
        self._row["type"] = format_html(
            "{}<br><em>{}</em>",
            no_wrap_html(self._row["type_name"]),
            no_wrap_html(self._row["group_name"]),
        )

        # poco
        self._row["is_poco"] = structure_type.is_poco

    def _build_name(self):
        self._row["structure_name"] = escape(self._structure.name)
        tags = []
        if self._structure.tags:
            tags += [x.html for x in self._structure.tags.all()]
            self._row["structure_name"] += format_html(
                "<br>{}", mark_safe(" ".join(tags))
            )

    def _build_services(self):
        if self._row["is_poco"] or self._row["is_starbase"]:
            self._row["services"] = gettext_lazy("N/A")
        else:
            services = list()
            services_qs = self._structure.structureservice_set.all().order_by("name")
            for service in services_qs:
                service_name = no_wrap_html(
                    format_html("<small>{}</small>", service.name_localized)
                )
                if service.state == StructureService.STATE_OFFLINE:
                    service_name = format_html("<del>{}</del>", service_name)

                services.append(service_name)
            services_str = "<br>".join(services) if services else "-"
            self._row["services"] = services_str

    def _build_reinforcement_infos(self):
        self._row["is_reinforced"] = self._structure.is_reinforced
        self._row["is_reinforced_str"] = yesno_str(self._structure.is_reinforced)

        if self._row["is_starbase"]:
            self._row["reinforcement"] = gettext_lazy("N/A")
        else:
            if self._structure.reinforce_hour:
                self._row["reinforcement"] = "{:02d}:00".format(
                    self._structure.reinforce_hour
                )
            else:
                self._row["reinforcement"] = ""

    def _build_fuel_infos(self):
        if self._structure.eve_type.is_poco:
            fuel_expires_display = "N/A"
            fuel_expires_timestamp = None
        elif self._structure.is_low_power:
            fuel_expires_display = format_html_lazy(
                bootstrap_label_html(
                    self._structure.get_power_mode_display(), "warning"
                )
            )
            fuel_expires_timestamp = None
        elif self._structure.is_abandoned:
            fuel_expires_display = format_html_lazy(
                bootstrap_label_html(self._structure.get_power_mode_display(), "danger")
            )
            fuel_expires_timestamp = None
        elif self._structure.is_maybe_abandoned:
            fuel_expires_display = format_html_lazy(
                bootstrap_label_html(
                    self._structure.get_power_mode_display(), "warning"
                )
            )
            fuel_expires_timestamp = None
        elif self._structure.fuel_expires_at:
            fuel_expires_timestamp = self._structure.fuel_expires_at.isoformat()
            if STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE:
                fuel_expires_display = timeuntil_str(
                    self._structure.fuel_expires_at - now(), show_seconds=False
                )
                if not fuel_expires_display:
                    fuel_expires_display = "?"
                    fuel_expires_timestamp = None
            else:
                if self._structure.fuel_expires_at >= now():
                    fuel_expires_display = self._structure.fuel_expires_at.strftime(
                        DATETIME_FORMAT
                    )
                else:
                    fuel_expires_display = "?"
                    fuel_expires_timestamp = None
        else:
            fuel_expires_display = gettext_lazy("N/A")
            fuel_expires_timestamp = None

        self._row["fuel_expires_at"] = {
            "display": no_wrap_html(fuel_expires_display),
            "timestamp": fuel_expires_timestamp,
        }

    def _build_online_infos(self):
        self._row["power_mode_str"] = self._structure.get_power_mode_display()
        if self._structure.eve_type.is_poco:
            last_online_at_display = "N/A"
            last_online_at_timestamp = None
        elif self._structure.is_full_power:
            last_online_at_display = format_html_lazy(
                bootstrap_label_html(
                    self._structure.get_power_mode_display(), "success"
                )
            )
            last_online_at_timestamp = None
        elif self._structure.is_maybe_abandoned:
            last_online_at_display = format_html_lazy(
                bootstrap_label_html(
                    self._structure.get_power_mode_display(), "warning"
                )
            )
            last_online_at_timestamp = None
        elif self._structure.is_abandoned:
            last_online_at_display = format_html_lazy(
                bootstrap_label_html(self._structure.get_power_mode_display(), "danger")
            )
            last_online_at_timestamp = None
        elif self._structure.last_online_at:
            last_online_at_timestamp = self._structure.last_online_at.isoformat()
            if STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE:
                last_online_at_display = timeuntil_str(
                    now() - self._structure.last_online_at, show_seconds=False
                )
                if not last_online_at_display:
                    last_online_at_display = "?"
                    last_online_at_timestamp = None
                else:
                    last_online_at_display = "- " + last_online_at_display
            else:
                last_online_at_display = self._structure.last_online_at.strftime(
                    DATETIME_FORMAT
                )
        else:
            last_online_at_display = "-"
            last_online_at_timestamp = None

        self._row["last_online_at"] = {
            "display": no_wrap_html(last_online_at_display),
            "timestamp": last_online_at_timestamp,
        }

    def _build_state(self):
        def cap_first(s: str) -> str:
            return s[0].upper() + s[1::]

        self._row["state_str"] = cap_first(self._structure.get_state_display())
        self._row["state_details"] = self._row["state_str"]
        if self._structure.state_timer_end:
            self._row["state_details"] += format_html(
                "<br>{}",
                no_wrap_html(self._structure.state_timer_end.strftime(DATETIME_FORMAT)),
            )

        if (
            self._request.user.has_perm("structures.view_all_unanchoring_status")
            and self._structure.unanchors_at
        ):
            self._row["state_details"] += format_html(
                "<br>Unanchoring until {}",
                no_wrap_html(self._structure.unanchors_at.strftime(DATETIME_FORMAT)),
            )


@login_required
@permission_required("structures.basic_access")
def structure_list_data(request):
    """returns structure list in JSON for AJAX call in structure_list view"""

    structure_rows = list()
    row_converter = StructuresRowBuilder(request)
    for structure in _structures_query_for_user(request):
        structure_rows.append(row_converter.convert(structure))

    return JsonResponse(structure_rows, safe=False)


def _structures_query_for_user(request):
    """returns query according to users permissions and current tags"""
    tags_raw = request.GET.get(QUERY_PARAM_TAGS)
    if tags_raw:
        tags = tags_raw.split(",")
    else:
        tags = None

    if request.user.has_perm("structures.view_all_structures"):
        structures_query = Structure.objects.select_related_defaults()
        if tags:
            structures_query = structures_query.filter(tags__name__in=tags).distinct()

    else:
        corporation_ids = {
            character.character.corporation_id
            for character in request.user.character_ownerships.all()
        }
        corporations = list(
            EveCorporationInfo.objects.select_related("alliance").filter(
                corporation_id__in=corporation_ids
            )
        )
        if request.user.has_perm("structures.view_alliance_structures"):
            alliances = {
                corporation.alliance
                for corporation in corporations
                if corporation.alliance
            }
            for alliance in alliances:
                corporations += alliance.evecorporationinfo_set.all()

            corporations = list(set(corporations))

        structures_query = Structure.objects.select_related_defaults().filter(
            owner__corporation__in=corporations
        )

    return structures_query


@login_required
@permission_required("structures.add_structure_owner")
@token_required(scopes=Owner.get_esi_scopes())
def add_structure_owner(request, token):
    token_char = EveCharacter.objects.get(character_id=token.character_id)

    success = True
    try:
        owned_char = CharacterOwnership.objects.get(
            user=request.user, character=token_char
        )
    except CharacterOwnership.DoesNotExist:
        messages_plus.error(
            request,
            format_html(
                gettext_lazy(
                    "You can only use your main or alt characters "
                    "to add corporations. "
                    "However, character %s is neither. "
                )
                % format_html("<strong>{}</strong>", token_char.character_name)
            ),
        )
        success = False
        owned_char = None

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
                corporation=corporation, defaults={"character": owned_char}
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
                    "%(corporation)s has been added with %(character)s "
                    "as sync character. We have started fetching structures "
                    "for this corporation. You will receive a report once "
                    "the process is finished."
                )
                % {
                    "corporation": format_html("<strong>{}</strong>", owner),
                    "character": format_html(
                        "<strong>{}</strong>", owner.character.character.character_name
                    ),
                }
            ),
        )
        if STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED:
            notify_admins(
                message=gettext_lazy(
                    "%(corporation)s was added as new " "structure owner by %(user)s."
                )
                % {
                    "corporation": owner.corporation.corporation_name,
                    "user": request.user.username,
                },
                title="{}: Structure owner added: {}".format(
                    __title__, owner.corporation.corporation_name
                ),
            )
    return redirect("structures:index")


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
        return HttpResponse(gettext_lazy("service is up"))
    else:
        return HttpResponseServerError(gettext_lazy("service is down"))
