from django.contrib import admin
from django.contrib.admin import SimpleListFilter

from .app_settings import STRUCTURES_DEVELOPER_MODE
from .models import *
from . import tasks
from .utils import LoggerAddTag

logger = LoggerAddTag(logging.getLogger(__name__), __package__)

if STRUCTURES_DEVELOPER_MODE:
    @admin.register(EveConstellation)
    class EveConstellationAdmin(admin.ModelAdmin):
       pass


    @admin.register(EveEntity)
    class EveEntityAdmin(admin.ModelAdmin):
        list_display = (
            'id', 
            'name', 
            'category',         
        )
        list_filter = ( 'category', )
        list_display_links = None


    @admin.register(EveGroup)
    class EveGroupAdmin(admin.ModelAdmin):
        pass

    @admin.register(EveMoon)
    class EveMoonAdmin(admin.ModelAdmin):
        pass


    @admin.register(EveRegion)
    class EveRegionAdmin(admin.ModelAdmin):
        pass


    @admin.register(EveSolarSystem)
    class EveSolarSystemAdmin(admin.ModelAdmin):
       pass


    @admin.register(EveType)
    class EveTypeAdmin(admin.ModelAdmin):
        pass   


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'notification_id', 
        'owner', 
        'notification_type', 
        'timestamp',
        'created',
        'last_updated',        
        'webhook_list',
        'is_sent',
        'is_timer_added'
    )
    list_filter = ( 'owner', 'notification_type', 'is_sent')
    
    def webhook_list(self, obj):
        return ', '.join([x.name for x in obj.owner.webhooks.all().order_by('name')])

    actions = ('mark_as_sent', 'mark_as_unsent', 'send_to_webhook', 'add_to_timerboard')

    def mark_as_sent(self, request, queryset):                        
        notifications_count = 0
        for obj in queryset:
            obj.is_sent = True
            obj.save()
            notifications_count += 1

        self.message_user(
            request, 
            '{} notifications marked as sent'.format(notifications_count)
        )

    mark_as_sent.short_description = "Mark selected notifications as sent"

    def mark_as_unsent(self, request, queryset):                        
        notifications_count = 0
        for obj in queryset:
            obj.is_sent = False
            obj.save()
            notifications_count += 1

        self.message_user(
            request, 
            '{} notifications marked as unsent'.format(notifications_count)
        )

    mark_as_unsent.short_description = \
        "Mark selected notifications as unsent"
    
    def send_to_webhook(self, request, queryset):
        notifications_count = 0
        for obj in queryset:            
            tasks.send_notification.delay(obj.pk)            
            notifications_count += 1
            
        self.message_user(
            request, 
            'Initiated sending of {} notifications to configured webhooks'.format(
                notifications_count
        ))
    
    send_to_webhook.short_description = \
        "Send selected notifications to configured webhooks"

    def add_to_timerboard(self, request, queryset):
        notifications_count = 0
        for obj in queryset:            
            if obj.add_to_timerboard():
                notifications_count += 1
            
        self.message_user(
            request, 
            'Added timers from {} notifications to timerboard'.format(
                notifications_count
        ))
    
    add_to_timerboard.short_description = \
        "Add selected notifications to timerboard"

    def has_add_permission(self, request):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False

    def has_change_permission(self, request, obj=None):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False


class OwnerSyncStatusFilter(admin.SimpleListFilter):
    title = 'sync status'

    parameter_name = 'sync_status'
    
    def lookups(self, request, model_admin):
        """List of values to allow admin to select"""
        return (
            ('online', 'Online'),
            ('offline', 'Offline'),
        )

    def queryset(self, request, queryset):
        """Return the filtered queryset"""

        if self.value() == 'online':
            return queryset.filter(
                structures_last_error__exact=Owner.ERROR_NONE,
                notifications_last_error=Owner.ERROR_NONE,
                forwarding_last_error=Owner.ERROR_NONE
            )
        elif self.value() == 'offline':
            return queryset.exclude(
                structures_last_error__exact=Owner.ERROR_NONE,
                notifications_last_error=Owner.ERROR_NONE,
                forwarding_last_error=Owner.ERROR_NONE
            )
        else:
            return queryset


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = (
        'corporation', 
        'alliance',
        'character', 
        '_webhooks',
        'sync_status',         
    )

    list_filter = (        
        ('corporation__alliance', admin.RelatedOnlyFieldListFilter),
        OwnerSyncStatusFilter, 
    )

    fieldsets = (
            (None, {
                'fields': (
                    'corporation', 'character', 'webhooks', 'is_alliance_main', 'is_included_in_service_status'
                )
            }),
            ('Sync Status', {
                'classes': ('collapse',),
                'fields': (                    
                    ('structures_last_sync', 'structures_last_error', ),
                    ('notifications_last_sync', 'notifications_last_error', ),
                    ('forwarding_last_sync', 'forwarding_last_error', ),
                )
            }),
    )
    
    def alliance(self, obj):        
        return obj.corporation.alliance
        
    
    def _webhooks(self, obj):
        return ', '.join([x.name for x in obj.webhooks.all().order_by('name')])

    _webhooks.short_description = 'Webhooks'


    def sync_status(self, obj):
        return obj.notifications_last_error == Owner.ERROR_NONE \
            and obj.structures_last_error == Owner.ERROR_NONE \
            and obj.forwarding_last_error == Owner.ERROR_NONE

    sync_status.boolean = True


    def get_readonly_fields(self, request, obj = None):
        if obj: # editing an existing object
            return self.readonly_fields + (
                'notifications_last_error', 
                'notifications_last_sync',
                'structures_last_error',
                'structures_last_sync',
                'forwarding_last_sync',
                'forwarding_last_error',
            )
        return self.readonly_fields


    actions = ('update_structures', 'fetch_notifications', 'send_notifications')


    def update_structures(self, request, queryset):
                        
        for obj in queryset:            
            tasks.update_structures_for_owner.delay(                
                obj.pk,
                force_sync=True,
                user_pk=request.user.pk
            )            
            text = 'Started updating structures for: {}. '.format(obj)
            text += 'You will receive a notification once it is completed.'

            self.message_user(
                request, 
                text
            )
    
    update_structures.short_description = "Update structures from EVE server"

    def fetch_notifications(self, request, queryset):
                        
        for obj in queryset:            
            tasks.fetch_notifications_for_owner.delay(                
                obj.pk,
                force_sync=True,
                user_pk=request.user.pk
            )            
            text = 'Started fetching notifications for: {}. '.format(obj)
            text += 'You will receive a notification once it is completed.'

            self.message_user(
                request, 
                text
            )
    
    fetch_notifications.short_description = "Fetch notifications from EVE server"

    def send_notifications(self, request, queryset):
                        
        for obj in queryset:            
            tasks.send_new_notifications_for_owner.delay(                
                obj.pk
            )            
            text = 'Started sending new notifications for: {}. '.format(obj)
            #text += 'You will receive a notification once it is completed.'

            self.message_user(
                request, 
                text
            )
    
    send_notifications.short_description = "Send new notifications to Discord"


@admin.register(StructureTag)
class StructureTagAdmin(admin.ModelAdmin):
    list_display = (        
        'name', 
        'description',
        'style',
        'is_default',
    )
    list_filter = ( 
        'is_default', 
        'style',
    )
    

class StructureAdminInline(admin.TabularInline):
    model = StructureService

    def has_add_permission(self, request):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False

    def has_change_permission(self, request, obj=None):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False

    def has_delete_permission(self, request, obj=None):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = (
        'name', 
        'eve_solar_system', 
        'eve_type', 
        'owner', 
        'alliance', 
        '_tags'
    )
    list_filter = (        
        ('eve_solar_system', admin.RelatedOnlyFieldListFilter),        
        ('eve_type', admin.RelatedOnlyFieldListFilter),
        'owner',                 
        ('tags', admin.RelatedOnlyFieldListFilter),
    )

    def alliance(self, obj):        
        return obj.owner.corporation.alliance

    if not STRUCTURES_DEVELOPER_MODE:        
        readonly_fields = tuple([
            x.name for x in Structure._meta.get_fields()
            if isinstance(x, models.fields.Field)
            and x.name not in ['tags']
        ])
        
        fieldsets = (
            (None, {
                'fields': (
                    'name', 'eve_type', 'eve_solar_system', 'owner', 'tags'
                )
            }),
            ('Status', {
                'classes': ('collapse',),
                'fields': (
                    'state',
                    ('state_timer_start', 'state_timer_end', ),
                    'unanchors_at',
                    'fuel_expires'
                )
            }),
            ('Reinforcement', {
                'classes': ('collapse',),
                'fields': (
                    ('reinforce_hour', ),
                    (
                        'next_reinforce_hour', 
                        'next_reinforce_weekday', 
                        'next_reinforce_apply'
                    ),
                )
            }),
            ('Position', {
                'classes': ('collapse',),
                'fields': ('position_x', 'position_y' , 'position_z')
            }),
            (None, {
                'fields': (                     
                    ('id', 'last_updated', )
                )
            }),
        )
       
    inlines = (StructureAdminInline, )

    actions = ('add_default_tags', 'remove_all_tags', )

    def _tags(self, obj):
        return tuple([x.name for x in obj.tags.all().order_by('name')])

    _tags.short_description = 'Tags'
    

    def has_add_permission(self, request):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False

    def add_default_tags(self, request, queryset):
        structure_count = 0
        tags = StructureTag.objects.filter(is_default__exact=True)
        for obj in queryset:            
            for tag in tags:
                obj.tags.add(tag)            
            structure_count += 1
            
        self.message_user(
            request, 
            'Added {:,} default tags to {:,} structures'.format(
                tags.count(),
                structure_count
            ))
    
    add_default_tags.short_description = \
        "Add default tags to selected structures"

    def remove_all_tags(self, request, queryset):
        structure_count = 0
        for obj in queryset:            
            obj.tags.clear()
            structure_count += 1
            
        self.message_user(
            request, 
            'Removed all tags from {:,} structures'.format(structure_count))
    
    remove_all_tags.short_description = \
        "Remove all tags from selected structures"
    


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('name', 'webhook_type', 'is_active', 'is_default')
    list_filter = ( 'webhook_type', 'is_active')

    save_as = True

    actions = (
        'test_notification', 
        'activate', 
        'deactivate'
    )

    def test_notification(self, request, queryset):
        for obj in queryset:
            tasks.send_test_notifications_to_webhook.delay(
                obj.pk,
                user_pk=request.user.pk
            )            
            self.message_user(
                request,
                'Initiated sending test notification to webhook "{}".'\
                    .format(obj) + ' You will receive a report on completion.'
            )
    
    test_notification.short_description = \
        "Send test notification to selected webhooks"

    def activate(self, request, queryset):                                
        for obj in queryset:
            obj.is_active = True
            obj.save()
            
            self.message_user(
                request, 
                'You have activated profile "{}"'.format(obj)
            )

    activate.short_description = 'Activate selected profiles'

    def deactivate(self, request, queryset):                        
        for obj in queryset:
            obj.is_active = False
            obj.save()
            
            self.message_user(
                request, 
                'You have de-activated profile "{}"'.format(obj)
            )

    deactivate.short_description = 'Deactivate selected profiles'

    
