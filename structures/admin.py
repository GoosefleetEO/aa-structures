from django.contrib import admin
from django.conf import settings

from .models import *
from . import tasks


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ('corporation', 'character', 'last_sync')
    actions = ['update_structures', 'fetch_notifications']

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
            tasks.update_notifications_for_owner.delay(                
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


@admin.register(EveRegion)
class EveRegionAdmin(admin.ModelAdmin):
    pass


@admin.register(EveConstellation)
class EveConstellationSystemAdmin(admin.ModelAdmin):
    pass


@admin.register(EveSolarSystem)
class EveSolarSystemAdmin(admin.ModelAdmin):
    pass


@admin.register(EveType)
class EveTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(EveGroup)
class EveGroupAdmin(admin.ModelAdmin):
    pass


class StructureAdminInline(admin.TabularInline):
    model = StructureService


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = ('name', 'eve_solar_system', 'eve_type', 'owner')
    list_filter = ('eve_solar_system', 'eve_type', 'owner')

    inlines = (StructureAdminInline, )

    def has_add_permission(self, request):
        if settings.DEBUG:
            return True
        else:
            return False

    def has_change_permission(self, request, obj=None):
        if settings.DEBUG:
            return True
        else:
            return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'notification_id', 
        'owner', 
        'notification_type', 
        'timestamp',
        'webhook',
        'is_sent'
    )
    list_filter = ( 'owner', 'notification_type', 'is_sent')
    actions = ['send_to_webhook']

    def webhook(self, obj):
        return obj.owner.webhook

    def send_to_webhook(self, request, queryset):
                        
        for obj in queryset:            
            tasks.send_notification.delay(obj.pk)
            text = 'Initiated sending of notification {} to webhook {}'.format(
                obj.notification_id,
                obj.owner.webhook
            )
            
            self.message_user(
                request, 
                text
            )
    
    send_to_webhook.short_description = "Send to configured webhook"

    def has_add_permission(self, request):
        if settings.DEBUG:
            return True
        else:
            return False

    def has_change_permission(self, request, obj=None):
        if settings.DEBUG:
            return True
        else:
            return False


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('name', 'webhook_type', 'is_default', 'is_active')
    list_filter = ( 'webhook_type', 'is_active')

    actions = ('test_notification', )

    def test_notification(self, request, queryset):                        
        for obj in queryset:
            tasks.send_test_notifications_to_webhook.delay(                
                obj.pk,
                user_pk=request.user.pk
            )            
            text = 'Initiated sending test notification to webhook "{}".'\
                .format(obj) + ' You will receive a report on completion.'

            self.message_user(
                request, 
                text
            )
    
    test_notification.short_description = "Send test notification to webhook"


@admin.register(NotificationEntity)
class NotificationEntityAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'name', 
        'entity_type',         
    )
    list_filter = ( 'entity_type', )
    list_display_links = None

    def has_add_permission(self, request):
        if settings.DEBUG:
            return True
        else:
            return False

    def has_change_permission(self, request, obj=None):
        if settings.DEBUG:
            return True
        else:
            return False
