import re
from abc import ABC, abstractmethod

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext as _

from allianceauth.eveonline.evelinks import dotlan
from app_utils.datetime import DATETIME_FORMAT, timeuntil_str
from app_utils.views import (
    BootstrapStyle,
    bootstrap_label_html,
    format_html_lazy,
    link_html,
    no_wrap_html,
    yesno_str,
    yesnonone_str,
)

from ..app_settings import STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE
from ..constants import EveTypeId
from ..models import Structure, StructureItem, StructureService


class _AbstractStructureListSerializer(ABC):
    """Converting a list of structure objects into a dict for JSON."""

    ICON_RENDER_SIZE = 64
    ICON_OUTPUT_SIZE = 32

    def __init__(self, queryset: models.QuerySet, request=None):
        self.queryset = queryset
        self._request = request

    def has_data(self) -> bool:
        return self.queryset.exists()

    def count(self) -> bool:
        return self.queryset.count()

    def to_list(self) -> list:
        """Serialize all objects into a list."""
        return [self.serialize_object(obj) for obj in self.queryset]

    @abstractmethod
    def serialize_object(self, structure: Structure) -> dict:
        """Serialize one objects into a dict."""
        return {"id": structure.id}

    def _add_owner(self, structure, row):
        corporation = structure.owner.corporation
        alliance_name = (
            corporation.alliance.alliance_name if corporation.alliance else ""
        )
        row["owner"] = format_html(
            '<a href="{}">{}</a><br>{}',
            dotlan.corporation_url(corporation.corporation_name),
            corporation.corporation_name,
            alliance_name,
        )
        if not structure.owner.is_structure_sync_fresh:
            update_warning_html = format_html(
                '<i class="fas fa-exclamation-circle text-warning" '
                'title="Data has not been updated for a while and may be outdated."></i>'
            )
        else:
            update_warning_html = ""
        row["corporation_icon"] = format_html(
            '<span class="nowrap">{} <img src="{}" width="{}" height="{}"/></span>',
            update_warning_html,
            corporation.logo_url(size=self.ICON_RENDER_SIZE),
            self.ICON_OUTPUT_SIZE,
            self.ICON_OUTPUT_SIZE,
        )
        row["alliance_name"] = alliance_name
        row["corporation_name"] = corporation.corporation_name

    def _add_location(self, structure, row):
        solar_system = structure.eve_solar_system

        # location
        row["region_name"] = solar_system.eve_constellation.eve_region.name_localized
        row["solar_system_name"] = solar_system.name_localized
        solar_system_url = dotlan.solar_system_url(solar_system.name)
        if structure.eve_moon:
            location_name = structure.eve_moon.name_localized
        elif structure.eve_planet:
            location_name = structure.eve_planet.name_localized
        else:
            location_name = row["solar_system_name"]
        row["location"] = format_html(
            '<a href="{}">{}</a><br><em>{}</em>',
            solar_system_url,
            no_wrap_html(location_name),
            no_wrap_html(row["region_name"]),
        )

    def _add_type(self, structure, row):
        structure_type = structure.eve_type
        # category
        my_group = structure_type.eve_group
        row["group_name"] = my_group.name_localized
        try:
            my_category = my_group.eve_category
            row["category_name"] = my_category.name_localized
            row["is_starbase"] = structure.is_starbase
        except AttributeError:
            row["category_name"] = ""
            row["is_starbase"] = None
        # type icon
        row["type_icon"] = format_html(
            '<img src="{}" width="{}" height="{}"/>',
            structure_type.icon_url(size=self.ICON_RENDER_SIZE),
            self.ICON_OUTPUT_SIZE,
            self.ICON_OUTPUT_SIZE,
        )
        # type name
        row["type_name"] = structure_type.name_localized
        row["type"] = format_html(
            "{}<br><em>{}</em>",
            no_wrap_html(link_html(structure_type.profile_url, row["type_name"])),
            no_wrap_html(row["group_name"]),
        )
        # poco
        row["is_poco"] = structure.is_poco

    def _add_name(self, structure, row, check_tags=True):
        row["structure_name"] = escape(structure.name)
        tags = []
        if check_tags and structure.tags.exists():
            tags += [x.html for x in structure.tags.all()]
            row["structure_name"] += format_html("<br>{}", mark_safe(" ".join(tags)))

    def _add_services(self, structure, row):
        if row["is_poco"] or row["is_starbase"]:
            row["services"] = "-"
            return
        services = list()
        for service in structure.services.all():
            service_name_html = no_wrap_html(
                format_html("<small>{}</small>", service.name_localized)
            )
            if service.state == StructureService.State.OFFLINE:
                service_name_html = format_html("<del>{}</del>", service_name_html)
            services.append({"name": service.name, "html": service_name_html})
        row["services"] = (
            "<br>".join(
                map(lambda x: x["html"], sorted(services, key=lambda x: x["name"]))
            )
            if services
            else "-"
        )

    def _add_reinforcement_infos(self, structure, row):
        row["is_reinforced"] = structure.is_reinforced
        row["is_reinforced_str"] = yesno_str(structure.is_reinforced)
        if structure.is_starbase:
            row["reinforcement"] = "-"
        else:
            if structure.reinforce_hour is not None:
                row["reinforcement"] = "{:02d}:00".format(structure.reinforce_hour)
            else:
                row["reinforcement"] = ""

    def _add_fuel_infos(self, structure, row):
        if structure.is_poco:
            fuel_expires_display = "-"
            fuel_expires_timestamp = None
        elif structure.is_low_power:
            fuel_expires_display = format_html_lazy(
                bootstrap_label_html(
                    structure.get_power_mode_display(), BootstrapStyle.WARNING
                )
            )
            fuel_expires_timestamp = None
        elif structure.is_abandoned:
            fuel_expires_display = format_html_lazy(
                bootstrap_label_html(
                    structure.get_power_mode_display(), BootstrapStyle.DANGER
                )
            )
            fuel_expires_timestamp = None
        elif structure.is_maybe_abandoned:
            fuel_expires_display = format_html_lazy(
                bootstrap_label_html(
                    structure.get_power_mode_display(), BootstrapStyle.WARNING
                )
            )
            fuel_expires_timestamp = None
        elif structure.fuel_expires_at:
            fuel_expires_timestamp = structure.fuel_expires_at.isoformat()
            if STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE:
                fuel_expires_display = timeuntil_str(
                    structure.fuel_expires_at - now(), show_seconds=False
                )
                if not fuel_expires_display:
                    fuel_expires_display = "?"
                    fuel_expires_timestamp = None
            else:
                if structure.fuel_expires_at >= now():
                    fuel_expires_display = structure.fuel_expires_at.strftime(
                        DATETIME_FORMAT
                    )
                else:
                    fuel_expires_display = "?"
                    fuel_expires_timestamp = None
        else:
            fuel_expires_display = "-"
            fuel_expires_timestamp = None
        row["fuel_expires_at"] = {
            "display": no_wrap_html(fuel_expires_display),
            "timestamp": fuel_expires_timestamp,
        }

    def _add_online_infos(self, structure, row):
        row["power_mode_str"] = structure.get_power_mode_display()
        if structure.is_poco:
            last_online_at_display = "-"
            last_online_at_timestamp = None
        elif structure.is_full_power:
            last_online_at_display = format_html_lazy(
                bootstrap_label_html(
                    structure.get_power_mode_display(), BootstrapStyle.SUCCESS
                )
            )
            last_online_at_timestamp = None
        elif structure.is_maybe_abandoned:
            last_online_at_display = format_html_lazy(
                bootstrap_label_html(
                    structure.get_power_mode_display(), BootstrapStyle.WARNING
                )
            )
            last_online_at_timestamp = None
        elif structure.is_abandoned:
            last_online_at_display = format_html_lazy(
                bootstrap_label_html(
                    structure.get_power_mode_display(), BootstrapStyle.DANGER
                )
            )
            last_online_at_timestamp = None
        elif structure.last_online_at:
            last_online_at_timestamp = structure.last_online_at.isoformat()
            if STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE:
                last_online_at_display = timeuntil_str(
                    now() - structure.last_online_at, show_seconds=False
                )
                if not last_online_at_display:
                    last_online_at_display = "?"
                    last_online_at_timestamp = None
                else:
                    last_online_at_display = "- " + last_online_at_display
            else:
                last_online_at_display = structure.last_online_at.strftime(
                    DATETIME_FORMAT
                )
        else:
            last_online_at_display = "-"
            last_online_at_timestamp = None
        row["last_online_at"] = {
            "display": no_wrap_html(last_online_at_display),
            "timestamp": last_online_at_timestamp,
        }

    def _add_state(self, structure, row, request):
        def cap_first(s: str) -> str:
            return s[0].upper() + s[1::]

        row["state_str"] = (
            cap_first(structure.get_state_display()) if not structure.is_poco else "-"
        )
        row["state_details"] = row["state_str"]
        if structure.state_timer_end:
            row["state_details"] += format_html(
                "<br>{}",
                no_wrap_html(structure.state_timer_end.strftime(DATETIME_FORMAT)),
            )
        if (
            request.user.has_perm("structures.view_all_unanchoring_status")
            and structure.unanchors_at
        ):
            row["state_details"] += format_html(
                "<br>Unanchoring until {}",
                no_wrap_html(structure.unanchors_at.strftime(DATETIME_FORMAT)),
            )

    def _add_core_status(self, structure, row):
        if structure.is_upwell_structure:
            if structure.has_core is True:
                has_core = True
                core_status = '<i class="fas fa-check" title="Core present"></i>'
            elif structure.has_core is False:
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
        row["core_status"] = core_status
        row["core_status_str"] = yesnonone_str(has_core)

    def _add_details_widget(self, structure, row, request):
        """Add details widget when applicable"""
        if structure.has_fitting and request.user.has_perm(
            "structures.view_structure_fit"
        ):
            ajax_url = reverse("structures:structure_details", args=[structure.id])
            row["details"] = format_html(
                '<button type="button" class="btn btn-default" '
                'data-toggle="modal" data-target="#modalUpwellDetails" '
                f"data-ajax_url={ajax_url} "
                f'title="{_("Show fitting")}">'
                '<i class="fas fa-search"></i></button>'
            )
        elif structure.has_poco_details:
            ajax_url = reverse(
                "structures:poco_details",
                args=[structure.id],
            )
            row["details"] = format_html(
                '<button type="button" class="btn btn-default" '
                'data-toggle="modal" data-target="#modalPocoDetails" '
                f"data-ajax_url={ajax_url} "
                f'title="{_("Show details")}">'
                '<i class="fas fa-search"></i></button>'
            )
        else:
            row["details"] = ""


class StructureListSerializer(_AbstractStructureListSerializer):
    def __init__(self, queryset: models.QuerySet, request=None):
        super().__init__(queryset, request=request)
        self.queryset = self.queryset.prefetch_related(
            "tags", "services"
        ).annotate_has_poco_details()

    def serialize_object(self, structure: Structure) -> dict:
        row = super().serialize_object(structure)
        self._add_owner(structure, row)
        self._add_location(structure, row)
        self._add_type(structure, row)
        self._add_name(structure, row)
        self._add_services(structure, row)
        self._add_reinforcement_infos(structure, row)
        self._add_fuel_infos(structure, row)
        self._add_online_infos(structure, row)
        self._add_state(structure, row, self._request)
        self._add_core_status(structure, row)
        self._add_details_widget(structure, row, self._request)
        return row


class JumpGatesListSerializer(_AbstractStructureListSerializer):
    def __init__(self, queryset: models.QuerySet, request=None):
        super().__init__(queryset, request=request)
        self.queryset = self.queryset.annotate(
            jump_fuel_quantity_2=Sum(
                "items__quantity",
                filter=Q(
                    items__eve_type=EveTypeId.LIQUID_OZONE,
                    items__location_flag=StructureItem.LocationFlag.STRUCTURE_FUEL,
                ),
            )
        )

    def serialize_object(self, structure: Structure) -> dict:
        row = super().serialize_object(structure)
        self._add_owner(structure, row)
        self._add_location(structure, row)
        self._add_name(structure, row, check_tags=False)
        self._add_jump_fuel_level(structure, row)
        self._add_fuel_infos(structure, row)
        self._add_reinforcement_infos(structure, row)
        self._add_online_infos(structure, row)
        return row

    def _add_jump_fuel_level(self, structure, row):
        row["jump_fuel_quantity"] = structure.jump_fuel_quantity_2


class PocoListSerializer(_AbstractStructureListSerializer):
    def __init__(self, queryset: models.QuerySet, request=None):
        super().__init__(queryset, request=request)
        self.queryset = self.queryset.select_related(
            "eve_planet",
            "eve_planet__eve_type",
            "eve_type",
            "eve_type__eve_group",
            "eve_solar_system",
            "eve_solar_system__eve_constellation__eve_region",
            "poco_details",
            "owner__corporation",
        )
        if not request:
            raise ValueError("request can not be None")
        try:
            self.main_character = request.user.profile.main_character
        except (AttributeError, ObjectDoesNotExist):
            self.main_character = None

    def serialize_object(self, structure: Structure) -> dict:
        row = super().serialize_object(structure)
        self._add_type(structure, row)
        self._add_solar_system(structure, row)
        self._add_planet(structure, row)
        self._add_has_access_and_tax(structure, row, self.main_character)
        return row

    def _add_type(self, structure, row):
        row["type_icon"] = format_html(
            '<img src="{}" width="{}" height="{}"/>',
            structure.eve_type.icon_url(size=self.ICON_RENDER_SIZE),
            self.ICON_OUTPUT_SIZE,
            self.ICON_OUTPUT_SIZE,
        )

    def _add_solar_system(self, structure, row):
        if structure.eve_solar_system.is_low_sec:
            space_badge_type = "warning"
        elif structure.eve_solar_system.is_high_sec:
            space_badge_type = "success"
        else:
            space_badge_type = "danger"
        solar_system_html = format_html(
            "{}<br>{}",
            link_html(
                dotlan.solar_system_url(structure.eve_solar_system.name),
                structure.eve_solar_system.name,
            ),
            bootstrap_label_html(
                text=structure.eve_solar_system.space_type, label=space_badge_type
            ),
        )
        row["solar_system_html"] = {
            "display": solar_system_html,
            "sort": structure.eve_solar_system.name,
        }
        row["solar_system"] = structure.eve_solar_system.name
        row["region"] = structure.eve_solar_system.eve_constellation.eve_region.name
        row["space_type"] = structure.eve_solar_system.space_type

    def _add_planet(self, structure, row):
        try:
            match = re.search(r"Planet \((\S+)\)", structure.eve_planet.eve_type.name)
        except AttributeError:
            planet_name = planet_type_name = "?"
            planet_type_icon = ""
        else:
            if match:
                planet_type_name = match.group(1)
            else:
                planet_type_name = ""
            planet_name = structure.eve_planet.name
            planet_type_icon = format_html(
                '<img src="{}" width="{}" height="{}"/>',
                structure.eve_planet.eve_type.icon_url(size=self.ICON_RENDER_SIZE),
                self.ICON_OUTPUT_SIZE,
                self.ICON_OUTPUT_SIZE,
            )
        row["planet"] = planet_name
        row["planet_type_icon"] = planet_type_icon
        row["planet_type_name"] = planet_type_name

    def _add_has_access_and_tax(self, structure, row, main_character):
        tax = None
        has_access = None
        if main_character:
            try:
                details = structure.poco_details
            except (AttributeError, ObjectDoesNotExist):
                pass
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
        row["has_access_html"] = has_access_html
        row["has_access_str"] = has_access_str
        row["tax"] = f"{tax * 100:.0f} %" if tax else "?"
