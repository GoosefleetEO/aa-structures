from django.contrib import admin

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

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    pass