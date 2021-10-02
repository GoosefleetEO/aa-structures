import re
import urllib
from enum import IntEnum

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q
from django.http import (
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext as _
from esi.decorators import token_required
from eveuniverse.core import eveimageserver
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
    image_html,
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


def default_if_none(value, default=None):
    """Return default if a value is None."""
    if value is None:
        return default
    return value


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
        "page_title": _(__title__),
        "active_tags": active_tags,
        "tags_filter_form": form,
        "tags_exist": StructureTag.objects.exists(),
        "data_tables_page_length": STRUCTURES_DEFAULT_PAGE_LENGTH,
        "data_tables_paging": STRUCTURES_PAGING_ENABLED,
        "last_updated": Owner.objects.structures_last_updated(),
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
        self._build_details_widget()
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
        if not self._structure.owner.is_structure_sync_fresh:
            update_warning_html = format_html(
                '<i class="fas fa-exclamation-circle text-warning" '
                'title="Data has not been updated for a while and may be outdated."></i>'
            )
        else:
            update_warning_html = ""
        self._row["corporation_icon"] = format_html(
            '<span class="nowrap">{} <img src="{}" width="{}" height="{}"/></span>',
            update_warning_html,
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
            self._row["is_starbase"] = self._structure.is_starbase
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
        self._row["is_poco"] = self._structure.is_poco

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
        if self._structure.is_poco:
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
        if self._structure.is_poco:
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
            if not self._structure.is_poco
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
        if self._structure.is_upwell_structure:
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

    def _build_details_widget(self):
        """Add details widget when applicable"""
        if self._structure.has_fitting and self._request.user.has_perm(
            "structures.view_structure_fit"
        ):
            ajax_url = reverse(
                "structures:structure_details",
                args=[self._row["structure_id"]],
            )
            self._row["details"] = format_html(
                '<button type="button" class="btn btn-default" '
                'data-toggle="modal" data-target="#modalUpwellDetails" '
                f"data-ajax_url={ajax_url} "
                f'title="{_("Show fitting")}">'
                '<i class="fas fa-search"></i></button>'
            )
        elif self._structure.has_poco_details:
            ajax_url = reverse(
                "structures:poco_details",
                args=[self._row["structure_id"]],
            )
            self._row["details"] = format_html(
                '<button type="button" class="btn btn-default" '
                'data-toggle="modal" data-target="#modalPocoDetails" '
                f"data-ajax_url={ajax_url} "
                f'title="{_("Show details")}">'
                '<i class="fas fa-search"></i></button>'
            )
        else:
            self._row["details"] = ""


@login_required
@permission_required("structures.basic_access")
def structure_list_data(request):
    """returns structure list in JSON for AJAX call in structure_list view"""
    tags_raw = request.GET.get(QUERY_PARAM_TAGS)
    tags = tags_raw.split(",") if tags_raw else None
    row_converter = StructuresRowBuilder(request)
    structure_rows = [
        row_converter.convert(structure)
        for structure in Structure.objects.visible_for_user(request.user, tags)
    ]

    return JsonResponse(structure_rows, safe=False)


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
        "last_updated": structure.owner.assets_last_update_at,
    }
    return render(request, "structures/modals/structure_details.html", context)


@login_required
@permission_required("structures.basic_access")
def poco_details(request, structure_id):
    """Shows details modal for a POCO"""

    try:
        poco = (
            Structure.objects.select_related(
                "owner", "eve_type", "eve_solar_system", "poco_details"
            )
            .filter(eve_type=constants.EVE_TYPE_ID_POCO, poco_details__isnull=False)
            .get(id=structure_id)
        )
    except Structure.DoesNotExist:
        logger.warning("Could not find poco details for structure %s", structure_id)
        return HttpResponseNotFound()
    context = {
        "poco": poco,
        "details": poco.poco_details,
        "poco_image_url": eveimageserver.type_render_url(
            type_id=constants.EVE_TYPE_ID_POCO, size=256
        ),
        "last_updated": poco.last_updated_at,
    }
    return render(request, "structures/modals/poco_details.html", context)


@login_required
@permission_required("structures.add_structure_owner")
@token_required(scopes=Owner.get_esi_scopes())
def add_structure_owner(request, token):
    token_char = get_object_or_404(EveCharacter, character_id=token.character_id)
    try:
        character_ownership = CharacterOwnership.objects.get(
            user=request.user, character=token_char
        )
    except CharacterOwnership.DoesNotExist:
        character_ownership = None
        messages_plus.error(
            request,
            format_html(
                _(
                    "You can only use your main or alt characters "
                    "to add corporations. "
                    "However, character %s is neither. "
                )
                % format_html("<strong>{}</strong>", token_char.character_name)
            ),
        )
        return redirect("structures:index")
    try:
        corporation = EveCorporationInfo.objects.get(
            corporation_id=token_char.corporation_id
        )
    except EveCorporationInfo.DoesNotExist:
        corporation = EveCorporationInfo.objects.create_corporation(
            token_char.corporation_id
        )
    owner, created = Owner.objects.update_or_create(
        corporation=corporation, defaults={"is_active": True}
    )
    owner.add_character(character_ownership)
    if created:
        default_webhooks = Webhook.objects.filter(is_default=True)
        if default_webhooks:
            for webhook in default_webhooks:
                owner.webhooks.add(webhook)
            owner.save()

    if owner.characters.count() == 1:
        tasks.update_all_for_owner.delay(owner_pk=owner.pk, user_pk=request.user.pk)
        messages_plus.info(
            request,
            format_html(
                _(
                    "%(corporation)s has been added with %(character)s "
                    "as sync character. "
                    "We have started fetching structures and notifications "
                    "for this corporation and you will receive a report once "
                    "the process is finished."
                )
                % {
                    "corporation": format_html("<strong>{}</strong>", owner),
                    "character": format_html("<strong>{}</strong>", token_char),
                }
            ),
        )
        if STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED:
            with translation.override(STRUCTURES_DEFAULT_LANGUAGE):
                notify_admins(
                    message=_(
                        "%(corporation)s was added as new "
                        "structure owner by %(user)s."
                    )
                    % {"corporation": owner, "user": request.user.username},
                    title=_("%s: Structure owner added: %s") % (__title__, owner),
                )
    else:
        messages_plus.info(
            request,
            format_html(
                _(
                    "%(character)s has been added to %(corporation)s "
                    "as sync character. "
                    "You now have %(characters_count)d sync character(s) configured."
                )
                % {
                    "corporation": format_html("<strong>{}</strong>", owner),
                    "character": format_html("<strong>{}</strong>", token_char),
                    "characters_count": owner.characters_count(),
                }
            ),
        )
        if STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED:
            with translation.override(STRUCTURES_DEFAULT_LANGUAGE):
                notify_admins(
                    message=_(
                        "%(character)s was added as sync character to "
                        "%(corporation)s by %(user)s.\n"
                        "We now have %(characters_count)d sync character(s) configured."
                    )
                    % {
                        "character": token_char,
                        "corporation": owner,
                        "user": request.user.username,
                        "characters_count": owner.characters_count(),
                    },
                    title=_("%s: Character added to: %s") % (__title__, owner),
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
        return HttpResponse(_("service is up"))
    else:
        return HttpResponseServerError(_("service is down"))


def poco_list_data(request) -> JsonResponse:
    pocos = (
        Structure.objects.select_related(
            "eve_planet",
            "eve_planet__eve_type",
            "eve_type",
            "eve_type__eve_group",
            "eve_solar_system",
            "eve_solar_system__eve_constellation__eve_region",
            "poco_details",
            "owner__corporation",
        )
        .filter(eve_type__eve_group__eve_category_id=constants.EVE_CATEGORY_ID_ORBITAL)
        .filter(owner__are_pocos_public=True)
    )
    data = list()
    try:
        main_character = request.user.profile.main_character
    except (AttributeError, ObjectDoesNotExist):
        main_character = None
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

        tax = None
        has_access = None
        if main_character:
            try:
                details = poco.poco_details
            except (AttributeError, ObjectDoesNotExist):
                ...
            else:
                tax = details.tax_for_character(main_character)
                has_access = details.has_character_access(main_character)

        if has_access is True:
            has_access_html = (
                '<i class="fas fa-check text-success" title="Has access"></i>'
            )
            has_access_str = _("yes")
        elif has_access is False:
            has_access_html = (
                '<i class="fas fa-times text-danger" title="No access"></i>'
            )
            has_access_str = _("no")
        else:
            has_access_html = '<i class="fas fa-question" title="Unknown"></i>'
            has_access_str = "?"

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
                "has_access_html": has_access_html,
                "has_access_str": has_access_str,
                "tax": f"{tax * 100:.0f} %" if tax else "?",
            }
        )
    return JsonResponse(data, safe=False)


@login_required
@permission_required("structures.basic_access")
def structure_summary_data(request):
    summary_qs = (
        Structure.objects.values(
            "owner__corporation__corporation_id",
            "owner__corporation__corporation_name",
            "owner__corporation__alliance__alliance_name",
        )
        .annotate(
            ec_count=Count(
                id,
                filter=Q(eve_type__eve_group=constants.EVE_GROUP_ID_ENGINERING_COMPLEX),
            )
        )
        .annotate(
            refinery_count=Count(
                id,
                filter=Q(eve_type__eve_group=constants.EVE_GROUP_ID_REFINERY),
            )
        )
        .annotate(
            citadel_count=Count(
                id,
                filter=Q(eve_type__eve_group=constants.EVE_GROUP_ID_CITADEL),
            )
        )
        .annotate(
            upwell_count=Count(
                id,
                filter=Q(
                    eve_type__eve_group__eve_category=constants.EVE_CATEGORY_ID_STRUCTURE
                ),
            )
        )
        .annotate(poco_count=Count(id, filter=Q(eve_type=constants.EVE_TYPE_ID_POCO)))
        .annotate(
            starbase_count=Count(
                id,
                filter=Q(
                    eve_type__eve_group__eve_category=constants.EVE_CATEGORY_ID_STARBASE
                ),
            )
        )
    )
    data = list()
    for row in summary_qs:
        data.append(
            {
                "id": int(row["owner__corporation__corporation_id"]),
                "corporation_icon": image_html(
                    eveimageserver.corporation_logo_url(
                        row["owner__corporation__corporation_id"], size=32
                    )
                ),
                "corporation_name": row["owner__corporation__corporation_name"],
                "alliance_name": default_if_none(
                    row["owner__corporation__alliance__alliance_name"], ""
                ),
                "citadel_count": row["citadel_count"],
                "ec_count": row["ec_count"],
                "refinery_count": row["refinery_count"],
                "other_count": row["upwell_count"]
                - row["ec_count"]
                - row["refinery_count"]
                - row["citadel_count"],
                "poco_count": row["poco_count"],
                "starbase_count": row["starbase_count"],
                "total": row["upwell_count"]
                + row["poco_count"]
                + row["starbase_count"],
            }
        )
    return JsonResponse(data, safe=False)
