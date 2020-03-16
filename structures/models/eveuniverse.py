"""Eve Universe models"""

import logging
import urllib

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import translation

from ..managers import EveUniverseManager
from ..utils import LoggerAddTag

logger = LoggerAddTag(logging.getLogger(__name__), __package__)


class EveUniverse(models.Model):
    """Base class for all EveUniverse models"""

    # language code mappings
    # Django, Eve Universe models, ESI
    LANG_CODES_MAPPING = (
        ('en', 'en', 'en-us'),
        ('de', 'de', 'de'),
        ('ko', 'ko', 'ko'),
        ('ru', 'ru', 'ru'),
        ('zh-hans', 'zh', 'zh'),
    )
    LANG_CODES_DJANGO = 0
    LANG_CODES_MODEL = 1
    LANG_CODES_ESI = 2

    ESI_LANGUAGES = {x[2] for x in LANG_CODES_MAPPING}
    ESI_DEFAULT_LANGUAGE = 'en-us'

    id = models.PositiveIntegerField(
        primary_key=True, help_text=_('Eve Online ID')
    )
    name = models.CharField(
        max_length=100, help_text=_('Eve Online name')
    )    
    name_de = models.CharField(
        max_length=100,        
        blank=True,
        help_text=_('Eve Online name localized for German')
    )   
    name_ko = models.CharField(
        max_length=100,        
        blank=True,
        help_text=_('Eve Online name localized for Korean')
    )    
    name_ru = models.CharField(
        max_length=100,        
        blank=True,
        help_text=_('Eve Online name localized for Russian')
    )    
    name_zh = models.CharField(
        max_length=100,        
        blank=True,
        help_text=_('Eve Online name localized for Chinese')
    )    
    last_updated = models.DateTimeField(
        default=None,
        null=True,
        blank=True,
        help_text=_('When this object was last updated from ESI'),
        db_index=True
    )    

    objects = EveUniverseManager()

    def __repr__(self):
        return '{}(id={}, name=\'{}\')'.format(
            self.__class__.__name__,
            self.id,
            self.name
        )

    def __str__(self):
        return self.name

    @property
    def name_localized(self):
        """returns the localized version of name for the current language
        will return the default if a translation does not exist
        """        
        lang_mapping = self.language_code_translation(
            translation.get_language(), self.LANG_CODES_DJANGO
        )
        if lang_mapping and (
            lang_mapping[self.LANG_CODES_ESI] != self.ESI_DEFAULT_LANGUAGE
        ):
            field_ext = lang_mapping[self.LANG_CODES_MODEL]        
            field_name = ('name_%s' % field_ext) if field_ext else 'name'
        else:
            field_name = 'name'
        if not hasattr(self, field_name):
            raise NotImplementedError(
                'field name "%s" not found in %s' % (
                    field_name, type(self).__name__
                )
            )
        name_translation = getattr(self, field_name)
        return name_translation if name_translation else self.name

    class Meta:
        abstract = True

    @classmethod
    def language_code_translation(cls, code: str, category_from: int) -> tuple:
        """translates language codes between systems"""
        result = None
        for mapping in cls.LANG_CODES_MAPPING:
            if mapping[category_from] == code:
                result = mapping
        return result
    
    @classmethod
    def esi_pk(cls):
        """returns the name of the pk column on ESI that must exist"""
        return cls._eve_universe_meta_attr('esi_pk', is_mandatory=True)
       
    @classmethod
    def esi_method(cls):        
        return cls._eve_universe_meta_attr('esi_method', is_mandatory=True)
                    
    @classmethod
    def field_names_not_pk(cls) -> set:
        """returns field names excl. PK, localization and auto created fields"""
        return {
            x.name for x in cls._meta.get_fields()
            if not x.auto_created and (
                not hasattr(x, 'primary_key') or x.primary_key is False
            ) and x.name not in {'language_code', 'last_updated'}
            and 'name_' not in x.name
        }

    @classmethod
    def child_mappings(cls) -> dict:
        """returns the mapping of children for this class"""
        mappings = cls._eve_universe_meta_attr('children')        
        return mappings if mappings else dict()

    @classmethod
    def field_mappings(cls) -> dict:
        """returns the mappings for model fields vs. esi fields"""        
        mappings = cls._eve_universe_meta_attr('field_mappings')
        return mappings if mappings else dict()

    @classmethod
    def fk_mappings(cls) -> dict:
        """returns the foreign key mappings for this class
        
        'model field name': ('Foreign Key name on ESI', 'related model class')
        """
        
        def convert_to_esi_name(name: str, extra_fk_mappings: dict) -> str:            
            if name in extra_fk_mappings:
                esi_name = extra_fk_mappings[name]
            else:
                esi_name = name.replace('eve_', '') + '_id'
            return esi_name
        
        extra_fk_mappings = cls._eve_universe_meta_attr('fk_mappings')
        if not extra_fk_mappings:
            extra_fk_mappings = {}

        mappings = {
            x.name: (
                convert_to_esi_name(x.name, extra_fk_mappings), 
                x.related_model
            )
            for x in cls._meta.get_fields() 
            if isinstance(x, models.ForeignKey)
        }
        return mappings
    
    @classmethod
    def has_localization(cls) -> bool:
        has_localization = cls._eve_universe_meta_attr('has_localization')
        return True if has_localization is None else has_localization
        
    @classmethod
    def _eve_universe_meta_attr(
        cls, attr_name: str, is_mandatory: bool = False
    ):
        """returns value of an attribute from EveUniverseMeta or None"""
        if not hasattr(cls, 'EveUniverseMeta'):
            raise ValueError(
                'EveUniverseMeta not defined for class %s' % cls.__name__
            )
    
        if hasattr(cls.EveUniverseMeta, attr_name):
            value = getattr(cls.EveUniverseMeta, attr_name)
        else:
            value = None
            if is_mandatory:
                raise ValueError(
                    'Mandatory attribute EveUniverseMeta.%s not defined '
                    'for class %s' % (attr_name, cls.__name__)
                )
        return value


class EveCategory(EveUniverse):
    """group in Eve Online"""

    # named category IDs
    EVE_CATEGORY_ID_ORBITAL = 46
    EVE_CATEGORY_ID_STARBASE = 23
    EVE_CATEGORY_ID_STRUCTURE = 65

    @property
    def is_starbase(self):
        return self.id == self.EVE_CATEGORY_ID_STARBASE

    @property
    def is_upwell_structure(self):
        return self.id == self.EVE_CATEGORY_ID_STRUCTURE
    
    class EveUniverseMeta:
        esi_pk = 'category_id'
        esi_method = 'get_universe_categories_category_id'


class EveGroup(EveUniverse):
    """group in Eve Online"""
    
    eve_category = models.ForeignKey(
        EveCategory,
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True
    )

    class EveUniverseMeta:
        esi_pk = 'group_id'
        esi_method = 'get_universe_groups_group_id'


class EveType(EveUniverse):
    """type in Eve Online"""

    # named type IDs
    EVE_TYPE_ID_POCO = 2233
    EVE_TYPE_ID_TCU = 32226
    EVE_TYPE_ID_IHUB = 32458

    EVE_IMAGESERVER_BASE_URL = 'https://images.evetech.net'
    
    eve_group = models.ForeignKey(EveGroup, on_delete=models.CASCADE)

    class EveUniverseMeta:
        esi_pk = 'type_id'
        esi_method = 'get_universe_types_type_id'
    
    @property
    def is_poco(self):
        return self.id == self.EVE_TYPE_ID_POCO

    @property
    def is_starbase(self):
        return self.eve_group.eve_category.is_starbase

    @property
    def is_upwell_structure(self):
        return self.eve_group.eve_category.is_upwell_structure

    @classmethod
    def generic_icon_url(cls, type_id: int, size: int = 64) -> str:
        if size < 32 or size > 1024 or (size % 2 != 0):
            raise ValueError("Invalid size: {}".format(size))

        url = '{}/types/{}/icon'.format(
            cls.EVE_IMAGESERVER_BASE_URL,
            int(type_id)
        )
        if size:
            args = {'size': int(size)}
            url += '?{}'.format(urllib.parse.urlencode(args))

        return url

    def icon_url(self, size=64):
        return self.generic_icon_url(self.id, size)


class EveRegion(EveUniverse):
    """region in Eve Online"""
    
    class EveUniverseMeta:
        esi_pk = 'region_id'
        esi_method = 'get_universe_regions_region_id'
    

class EveConstellation(EveUniverse):
    """constellation in Eve Online"""

    eve_region = models.ForeignKey(EveRegion, on_delete=models.CASCADE)

    class EveUniverseMeta:
        esi_pk = 'constellation_id'
        esi_method = 'get_universe_constellations_constellation_id'


class EveSolarSystem(EveUniverse):
    """solar system in Eve Online"""
    
    eve_constellation = models.ForeignKey(
        EveConstellation,
        on_delete=models.CASCADE
    )
    security_status = models.FloatField()

    class EveUniverseMeta:
        esi_pk = 'system_id'
        esi_method = 'get_universe_systems_system_id'
        children = {
            'planets': 'EvePlanet'
        }


class EveMoon(EveUniverse):  
    """"moon in Eve Online"""

    position_x = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('x position in the solar system')
    )
    position_y = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('y position in the solar system')
    )
    position_z = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('z position in the solar system')
    )
    eve_solar_system = models.ForeignKey(
        EveSolarSystem,
        on_delete=models.CASCADE
    )

    class EveUniverseMeta:
        esi_pk = 'moon_id'
        esi_method = 'get_universe_moons_moon_id'
        fk_mappings = {
            'eve_solar_system': 'system_id'
        }
        field_mappings = {            
            'position_x': ('position', 'x'),
            'position_y': ('position', 'y'),
            'position_z': ('position', 'z')
        }
        has_localization = False


class EvePlanet(EveUniverse):
    """"planet in Eve Online"""
    
    position_x = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('x position in the solar system')
    )
    position_y = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('y position in the solar system')
    )
    position_z = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('z position in the solar system')
    )
    eve_solar_system = models.ForeignKey(
        EveSolarSystem,
        on_delete=models.CASCADE
    )
    eve_type = models.ForeignKey(
        EveType,
        on_delete=models.CASCADE
    )

    class EveUniverseMeta:
        esi_pk = 'planet_id'
        esi_method = 'get_universe_planets_planet_id'
        fk_mappings = {
            'eve_solar_system': 'system_id'
        }
        field_mappings = {            
            'position_x': ('position', 'x'),
            'position_y': ('position', 'y'),
            'position_z': ('position', 'z')
        }
        has_localization = False
