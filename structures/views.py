"""Views for Structures."""

import functools
from collections import defaultdict
from enum import IntEnum
from typing import Dict
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseServerError, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from esi.decorators import token_required
from eveuniverse.core import eveimageserver
from eveuniverse.models import EveType, EveTypeDogmaAttribute

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger
from app_utils.allianceauth import notify_admins
from app_utils.logging import LoggerAddTag
from app_utils.views import image_html

from . import __title__, tasks
from .app_settings import (
    STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED,
    STRUCTURES_DEFAULT_LANGUAGE,
    STRUCTURES_DEFAULT_PAGE_LENGTH,
    STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED,
    STRUCTURES_PAGING_ENABLED,
    STRUCTURES_SHOW_JUMP_GATES,
)
from .constants import EveAttributeId, EveCategoryId, EveGroupId, EveTypeId
from .core.serializers import (
    JumpGatesListSerializer,
    PocoListSerializer,
    StructureListSerializer,
)
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
    """Redirect from index view to main."""
    url = reverse("structures:main")
    if STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED:
        params = {
            QUERY_PARAM_TAGS: ",".join(
                [x.name for x in StructureTag.objects.filter(is_default=True)]
            )
        }
        params_encoded = urlencode(params)
        url += f"?{params_encoded}"
    return redirect(url)


@login_required
@permission_required("structures.basic_access")
def main(request):
    """Main view"""
    active_tags = []
    if request.method == "POST":
        form = TagsFilterForm(data=request.POST)
        if form.is_valid():
            for name, activated in form.cleaned_data.items():
                if activated:
                    active_tags.append(get_object_or_404(StructureTag, name=name))

            url = reverse("structures:main")
            if active_tags:
                params = {QUERY_PARAM_TAGS: ",".join([x.name for x in active_tags])}
                params_encoded = urlencode(params)
                url += f"?{params_encoded}"
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
    """Return structure list in JSON for AJAX call in structure_list view."""
    tags_raw = request.GET.get(QUERY_PARAM_TAGS)
    tags = tags_raw.split(",") if tags_raw else None
    structures = Structure.objects.visible_for_user(request.user, tags)
    serializer = StructureListSerializer(queryset=structures, request=request)
    return JsonResponse({"data": serializer.to_list()})


class FakeEveType:
    """A faked eve type."""

    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.profile_url = ""

    def icon_url(self, size=64) -> str:
        """Return icon url for an EveType."""
        return eveimageserver.type_icon_url(self.id, size)


class FakeAsset:
    """Fake asset object for showing additional information in the asset list."""

    def __init__(self, name, quantity, eve_type_id):
        self.name = name
        self.quantity = quantity
        self.eve_type_id = eve_type_id
        self.eve_type = FakeEveType(eve_type_id, name)
        self.is_singleton = False


class Slot(IntEnum):
    """A slot type in a fitting."""

    HIGH = 14
    MEDIUM = 13
    LOW = 12
    RIG = 1137
    SERVICE = 2056

    def image_url(self, type_attributes: dict) -> str:
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
            my_id = id_map[Slot(self.value)]
            return staticfiles_storage.url(
                f"structures/img/panel/{slot_num}{my_id}.png"
            )
        except KeyError:
            return ""


@login_required
@permission_required("structures.view_structure_fit")
def structure_details(request, structure_id):
    """Main view of the structure fit"""

    structure = get_object_or_404(
        Structure.objects.select_related(
            "owner",
            "owner__corporation",
            "owner__corporation__alliance",
            "eve_type",
            "eve_type__eve_group",
            "eve_solar_system",
            "eve_solar_system__eve_constellation",
            "eve_solar_system__eve_constellation__eve_region",
        ),
        id=structure_id,
    )
    assets = structure.items.select_related("eve_type")
    high_slots = _extract_slot_assets(assets, "HiSlot")
    med_slots = _extract_slot_assets(assets, "MedSlot")
    low_slots = _extract_slot_assets(assets, "LoSlot")
    rig_slots = _extract_slot_assets(assets, "RigSlot")
    service_slots = _extract_slot_assets(assets, "ServiceSlot")
    fighter_tubes = _extract_slot_assets(assets, "FighterTube")
    _patch_fighter_tube_quantities(fighter_tubes)

    assets_grouped = _init_assets_grouped(assets)

    if structure.is_upwell_structure:
        assets_grouped["fuel_usage"] = [
            FakeAsset(
                name=_("Fuel blocks per day (est.)"),
                quantity=structure.structure_fuel_usage(),
                eve_type_id=24756,
            )
        ]

    fuel_blocks_total = (
        functools.reduce(
            lambda x, y: x + y, [obj.quantity for obj in assets_grouped["fuel_bay"]]
        )
        if assets_grouped["fuel_bay"]
        else 0
    )
    ammo_total = (
        functools.reduce(
            lambda x, y: x + y, [obj.quantity for obj in assets_grouped["ammo_hold"]]
        )
        if assets_grouped["ammo_hold"]
        else 0
    )
    context = {
        "fitting": assets,
        "slots": _generate_slot_image_urls(structure),
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
        "modules_count": len(
            high_slots + med_slots + low_slots + rig_slots + service_slots
        ),
        "fuel_blocks_total": fuel_blocks_total,
        "fighters_total": _calc_fighters_total(fighter_tubes, assets_grouped),
        "ammo_total": ammo_total,
        "last_updated": structure.owner.assets_last_update_at,
    }
    return render(request, "structures/modals/structure_details.html", context)


def _init_assets_grouped(assets):
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
    return assets_grouped


def _calc_fighters_total(fighter_tubes, assets_grouped):
    fighters_consolidated = assets_grouped["fighter_bay"] + fighter_tubes
    fighters_total = (
        functools.reduce(
            lambda x, y: x + y, [obj.quantity for obj in fighters_consolidated]
        )
        if fighters_consolidated
        else 0
    )

    return fighters_total


def _generate_slot_image_urls(structure):
    type_attributes = {
        obj["eve_dogma_attribute_id"]: int(obj["value"])
        for obj in EveTypeDogmaAttribute.objects.filter(
            eve_type_id=structure.eve_type_id
        ).values("eve_dogma_attribute_id", "value")
    }
    slot_image_urls = {
        "high": Slot.HIGH.image_url(type_attributes),
        "med": Slot.MEDIUM.image_url(type_attributes),
        "low": Slot.LOW.image_url(type_attributes),
        "rig": Slot.RIG.image_url(type_attributes),
        "service": Slot.SERVICE.image_url(type_attributes),
    }

    return slot_image_urls


def _extract_slot_assets(fittings: list, slot_name: str) -> list:
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


def _patch_fighter_tube_quantities(fighter_tubes):
    eve_type_ids = {item.eve_type_id for item in fighter_tubes}
    eve_types = [
        EveType.objects.get_or_create_esi(
            id=eve_type_id, enabled_sections=[EveType.Section.DOGMAS]
        )[0]
        for eve_type_id in eve_type_ids
    ]
    squadron_sizes = {
        eve_type.id: int(
            eve_type.dogma_attributes.get(
                eve_dogma_attribute=EveAttributeId.SQUADRON_SIZE.value
            ).value
        )
        for eve_type in eve_types
    }
    for item in fighter_tubes:
        try:
            squadron_size = squadron_sizes[item.eve_type_id]
        except KeyError:
            pass
        else:
            item.quantity = squadron_size
            item.is_singleton = False


@login_required
@permission_required("structures.basic_access")
def poco_details(request, structure_id):
    """Shows details modal for a POCO."""

    structure = get_object_or_404(
        Structure.objects.select_related(
            "owner",
            "eve_type",
            "eve_solar_system",
            "eve_solar_system__eve_constellation",
            "eve_solar_system__eve_constellation__eve_region",
            "poco_details",
            "eve_planet",
        ).filter(eve_type=EveTypeId.CUSTOMS_OFFICE, poco_details__isnull=False),
        id=structure_id,
    )
    context = {
        "structure": structure,
        "details": structure.poco_details,
        "last_updated": structure.last_updated_at,
    }
    return render(request, "structures/modals/poco_details.html", context)


@login_required
@permission_required("structures.basic_access")
def starbase_detail(request, structure_id):
    """Shows detail modal for a starbase."""

    structure = get_object_or_404(
        Structure.objects.select_related(
            "owner",
            "owner__corporation",
            "owner__corporation__alliance",
            "eve_type",
            "eve_type__eve_group",
            "eve_solar_system",
            "eve_solar_system__eve_constellation",
            "eve_solar_system__eve_constellation__eve_region",
            "starbase_detail",
            "eve_moon",
        ).filter(starbase_detail__isnull=False),
        id=structure_id,
    )
    fuels = structure.starbase_detail.fuels.select_related("eve_type").order_by(
        "eve_type__name"
    )
    assets = defaultdict(int)
    for item in structure.items.select_related("eve_type"):
        assets[item.eve_type_id] += item.quantity
    eve_types: Dict[int, EveType] = EveType.objects.in_bulk(id_list=assets.keys())
    modules = sorted(
        [
            {"eve_type": eve_types.get(eve_type_id), "quantity": quantity}
            for eve_type_id, quantity in assets.items()
        ],
        key=lambda obj: obj["eve_type"].name,
    )
    modules_count = (
        functools.reduce(lambda x, y: x + y, [obj["quantity"] for obj in modules])
        if modules
        else 0
    )
    try:
        fuel_blocks_count = (
            structure.starbase_detail.fuels.filter(
                eve_type__eve_group_id=EveGroupId.FUEL_BLOCK
            )
            .first()
            .quantity
        )
    except AttributeError:
        fuel_blocks_count = None
    context = {
        "structure": structure,
        "detail": structure.starbase_detail,
        "fuels": fuels,
        "modules": modules,
        "modules_count": modules_count,
        "fuel_blocks_count": fuel_blocks_count,
        "last_updated_at": structure.last_updated_at,
    }
    return render(request, "structures/modals/starbase_detail.html", context)


@login_required
@permission_required("structures.add_structure_owner")
@token_required(scopes=Owner.get_esi_scopes())  # type: ignore
def add_structure_owner(request, token):
    """View for adding or replacing a structure owner."""
    token_char = get_object_or_404(EveCharacter, character_id=token.character_id)
    try:
        character_ownership = CharacterOwnership.objects.get(
            user=request.user, character=token_char
        )
    except CharacterOwnership.DoesNotExist:
        character_ownership = None
        messages.error(
            request,
            format_html(
                _(
                    "You can only use your main or alt characters "
                    "to add corporations. "
                    "However, character %s is neither. "
                )
                % token_char.character_name
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
        tasks.update_all_for_owner.delay(owner_pk=owner.pk, user_pk=request.user.pk)  # type: ignore
        messages.info(
            request,
            format_html(
                _(
                    "%(corporation)s has been added with %(character)s "
                    "as sync character. "
                    "We have started fetching structures and notifications "
                    "for this corporation and you will receive a report once "
                    "the process is finished."
                )
                % {"corporation": owner, "character": token_char}
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
        messages.info(
            request,
            format_html(
                _(
                    "%(character)s has been added to %(corporation)s "
                    "as sync character. "
                    "You now have %(characters_count)d sync character(s) configured."
                )
                % {
                    "corporation": owner,
                    "character": token_char,
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
    return HttpResponseServerError(_("service is down"))


def poco_list_data(request) -> JsonResponse:
    """List of public POCOs for DataTables."""
    pocos = Structure.objects.filter(
        eve_type__eve_group__eve_category_id=EveCategoryId.ORBITAL,
        owner__are_pocos_public=True,
    )
    serializer = PocoListSerializer(queryset=pocos, request=request)
    return JsonResponse({"data": serializer.to_list()})


@login_required
@permission_required("structures.basic_access")
def structure_summary_data(request) -> JsonResponse:
    """View returning data for structure summary page."""
    summary_qs = (
        Structure.objects.values(
            "owner__corporation__corporation_id",
            "owner__corporation__corporation_name",
            "owner__corporation__alliance__alliance_name",
        )
        .annotate(
            ec_count=Count(
                "id", filter=Q(eve_type__eve_group=EveGroupId.ENGINEERING_COMPLEX)
            )
        )
        .annotate(
            refinery_count=Count(
                "id", filter=Q(eve_type__eve_group=EveGroupId.REFINERY)
            )
        )
        .annotate(
            citadel_count=Count("id", filter=Q(eve_type__eve_group=EveGroupId.CITADEL))
        )
        .annotate(
            upwell_count=Count(
                "id",
                filter=Q(eve_type__eve_group__eve_category=EveCategoryId.STRUCTURE),
            )
        )
        .annotate(poco_count=Count("id", filter=Q(eve_type=EveTypeId.CUSTOMS_OFFICE)))
        .annotate(
            starbase_count=Count(
                "id", filter=Q(eve_type__eve_group__eve_category=EveCategoryId.STARBASE)
            )
        )
    )
    data = []
    for row in summary_qs:
        other_count = (
            row["upwell_count"]
            - row["ec_count"]
            - row["refinery_count"]
            - row["citadel_count"]
        )
        total = row["upwell_count"] + row["poco_count"] + row["starbase_count"]
        corporation_icon_url = eveimageserver.corporation_logo_url(
            row["owner__corporation__corporation_id"], size=64
        )
        corporation_icon = image_html(corporation_icon_url, size=32)
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
        eve_type_id=EveTypeId.JUMP_GATE
    )
    serializer = JumpGatesListSerializer(queryset=jump_gates)
    return JsonResponse({"data": serializer.to_list()})
