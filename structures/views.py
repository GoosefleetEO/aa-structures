import re
import urllib
from enum import IntEnum

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseServerError, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.html import format_html
from django.utils.translation import gettext as _
from esi.decorators import token_required
from eveuniverse.core import eveimageserver
from eveuniverse.models import EveTypeDogmaAttribute

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.evelinks import dotlan
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger
from app_utils.allianceauth import notify_admins
from app_utils.logging import LoggerAddTag
from app_utils.messages import messages_plus
from app_utils.views import bootstrap_label_html, image_html, link_html

from . import __title__, constants, tasks
from .app_settings import (
    STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED,
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_DEFAULT_PAGE_LENGTH,
    STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED,
    STRUCTURES_PAGING_ENABLED,
    STRUCTURES_SHOW_JUMP_GATES,
)
from .constants import STRUCTURE_LIST_ICON_OUTPUT_SIZE, STRUCTURE_LIST_ICON_RENDER_SIZE
from .core.serializers import JumpGatesListSerializer, StructureListSerializer
from .forms import TagsFilterForm
from .models import Owner, Structure, StructureItem, StructureTag, Webhook

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

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
                    active_tags.append(get_object_or_404(StructureTag, name=name))

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
        "show_jump_gates_tab": STRUCTURES_SHOW_JUMP_GATES,
        "last_updated": Owner.objects.structures_last_updated(),
    }
    return render(request, "structures/main.html", context)


@login_required
@permission_required("structures.basic_access")
def structure_list_data(request) -> JsonResponse:
    """returns structure list in JSON for AJAX call in structure_list view"""
    tags_raw = request.GET.get(QUERY_PARAM_TAGS)
    tags = tags_raw.split(",") if tags_raw else None
    structures = Structure.objects.visible_for_user(request.user, tags)
    serializer = StructureListSerializer(queryset=structures, request=request)
    return JsonResponse({"data": serializer.to_list()})


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

    structure = get_object_or_404(
        Structure.objects.select_related("owner", "eve_type", "eve_solar_system"),
        id=structure_id,
    )
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
    assets = structure.items.select_related("eve_type")
    high_slots = extract_slot_assets(assets, "HiSlot")
    med_slots = extract_slot_assets(assets, "MedSlot")
    low_slots = extract_slot_assets(assets, "LoSlot")
    rig_slots = extract_slot_assets(assets, "RigSlot")
    service_slots = extract_slot_assets(assets, "ServiceSlot")
    fighter_tubes = extract_slot_assets(assets, "FighterTube")
    assets_grouped = {"ammo_hold": [], "fighter_bay": [], "fuel_bay": []}
    for asset in assets:
        if asset.location_flag == StructureItem.LocationFlag.CARGO:
            assets_grouped["ammo_hold"].append(asset)
        elif asset.location_flag == StructureItem.LocationFlag.FIGHTER_BAY:
            assets_grouped["fighter_bay"].append(asset)
        elif asset.location_flag == StructureItem.LocationFlag.STRUCTURE_FUEL:
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

    poco = get_object_or_404(
        Structure.objects.select_related(
            "owner", "eve_type", "eve_solar_system", "poco_details"
        ).filter(eve_type=constants.EVE_TYPE_ID_POCO, poco_details__isnull=False),
        id=structure_id,
    )
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
    """List of public POCOs for DataTables."""
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
    return JsonResponse({"data": data})


@login_required
@permission_required("structures.basic_access")
def structure_summary_data(request) -> JsonResponse:
    summary_qs = (
        Structure.objects.values(
            "owner__corporation__corporation_id",
            "owner__corporation__corporation_name",
            "owner__corporation__alliance__alliance_name",
        )
        .annotate(
            ec_count=Count(
                "id",
                filter=Q(eve_type__eve_group=constants.EVE_GROUP_ID_ENGINERING_COMPLEX),
            )
        )
        .annotate(
            refinery_count=Count(
                "id",
                filter=Q(eve_type__eve_group=constants.EVE_GROUP_ID_REFINERY),
            )
        )
        .annotate(
            citadel_count=Count(
                "id",
                filter=Q(eve_type__eve_group=constants.EVE_GROUP_ID_CITADEL),
            )
        )
        .annotate(
            upwell_count=Count(
                "id",
                filter=Q(
                    eve_type__eve_group__eve_category=constants.EVE_CATEGORY_ID_STRUCTURE
                ),
            )
        )
        .annotate(poco_count=Count("id", filter=Q(eve_type=constants.EVE_TYPE_ID_POCO)))
        .annotate(
            starbase_count=Count(
                "id",
                filter=Q(
                    eve_type__eve_group__eve_category=constants.EVE_CATEGORY_ID_STARBASE
                ),
            )
        )
    )
    data = list()
    for row in summary_qs:
        other_count = (
            row["upwell_count"]
            - row["ec_count"]
            - row["refinery_count"]
            - row["citadel_count"]
        )
        total = row["upwell_count"] + row["poco_count"] + row["starbase_count"]
        corporation_icon = image_html(
            eveimageserver.corporation_logo_url(
                row["owner__corporation__corporation_id"], size=32
            )
        )
        alliance_name = default_if_none(
            row["owner__corporation__alliance__alliance_name"], ""
        )
        data.append(
            {
                "id": int(row["owner__corporation__corporation_id"]),
                "corporation_icon": corporation_icon,
                "corporation_name": row["owner__corporation__corporation_name"],
                "alliance_name": alliance_name,
                "citadel_count": row["citadel_count"],
                "ec_count": row["ec_count"],
                "refinery_count": row["refinery_count"],
                "other_count": other_count,
                "poco_count": row["poco_count"],
                "starbase_count": row["starbase_count"],
                "total": total,
            }
        )
    return JsonResponse({"data": data})


def jump_gates_list_data(request) -> JsonResponse:
    """List of jump gates for DataTables."""
    jump_gates = Structure.objects.visible_for_user(request.user).filter(
        eve_type_id=constants.EVE_TYPE_ID_JUMP_GATE
    )
    serializer = JumpGatesListSerializer(queryset=jump_gates)
    return JsonResponse({"data": serializer.to_list()})
