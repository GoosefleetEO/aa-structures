import re
import urllib
from enum import IntEnum

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpResponse, HttpResponseServerError, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext, gettext_lazy
from esi.decorators import token_required
from eveuniverse.models import EveTypeDogmaAttribute

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.evelinks import dotlan
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger
from app_utils.allianceauth import notify_admins
from app_utils.datetime import DATETIME_FORMAT, timeuntil_str
from app_utils.logging import LoggerAddTag
from app_utils.messages import messages_plus
from app_utils.views import (
    BootstrapStyle,
    bootstrap_label_html,
    format_html_lazy,
    link_html,
    no_wrap_html,
    yesno_str,
    yesnonone_str,
)

from . import __title__, constants, tasks
from .app_settings import (
    STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED,
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_DEFAULT_PAGE_LENGTH,
    STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED,
    STRUCTURES_PAGING_ENABLED,
    STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE,
)
from .forms import TagsFilterForm
from .models import (
    Owner,
    OwnerAsset,
    Structure,
    StructureService,
    StructureTag,
    Webhook,
)

logger = LoggerAddTag(get_extension_logger(__name__), __title__)
STRUCTURE_LIST_ICON_RENDER_SIZE = 64
STRUCTURE_LIST_ICON_OUTPUT_SIZE = 32
QUERY_PARAM_TAGS = "tags"


@login_required
@permission_required("structures.basic_access")
def index(request):
    url = reverse("structures:main")
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
def main(request):
    """Main view"""
    active_tags = list()
    if request.method == "POST":
        form = TagsFilterForm(data=request.POST)
        if form.is_valid():
            for name, activated in form.cleaned_data.items():
                if activated:
                    active_tags.append(StructureTag.objects.get(name=name))

            url = reverse("structures:main")
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
    return render(request, "structures/main.html", context)


class StructuresRowBuilder:
    """This class build the HTML table rows from structure objects."""

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
        self._build_core_status()
        self._build_view_fit()
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
        try:
            my_category = my_group.eve_category
            self._row["category_name"] = my_category.name_localized
            self._row["is_starbase"] = my_category.is_starbase
        except AttributeError:
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
            no_wrap_html(link_html(structure_type.profile_url, self._row["type_name"])),
            no_wrap_html(self._row["group_name"]),
        )

        # poco
        self._row["is_poco"] = structure_type.is_poco

    def _build_name(self):
        self._row["structure_name"] = escape(self._structure.name)
        tags = []
        if self._structure.tags.exists():
            tags += [x.html for x in self._structure.tags.all()]
            self._row["structure_name"] += format_html(
                "<br>{}", mark_safe(" ".join(tags))
            )

    def _build_services(self):
        if self._row["is_poco"] or self._row["is_starbase"]:
            self._row["services"] = "-"
        else:
            services = list()
            for service in self._structure.services.all():
                service_name_html = no_wrap_html(
                    format_html("<small>{}</small>", service.name_localized)
                )
                if service.state == StructureService.State.OFFLINE:
                    service_name_html = format_html("<del>{}</del>", service_name_html)

                services.append({"name": service.name, "html": service_name_html})
            self._row["services"] = (
                "<br>".join(
                    map(lambda x: x["html"], sorted(services, key=lambda x: x["name"]))
                )
                if services
                else "-"
            )

    def _build_reinforcement_infos(self):
        self._row["is_reinforced"] = self._structure.is_reinforced
        self._row["is_reinforced_str"] = yesno_str(self._structure.is_reinforced)

        if self._row["is_starbase"]:
            self._row["reinforcement"] = "-"
        else:
            if self._structure.reinforce_hour is not None:
                self._row["reinforcement"] = "{:02d}:00".format(
                    self._structure.reinforce_hour
                )
            else:
                self._row["reinforcement"] = ""

    def _build_fuel_infos(self):
        if self._structure.eve_type.is_poco:
            fuel_expires_display = "-"
            fuel_expires_timestamp = None
        elif self._structure.is_low_power:
            fuel_expires_display = format_html_lazy(
                bootstrap_label_html(
                    self._structure.get_power_mode_display(), BootstrapStyle.WARNING
                )
            )
            fuel_expires_timestamp = None
        elif self._structure.is_abandoned:
            fuel_expires_display = format_html_lazy(
                bootstrap_label_html(
                    self._structure.get_power_mode_display(), BootstrapStyle.DANGER
                )
            )
            fuel_expires_timestamp = None
        elif self._structure.is_maybe_abandoned:
            fuel_expires_display = format_html_lazy(
                bootstrap_label_html(
                    self._structure.get_power_mode_display(), BootstrapStyle.WARNING
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
            fuel_expires_display = "-"
            fuel_expires_timestamp = None

        self._row["fuel_expires_at"] = {
            "display": no_wrap_html(fuel_expires_display),
            "timestamp": fuel_expires_timestamp,
        }

    def _build_online_infos(self):
        self._row["power_mode_str"] = self._structure.get_power_mode_display()
        if self._structure.eve_type.is_poco:
            last_online_at_display = "-"
            last_online_at_timestamp = None
        elif self._structure.is_full_power:
            last_online_at_display = format_html_lazy(
                bootstrap_label_html(
                    self._structure.get_power_mode_display(), BootstrapStyle.SUCCESS
                )
            )
            last_online_at_timestamp = None
        elif self._structure.is_maybe_abandoned:
            last_online_at_display = format_html_lazy(
                bootstrap_label_html(
                    self._structure.get_power_mode_display(), BootstrapStyle.WARNING
                )
            )
            last_online_at_timestamp = None
        elif self._structure.is_abandoned:
            last_online_at_display = format_html_lazy(
                bootstrap_label_html(
                    self._structure.get_power_mode_display(), BootstrapStyle.DANGER
                )
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

        self._row["state_str"] = (
            cap_first(self._structure.get_state_display())
            if not self._structure.eve_type.is_poco
            else "-"
        )
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

    def _build_core_status(self):
        if self._structure.eve_type.is_upwell_structure:
            if self._structure.has_core is True:
                has_core = True
                core_status = '<i class="fas fa-check" title="Core present"></i>'
            elif self._structure.has_core is False:
                has_core = False
                core_status = (
                    '<i class="fas fa-times text-danger title="Core absent"></i>'
                )
            else:
                has_core = None
                core_status = '<i class="fas fa-question" title="Status unknown"></i>'
        else:
            has_core = None
            core_status = "-"
        self._row["core_status"] = core_status
        self._row["core_status_str"] = yesnonone_str(has_core)

    def _build_view_fit(self):
        """Only enable view fit for structure types"""
        if self._structure.has_fitting and self._request.user.has_perm(
            "structures.view_structure_fit"
        ):
            ajax_structure_fit = reverse(
                "structures:structure_details",
                args=[self._row["structure_id"]],
            )
            self._row["view_fit"] = format_html(
                '<button type="button" class="btn btn-default" '
                'data-toggle="modal" data-target="#modalStructureFit" '
                f"data-ajax_structure_fit={ajax_structure_fit} "
                f'title="{gettext("Show fitting")}">'
                '<i class="fas fa-search"></i></button>'
            )
        else:
            self._row["view_fit"] = ""


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
    """Returns query according to users permissions and current tags."""
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
        if request.user.has_perm(
            "structures.view_corporation_structures"
        ) or request.user.has_perm("structures.view_alliance_structures"):
            corporation_ids = {
                character.character.corporation_id
                for character in request.user.character_ownerships.all()
            }
            corporations = list(
                EveCorporationInfo.objects.select_related("alliance").filter(
                    corporation_id__in=corporation_ids
                )
            )
        else:
            corporations = []

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

    structures_query = structures_query.prefetch_related("tags", "services")
    return structures_query


@login_required
@permission_required("structures.view_structure_fit")
def structure_details(request, structure_id):
    """Main view of the structure fit"""

    class Slot(IntEnum):
        HIGH = 14
        MEDIUM = 13
        LOW = 12
        RIG = 1137
        SERVICE = 2056

        def image_url(self) -> str:
            """Return url to image file for this slot variant"""
            id_map = {
                self.HIGH: "h",
                self.MEDIUM: "m",
                self.LOW: "l",
                self.RIG: "r",
                self.SERVICE: "s",
            }
            try:
                slot_num = type_attributes[self.value]
                return staticfiles_storage.url(
                    f"structures/img/pannel/{slot_num}{id_map[self.value]}.png"
                )
            except KeyError:
                return ""

    def extract_slot_assets(fittings: list, slot_name: str) -> list:
        """Return assets for slot sorted by slot number"""
        return [
            asset[0]
            for asset in sorted(
                [
                    (asset, asset.location_flag[-1])
                    for asset in fittings
                    if asset.location_flag.startswith(slot_name)
                ],
                key=lambda x: x[1],
            )
        ]

    structure = Structure.objects.select_related(
        "owner", "eve_type", "eve_solar_system"
    ).get(id=structure_id)
    type_attributes = {
        obj["eve_dogma_attribute_id"]: int(obj["value"])
        for obj in EveTypeDogmaAttribute.objects.filter(
            eve_type_id=structure.eve_type_id
        ).values("eve_dogma_attribute_id", "value")
    }
    slot_image_urls = {
        "high": Slot.HIGH.image_url(),
        "med": Slot.MEDIUM.image_url(),
        "low": Slot.LOW.image_url(),
        "rig": Slot.RIG.image_url(),
        "service": Slot.SERVICE.image_url(),
    }
    assets = OwnerAsset.objects.select_related("eve_type").filter(
        location_id=structure_id
    )
    high_slots = extract_slot_assets(assets, "HiSlot")
    med_slots = extract_slot_assets(assets, "MedSlot")
    low_slots = extract_slot_assets(assets, "LoSlot")
    rig_slots = extract_slot_assets(assets, "RigSlot")
    service_slots = extract_slot_assets(assets, "ServiceSlot")
    fighter_tubes = extract_slot_assets(assets, "FighterTube")
    assets_grouped = {"ammo_hold": [], "fighter_bay": [], "fuel_bay": []}
    for asset in assets:
        if asset.location_flag == "Cargo":
            assets_grouped["ammo_hold"].append(asset)
        elif asset.location_flag == "FighterBay":
            assets_grouped["fighter_bay"].append(asset)
        elif asset.location_flag == "StructureFuel":
            assets_grouped["fuel_bay"].append(asset)
        else:
            assets_grouped[asset.location_flag] = asset

    context = {
        "fitting": assets,
        "slots": slot_image_urls,
        "slot_assets": {
            "high_slots": high_slots,
            "med_slots": med_slots,
            "low_slots": low_slots,
            "rig_slots": rig_slots,
            "service_slots": service_slots,
            "fighter_tubes": fighter_tubes,
        },
        "assets_grouped": assets_grouped,
        "structure": structure,
        "last_updated": structure.owner.assets_last_sync,
    }
    return render(request, "structures/modals/structure_details.html", context)


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
            with translation.override(STRUCTURES_DEFAULT_LANGUAGE):
                notify_admins(
                    message=gettext_lazy(
                        "%(corporation)s was added as new "
                        "structure owner by %(user)s."
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
    """Public view to 3rd party monitoring.

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


def poco_list_data(request) -> JsonResponse:
    pocos = Structure.objects.select_related(
        "eve_planet",
        "eve_planet__eve_type",
        "eve_type",
        "eve_type__eve_group",
        "eve_solar_system",
        "eve_solar_system__eve_constellation__eve_region",
    ).filter(eve_type__eve_group__eve_category_id=constants.EVE_CATEGORY_ID_ORBITAL)
    data = list()
    for poco in pocos:
        if poco.eve_solar_system.is_low_sec:
            space_badge_type = "warning"
        elif poco.eve_solar_system.is_high_sec:
            space_badge_type = "success"
        else:
            space_badge_type = "danger"
        solar_system_html = format_html(
            "{}<br>{}",
            link_html(
                dotlan.solar_system_url(poco.eve_solar_system.name),
                poco.eve_solar_system.name,
            ),
            bootstrap_label_html(
                text=poco.eve_solar_system.space_type, label=space_badge_type
            ),
        )
        type_icon = format_html(
            '<img src="{}" width="{}" height="{}"/>',
            poco.eve_type.icon_url(size=STRUCTURE_LIST_ICON_RENDER_SIZE),
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
            STRUCTURE_LIST_ICON_OUTPUT_SIZE,
        )
        try:
            match = re.search(r"Planet \((\S+)\)", poco.eve_planet.eve_type.name)
        except AttributeError:
            planet_name = planet_type_name = "?"
            planet_type_icon = ""
        else:
            if match:
                planet_type_name = match.group(1)
            else:
                planet_type_name = ""
            planet_name = poco.eve_planet.name
            planet_type_icon = format_html(
                '<img src="{}" width="{}" height="{}"/>',
                poco.eve_planet.eve_type.icon_url(size=STRUCTURE_LIST_ICON_RENDER_SIZE),
                STRUCTURE_LIST_ICON_OUTPUT_SIZE,
                STRUCTURE_LIST_ICON_OUTPUT_SIZE,
            )

        data.append(
            {
                "id": poco.id,
                "type_icon": type_icon,
                "region": poco.eve_solar_system.eve_constellation.eve_region.name,
                "solar_system_html": {
                    "display": solar_system_html,
                    "sort": poco.eve_solar_system.name,
                },
                "solar_system": poco.eve_solar_system.name,
                "planet": planet_name,
                "planet_type_icon": planet_type_icon,
                "planet_type_name": planet_type_name,
                "space_type": poco.eve_solar_system.space_type,
            }
        )
    return JsonResponse(data, safe=False)
