from django.contrib import admin

from .app_settings import STRUCTURES_DEVELOPER_MODE
from .models import *
from . import tasks


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


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = (
        'corporation', 
        'character', 
        'webhooks_list',
        'no_errors',         
    )
    
    def webhooks_list(self, obj):
        return ', '.join([x.name for x in obj.webhooks.all().order_by('name')])

    def no_errors(self, obj):
        return obj.notifications_last_error == Owner.ERROR_NONE \
            and obj.structures_last_error == Owner.ERROR_NONE \
            and obj.forwarding_last_error == Owner.ERROR_NONE

    no_errors.boolean = True


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


    actions = ('update_structures', 'fetch_notifications')


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


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = ('name', 'eve_solar_system', 'eve_type', 'owner')
    list_filter = ('eve_solar_system', 'eve_type', 'owner')

    inlines = (StructureAdminInline, )

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

    
