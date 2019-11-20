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


@admin.register(EveRegion)
class EveRegionAdmin(admin.ModelAdmin):
    pass


@admin.register(EveConstellation)
class EveConstellationSystemAdmin(admin.ModelAdmin):
    pass


@admin.register(EveSolarSystem)
class EveSolarSystemAdmin(admin.ModelAdmin):
    pass


@admin.register(EveMoon)
class EveMoonAdmin(admin.ModelAdmin):
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
    
    def webhook(self, obj):
        return obj.owner.webhook

    actions = ('mark_as_sent', 'mark_as_unsent', 'send_to_webhook')

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
        "Send selected notifications to configured webhook"

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


@admin.register(NotificationEntity)
class NotificationEntityAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'name', 
        'category',         
    )
    list_filter = ( 'category', )
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


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('name', 'webhook_type')
    list_filter = ( 'webhook_type', )

    actions = ('test_notification', )

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


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'webhook', 'is_active')
    list_filter = ('owner', 'webhook', 'is_active')

    actions = ('activate', 'deactivate', )

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
