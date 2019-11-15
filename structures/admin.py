from django.contrib import admin

from .models import *

@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    pass

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

@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    pass

@admin.register(StructureService)
class StructureServiceAdmin(admin.ModelAdmin):
    pass