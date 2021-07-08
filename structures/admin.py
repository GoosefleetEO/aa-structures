import statistics

from django.contrib import admin
from django.db import models
from django.db.models import Count
from django.db.models.functions import Lower
from django.utils.html import format_html

from allianceauth.eveonline.models import EveAllianceInfo, EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger
from app_utils.django import admin_boolean_icon_html
from app_utils.logging import LoggerAddTag

from . import __title__, app_settings, tasks
from .models import (
    Notification,
    Owner,
    OwnerCharacter,
    Structure,
    StructureService,
    StructureTag,
    Webhook,
)

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class RenderableNotificationFilter(admin.SimpleListFilter):
    title = "can be send"

    parameter_name = "notification_renderable"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        """Return the filtered queryset"""
        if self.value() == "yes":
            return queryset.annotate_can_be_rendered().filter(can_be_rendered_2=True)
        elif self.value() == "no":
            return queryset.annotate_can_be_rendered().filter(can_be_rendered_2=False)
        else:
            return queryset


class OwnerFilter(admin.SimpleListFilter):
    title = "owner"
    parameter_name = "owner_filter"

    def lookups(self, request, model_admin):
        return (
            Notification.objects.values_list(
                "owner__pk", "owner__corporation__corporation_name"
            )
            .distinct()
            .order_by("owner__corporation__corporation_name")
        )

    def queryset(self, request, queryset):
        """Return the filtered queryset"""
        value = self.value()
        if value:
            return queryset.filter(owner__pk=self.value())
        else:
            return queryset


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "notification_id",
        "owner",
        "notif_type",
        "timestamp",
        "created",
        "last_updated",
        "_webhooks",
        "_is_sent",
        "_is_timer_added",
    )
    ordering = ["-timestamp", "-notification_id"]
    list_filter = (
        OwnerFilter,
        # "owner",
        RenderableNotificationFilter,
        "is_sent",
        "notif_type",
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("owner__webhooks").select_related(
            "owner", "owner__corporation", "sender"
        )

    def _webhooks(self, obj):
        if not obj.can_be_rendered:
            return format_html("<i>N/A</i>")
        names = sorted(
            [
                webhook.name
                for webhook in obj.owner.webhooks.all()
                if obj.notif_type in webhook.notification_types
            ]
        )
        if names:
            return ", ".join(names)
        else:
            return format_html(
                '<b><span style="color: orange">Not configured</span></b>'
            )

    def _is_sent(self, obj):
        value = obj.is_sent if obj.can_be_rendered else None
        return admin_boolean_icon_html(value)

    def _is_timer_added(self, obj):
        value = obj.is_timer_added if obj.can_have_timer else None
        return admin_boolean_icon_html(value)

    actions = (
        "mark_as_sent",
        "mark_as_unsent",
        "send_to_webhooks",
        "process_for_timerboard",
    )

    def mark_as_sent(self, request, queryset):
        notifications_count = 0
        for obj in queryset:
            obj.is_sent = True
            obj.save()
            notifications_count += 1

        self.message_user(
            request, "{} notifications marked as sent".format(notifications_count)
        )

    mark_as_sent.short_description = "Mark selected notifications as sent"

    def mark_as_unsent(self, request, queryset):
        notifications_count = 0
        for obj in queryset:
            obj.is_sent = False
            obj.save()
            notifications_count += 1

        self.message_user(
            request, "{} notifications marked as unsent".format(notifications_count)
        )

    mark_as_unsent.short_description = "Mark selected notifications as unsent"

    def send_to_webhooks(self, request, queryset):
        obj_pks = [obj.pk for obj in queryset if obj.can_be_rendered]
        ignored_count = len([obj for obj in queryset if not obj.can_be_rendered])
        tasks.send_notifications.delay(obj_pks)
        message = (
            f"Initiated sending of {len(obj_pks)} notification(s) to "
            f"configured webhooks."
        )
        if ignored_count:
            message += (
                f" Ignored {ignored_count} notification(s), which can not be rendered."
            )
        self.message_user(request, message)

    send_to_webhooks.short_description = (
        "Send selected notifications to configured webhooks"
    )

    def process_for_timerboard(self, request, queryset):
        notifications_count = 0
        ignored_count = 0
        for obj in queryset:
            if obj.process_for_timerboard():
                notifications_count += 1
            else:
                ignored_count += 1

        message = (
            f"Added timers from {notifications_count} notifications to timerboard."
        )
        if ignored_count:
            message += f" Ignored {ignored_count} notification(s), which has no relation to timers."
        self.message_user(request, message)

    process_for_timerboard.short_description = (
        "Process selected notifications for timerboard"
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class OwnerSyncStatusFilter(admin.SimpleListFilter):
    title = "is sync ok"

    parameter_name = "sync_status__exact"

    def lookups(self, request, model_admin):
        """List of values to allow admin to select"""
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        """Return the filtered queryset"""
        if self.value() == "yes":
            return queryset.filter(
                structures_last_update_ok=True,
                notifications_last_update_ok=True,
                forwarding_last_update_ok=True,
                assets_last_update_ok=True,
            )
        elif self.value() == "no":
            return queryset.exclude(
                structures_last_update_ok=True,
                notifications_last_update_ok=True,
                forwarding_last_update_ok=True,
                assets_last_update_ok=True,
            )
        else:
            return queryset


class OwnerCharacterAdminInline(admin.TabularInline):
    model = OwnerCharacter

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = (
        "_corporation",
        "_alliance",
        "_characters",
        "_is_active",
        "_webhooks",
        "_has_default_pings_enabled",
        "_ping_groups",
        "_is_alliance_main",
        "_is_sync_ok",
        "_structures_count",
        "_notifications_count",
    )
    list_filter = (
        ("corporation__alliance", admin.RelatedOnlyFieldListFilter),
        "has_default_pings_enabled",
        "is_active",
        "is_alliance_main",
        OwnerSyncStatusFilter,
    )
    ordering = ["corporation__corporation_name"]
    search_fields = ["corporation__corporation_name"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return (
            qs.select_related("corporation", "corporation__alliance")
            .prefetch_related("ping_groups", "webhooks")
            .annotate(notifications_count=Count("notifications", distinct=True))
            .annotate(structures_count=Count("structures", distinct=True))
            .annotate_characters_count()
        )

    def _characters(self, obj) -> int:
        return obj.x_characters_count

    _characters.admin_order_field = "x_characters_count"

    def _has_default_pings_enabled(self, obj):
        return obj.has_default_pings_enabled

    _has_default_pings_enabled.short_description = "default pings"
    _has_default_pings_enabled.boolean = True

    def _ping_groups(self, obj):
        return sorted([ping_group.name for ping_group in obj.ping_groups.all()])

    def _corporation(self, obj):
        return obj.corporation.corporation_name

    _corporation.admin_order_field = "corporation__corporation_name"

    def _alliance(self, obj):
        if obj.corporation.alliance:
            return obj.corporation.alliance.alliance_name
        else:
            return None

    _alliance.admin_order_field = "corporation__alliance__alliance_name"

    def _webhooks(self, obj):
        names = sorted([webhook.name for webhook in obj.webhooks.all()])
        if names:
            return names
        else:
            return format_html(
                '<span style="color: red"></i>Error: Notifications can not be sent, '
                "because there is no webhook configured for this owner."
            )

    def _is_active(self, obj):
        return obj.is_active

    _is_active.boolean = True
    _is_active.short_description = "active"

    def _is_alliance_main(self, obj):
        value = True if obj.is_alliance_main else None
        return admin_boolean_icon_html(value)

    _is_alliance_main.short_description = "alliance main"

    def _is_sync_ok(self, obj):
        if not obj.is_active:
            return None
        else:
            return obj.are_all_syncs_ok

    _is_sync_ok.boolean = True
    _is_sync_ok.short_description = "sync ok"

    def _notifications_count(self, obj: Owner) -> int:
        return obj.notifications_count

    _notifications_count.short_description = "notifications"

    def _structures_count(self, obj: Owner) -> int:
        return obj.structures_count

    _structures_count.short_description = "structures"

    actions = (
        "update_all",
        "update_structures",
        "fetch_notifications",
        "deactivate_owners",
        "activate_owners",
    )

    def activate_owners(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"Activated {queryset.count()} owners")

    activate_owners.short_description = "Activate selected owners"

    def deactivate_owners(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {queryset.count()} owners")

    deactivate_owners.short_description = "Deactivate selected owners"

    def update_all(self, request, queryset):
        for obj in queryset:
            tasks.update_all_for_owner.delay(obj.pk, user_pk=request.user.pk)
            text = (
                f"Started updating structures and notifications for {obj}. "
                "You will receive a notification once it is completed."
            )
            self.message_user(request, text)

    update_all.short_description = "Update all from EVE server"

    def update_structures(self, request, queryset):
        for obj in queryset:
            tasks.update_structures_for_owner.delay(obj.pk, user_pk=request.user.pk)
            text = (
                f"Started updating structures for {obj}. "
                "You will receive a notification once it is completed."
            )
            self.message_user(request, text)

    update_structures.short_description = "Update structures from EVE server"

    def fetch_notifications(self, request, queryset):
        for obj in queryset:
            tasks.process_notifications_for_owner.delay(obj.pk, user_pk=request.user.pk)
            text = (
                f"Started fetching notifications for {obj}. "
                "You will receive a notification once it is completed."
            )
            self.message_user(request, text)

    fetch_notifications.short_description = "Fetch notifications from EVE server"

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + (
                "assets_last_update_at",
                "assets_last_update_ok",
                "corporation",
                "forwarding_last_update_at",
                "forwarding_last_update_ok",
                "notifications_last_update_at",
                "notifications_last_update_ok",
                "structures_last_update_at",
                "structures_last_update_ok",
                "_avg_turnaround_time",
                "_are_all_syncs_ok",
                "_structures_last_update_fresh",
                "_notifications_last_update_fresh",
                "_forwarding_last_update_fresh",
                "_assets_last_update_fresh",
            )
        return self.readonly_fields

    inlines = (OwnerCharacterAdminInline,)
    filter_horizontal = ("ping_groups",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "corporation",
                    "webhooks",
                    "is_alliance_main",
                    "are_pocos_public",
                    "has_default_pings_enabled",
                    "ping_groups",
                    "is_included_in_service_status",
                    "is_active",
                )
            },
        ),
        (
            "Sync Status",
            {
                "classes": ("collapse",),
                "fields": (
                    "_are_all_syncs_ok",
                    (
                        "structures_last_update_ok",
                        "_structures_last_update_fresh",
                        "structures_last_update_at",
                    ),
                    (
                        "notifications_last_update_ok",
                        "_notifications_last_update_fresh",
                        "notifications_last_update_at",
                        "_avg_turnaround_time",
                    ),
                    (
                        "forwarding_last_update_ok",
                        "_forwarding_last_update_fresh",
                        "forwarding_last_update_at",
                    ),
                    (
                        "assets_last_update_ok",
                        "_assets_last_update_fresh",
                        "assets_last_update_at",
                    ),
                ),
            },
        ),
    )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """only show custom tags in dropdown"""
        if db_field.name == "webhooks":
            kwargs["queryset"] = Webhook.objects.filter(is_active=True)

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def _are_all_syncs_ok(self, obj):
        return obj.are_all_syncs_ok

    _are_all_syncs_ok.boolean = True
    _are_all_syncs_ok.short_description = "All syncs OK"

    def _avg_turnaround_time(self, obj) -> str:
        """Average time between timestamp of notifications an when they are received."""

        def my_format(value) -> str:
            return f"{value:,.0f}" if value else "-"

        max_short = app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_SHORT
        max_medium = app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_MEDIUM
        max_long = app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_LONG
        max_valid = app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_MAX_VALID
        notifications = obj.notifications.filter(created__isnull=False).order_by(
            "-timestamp"
        )
        data = [
            (rec[0] - rec[1]).total_seconds()
            for rec in notifications.values_list("created", "timestamp")
            if (rec[0] - rec[1]).total_seconds() < max_valid
        ]
        short = statistics.mean(data[:max_short]) if len(data) >= max_short else None
        medium = statistics.mean(data[:max_medium]) if len(data) >= max_medium else None
        long = statistics.mean(data[:max_long]) if len(data) >= max_long else None
        return f"{my_format(short)} | {my_format(medium)} | {my_format(long)}"

    _avg_turnaround_time.short_description = "Avg. turnaround time"

    def _structures_last_update_fresh(self, obj) -> int:
        return obj.is_structure_sync_fresh

    _structures_last_update_fresh.boolean = True
    _structures_last_update_fresh.short_description = "Last update fresh"

    def _notifications_last_update_fresh(self, obj) -> int:
        return obj.is_notification_sync_fresh

    _notifications_last_update_fresh.boolean = True
    _notifications_last_update_fresh.short_description = "Last update fresh"

    def _forwarding_last_update_fresh(self, obj) -> int:
        return obj.is_forwarding_sync_fresh

    _forwarding_last_update_fresh.boolean = True
    _forwarding_last_update_fresh.short_description = "Last update fresh"

    def _assets_last_update_fresh(self, obj) -> int:
        return obj.is_assets_sync_fresh

    _assets_last_update_fresh.boolean = True
    _assets_last_update_fresh.short_description = "Last update fresh"

    def get_form(self, *args, **kwargs):
        """Add help text to custom field."""
        help_texts = {
            "_avg_turnaround_time": (
                "For last %d | %d | %d notifications"
                % (
                    app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_SHORT,
                    app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_MEDIUM,
                    app_settings.STRUCTURES_NOTIFICATION_TURNAROUND_LONG,
                )
            ),
            "_are_all_syncs_ok": (
                "True when all syncs were successful and not older then "
                "the respective grace period."
            ),
            "_structures_last_update_fresh": (
                "True when last sync within %s minutes."
                % app_settings.STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES
            ),
            "_notifications_last_update_fresh": (
                "True when last sync within %s minutes."
                % app_settings.STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES
            ),
            "_forwarding_last_update_fresh": (
                "True when last sync within %s minutes."
                % app_settings.STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES
            ),
            "_assets_last_update_fresh": (
                "True when last sync within %s minutes."
                % app_settings.STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES
            ),
        }
        kwargs.update({"help_texts": help_texts})
        return super().get_form(*args, **kwargs)


@admin.register(StructureTag)
class StructureTagAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "description",
        "order",
        "style",
        "is_default",
        "is_user_managed",
    )
    list_filter = (
        "is_default",
        "style",
        "is_user_managed",
    )
    readonly_fields = ("is_user_managed",)

    def has_delete_permission(self, request, obj=None):
        return False if obj and not obj.is_user_managed else True

    def has_change_permission(self, request, obj=None):
        return False if obj and not obj.is_user_managed else True


class StructureAdminInline(admin.TabularInline):
    model = StructureService

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OwnerCorporationsFilter(admin.SimpleListFilter):
    """Custom filter to filter on corporations from owners only"""

    title = "owner corporation"
    parameter_name = "owner_corporation_id__exact"

    def lookups(self, request, model_admin):
        qs = (
            EveCorporationInfo.objects.filter(structure_owner__isnull=False)
            .values("corporation_id", "corporation_name")
            .distinct()
            .order_by(Lower("corporation_name"))
        )
        return tuple([(x["corporation_id"], x["corporation_name"]) for x in qs])

    def queryset(self, request, qs):
        if self.value() is None:
            return qs.all()
        else:
            return qs.filter(owner__corporation__corporation_id=self.value())


class OwnerAllianceFilter(admin.SimpleListFilter):
    """Custom filter to filter on alliances from owners only"""

    title = "owner alliance"
    parameter_name = "owner_alliance_id__exact"

    def lookups(self, request, model_admin):
        qs = (
            EveAllianceInfo.objects.filter(
                evecorporationinfo__structure_owner__isnull=False
            )
            .values("alliance_id", "alliance_name")
            .distinct()
            .order_by(Lower("alliance_name"))
        )
        return tuple([(x["alliance_id"], x["alliance_name"]) for x in qs])

    def queryset(self, request, qs):
        if self.value() is None:
            return qs.all()
        else:
            return qs.filter(owner__corporation__alliance__alliance_id=self.value())


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    show_full_result_count = True
    list_select_related = (
        "owner",
        "owner__corporation",
        "owner__corporation__alliance",
        "eve_solar_system",
        "eve_solar_system__eve_constellation__eve_region",
        "eve_type",
        "eve_type__eve_group",
        "eve_type__eve_group__eve_category",
        "eve_planet",
        "eve_moon",
    )
    search_fields = [
        "name",
        "owner__corporation__corporation_name",
        "eve_solar_system__name",
    ]
    ordering = ["name"]
    list_display = ("name", "_owner", "_location", "_type", "_power_mode", "_tags")
    list_filter = (
        OwnerCorporationsFilter,
        OwnerAllianceFilter,
        ("eve_solar_system", admin.RelatedOnlyFieldListFilter),
        (
            "eve_solar_system__eve_constellation__eve_region",
            admin.RelatedOnlyFieldListFilter,
        ),
        ("eve_type", admin.RelatedOnlyFieldListFilter),
        ("eve_type__eve_group", admin.RelatedOnlyFieldListFilter),
        ("eve_type__eve_group__eve_category", admin.RelatedOnlyFieldListFilter),
        ("tags", admin.RelatedOnlyFieldListFilter),
    )

    actions = ("add_default_tags", "remove_user_tags", "update_generated_tags")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("tags")

    def _owner(self, structure):
        alliance = structure.owner.corporation.alliance
        return format_html(
            "{}<br>{}",
            structure.owner.corporation,
            alliance if alliance else "",
        )

    def _location(self, structure):
        if structure.eve_moon:
            location_name = structure.eve_moon.name
        elif structure.eve_planet:
            location_name = structure.eve_planet.name
        else:
            location_name = structure.eve_solar_system.name
        return format_html(
            "{}<br>{}",
            location_name,
            structure.eve_solar_system.eve_constellation.eve_region,
        )

    def _type(self, structure):
        return format_html("{}<br>{}", structure.eve_type, structure.eve_type.eve_group)

    def _power_mode(self, structure):
        return structure.get_power_mode_display()

    def _tags(self, structure):
        return sorted([tag.name for tag in structure.tags.all()])

    _tags.short_description = "Tags"

    def has_add_permission(self, request):
        return False

    def add_default_tags(self, request, queryset):
        structure_count = 0
        tags = StructureTag.objects.filter(is_default=True)
        for structure in queryset:
            for tag in tags:
                structure.tags.add(tag)
            structure_count += 1

        self.message_user(
            request,
            "Added {:,} default tags to {:,} structures".format(
                tags.count(), structure_count
            ),
        )

    add_default_tags.short_description = "Add default tags to selected structures"

    def remove_user_tags(self, request, queryset):
        structure_count = 0
        for structure in queryset:
            for tag in structure.tags.filter(is_user_managed=True):
                structure.tags.remove(tag)
            structure_count += 1

        self.message_user(
            request,
            "Removed all user tags from {:,} structures".format(structure_count),
        )

    remove_user_tags.short_description = "Remove user tags for selected structures"

    def update_generated_tags(self, request, queryset):
        structure_count = 0
        for structure in queryset:
            structure.update_generated_tags(recreate_tags=True)
            structure_count += 1

        self.message_user(
            request,
            "Updated all generated tags for {:,} structures".format(structure_count),
        )

    update_generated_tags.short_description = (
        "Update generated tags for selected structures"
    )

    readonly_fields = tuple(
        [
            x.name
            for x in Structure._meta.get_fields()
            if isinstance(x, models.fields.Field) and x.name not in ["tags"]
        ]
    )
    fieldsets = (
        (None, {"fields": ("name", "owner", "eve_solar_system", "eve_type", "tags")}),
        (
            "Status",
            {
                "classes": ("collapse",),
                "fields": (
                    "state",
                    (
                        "state_timer_start",
                        "state_timer_end",
                    ),
                    "unanchors_at",
                    "fuel_expires_at",
                    "last_online_at",
                    "has_fitting",
                    "has_core",
                ),
            },
        ),
        (
            "Reinforcement",
            {
                "classes": ("collapse",),
                "fields": (
                    ("reinforce_hour",),
                    (
                        "next_reinforce_hour",
                        "next_reinforce_apply",
                    ),
                ),
            },
        ),
        (
            "Position",
            {
                "classes": ("collapse",),
                "fields": ("position_x", "position_y", "position_z"),
            },
        ),
        (
            None,
            {
                "fields": (
                    (
                        "id",
                        "last_updated_at",
                    )
                )
            },
        ),
    )
    inlines = (StructureAdminInline,)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """only show custom tags in dropdown"""
        if db_field.name == "tags":
            kwargs["queryset"] = StructureTag.objects.filter(is_user_managed=True)

        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    ordering = ["name"]
    list_display = (
        "name",
        "_ping_groups",
        "_owners",
        "is_active",
        "_is_default",
        "_messages_in_queue",
    )
    list_filter = ("is_active",)
    save_as = True

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("ping_groups", "owner_set", "owner_set__corporation")

    def _default_pings(self, obj):
        return obj.has_default_pings_enabled

    _default_pings.boolean = True

    def _ping_groups(self, obj):
        return sorted([ping_group.name for ping_group in obj.ping_groups.all()])

    def _owners(self, obj):
        return sorted([str(owner) for owner in obj.owner_set.all()])

    _owners.short_description = "Enabled for Owners"

    def _is_default(self, obj):
        value = True if obj.is_default else None
        return admin_boolean_icon_html(value)

    def _messages_in_queue(self, obj):
        return obj.queue_size()

    actions = ("test_notification", "activate", "deactivate", "purge_messages")

    def test_notification(self, request, queryset):
        for obj in queryset:
            tasks.send_test_notifications_to_webhook.delay(
                obj.pk, user_pk=request.user.pk
            )
            self.message_user(
                request,
                'Initiated sending test notification to webhook "{}". '
                "You will receive a report on completion.".format(obj),
            )

    test_notification.short_description = "Send test notification to selected webhooks"

    def activate(self, request, queryset):
        for obj in queryset:
            obj.is_active = True
            obj.save()
            self.message_user(request, f'You have activated webhook "{obj}"')

    activate.short_description = "Activate selected webhook"

    def deactivate(self, request, queryset):
        for obj in queryset:
            obj.is_active = False
            obj.save()

            self.message_user(request, f'You have de-activated webhook "{obj}"')

    deactivate.short_description = "Deactivate selected webhook"

    def purge_messages(self, request, queryset):
        actions_count = 0
        killmails_deleted = 0
        for webhook in queryset:
            killmails_deleted += webhook.clear_queue()
            actions_count += 1

        self.message_user(
            request,
            f"Purged queued messages for {actions_count} webhooks, "
            f"deleting a total of {killmails_deleted} messages.",
        )

    purge_messages.short_description = "Purge queued messages from selected webhooks"

    filter_horizontal = ("ping_groups",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "url",
                    "notes",
                    "notification_types",
                    "ping_groups",
                    "is_active",
                    "is_default",
                )
            },
        ),
        (
            "Advanced Options",
            {
                "classes": ("collapse",),
                "fields": (
                    "language_code",
                    "has_default_pings_enabled",
                    "webhook_type",
                ),
            },
        ),
    )
