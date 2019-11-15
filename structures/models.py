import logging

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCorporationInfo

from .managers import EveGroupManager, EveTypeManager, EveRegionManager, EveConstellationManager, EveSolarSystemManager
from .utils import LoggerAddTag, DATETIME_FORMAT


logger = LoggerAddTag(logging.getLogger(__name__), __package__)


class General(models.Model):
    """Meta model for global app permissions"""

    class Meta:
        managed = False                         
        default_permissions = ()
        permissions = ( 
            ('basic_access', 'Can access this app and view'),
            ('view_alliance_structures', 'Can view alliance structures'),
            ('view_all_structures', 'Can view all structures'),
            ('add_owner', 'Can add new structure owner'), 
        )


class Owner(models.Model):
    """corporation that owns structures"""

    # errors
    ERROR_NONE = 0
    ERROR_TOKEN_INVALID = 1
    ERROR_TOKEN_EXPIRED = 2
    ERROR_INSUFFICIENT_PERMISSIONS = 3    
    ERROR_NO_CHARACTER = 4
    ERROR_ESI_UNAVAILABLE = 5
    ERROR_OPERATION_MODE_MISMATCH = 6
    ERROR_UNKNOWN = 99

    ERRORS_LIST = [
        (ERROR_NONE, 'No error'),
        (ERROR_TOKEN_INVALID, 'Invalid token'),
        (ERROR_TOKEN_EXPIRED, 'Expired token'),
        (ERROR_INSUFFICIENT_PERMISSIONS, 'Insufficient permissions'),
        (ERROR_NO_CHARACTER, 'No character set for fetching alliance contacts'),
        (ERROR_ESI_UNAVAILABLE, 'ESI API is currently unavailable'),
        (ERROR_OPERATION_MODE_MISMATCH, 'Operaton mode does not match with current setting'),
        (ERROR_UNKNOWN, 'Unknown error'),
    ]

    corporation = models.OneToOneField(
        EveCorporationInfo, 
        primary_key=True, 
        on_delete=models.CASCADE,
        help_text='Corporation owning structures'
    )
    character = models.ForeignKey(
        CharacterOwnership,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        help_text='character used for syncing structures'
    )
    version_hash = models.CharField(
        max_length=32, 
        null=True, 
        default=None, 
        blank=True,
        help_text='hash to identify changes to structures'
    )
    last_sync = models.DateTimeField(
        null=True, 
        default=None, 
        blank=True,
        help_text='when the last sync happened'
    )
    last_error = models.IntegerField(
        choices=ERRORS_LIST, 
        default=ERROR_NONE,
        help_text='error that occurred at the last sync atttempt (if any)'
    )

    def __str__(self):
        return str(self.corporation.corporation_name)

    @classmethod
    def get_esi_scopes(cls) -> list:
        return [
            'esi-corporations.read_structures.v1',
            'esi-universe.read_structures.v1'
        ]


class EveRegion(models.Model):
    """region in Eve Online"""
    id = models.IntegerField(
        primary_key=True,
        validators=[MinValueValidator(0)],
        help_text='Eve Online region ID'
    )
    name = models.CharField(max_length=100)

    objects = EveRegionManager()

    def __str__(self):
        return self.name


class EveConstellation(models.Model):
    """constellation in Eve Online"""
    id = models.IntegerField(
        primary_key=True,
        validators=[MinValueValidator(0)],
        help_text='Eve Online region ID'
    )
    name = models.CharField(max_length=100)
    eve_region = models.ForeignKey(EveRegion, on_delete=models.CASCADE)

    objects = EveConstellationManager()

    def __str__(self):
        return self.name


class EveSolarSystem(models.Model):
    """solar system in Eve Online"""
    id = models.IntegerField(
        primary_key=True, 
        validators=[MinValueValidator(0)],
        help_text='Eve Online solar system ID'
    )
    name = models.CharField(max_length=100)
    eve_constellation = models.ForeignKey(
        EveConstellation, 
        on_delete=models.CASCADE
    )
    security_status = models.FloatField()

    objects = EveSolarSystemManager()

    def __str__(self):
        return self.name


class EveGroup(models.Model):
    """type in Eve Online"""
    id = models.IntegerField(
        primary_key=True,
        validators=[MinValueValidator(0)],
        help_text='Eve Online group ID'
    )
    name = models.CharField(max_length=100)

    objects = EveGroupManager()
    
    def __str__(self):
        return self.name


class EveType(models.Model):
    """type in Eve Online"""
    EVE_TYPE_ID_POCO = 2233

    id = models.IntegerField(
        primary_key=True,
        validators=[MinValueValidator(0)],
        help_text='Eve Online type ID'
    )
    name = models.CharField(max_length=100)
    eve_group = models.ForeignKey(EveGroup, on_delete=models.CASCADE)

    objects = EveTypeManager()
    
    def __str__(self):
        return self.name

    @property
    def is_poco(self):
        return id == self.EVE_TYPE_ID_POCO


class Structure(models.Model):
    """structure of a corporation"""

    STATE_NA = 0
    STATE_ANCHOR_VULNERABLE = 1
    STATE_ANCHORING = 2
    STATE_ARMOR_REINFORCE = 3
    STATE_ARMOR_VULNERABLE = 4
    STATE_DEPLOY_VULNERABLE = 5
    STATE_FITTING_INVULNERABLE = 6
    STATE_HULL_REINFORCE = 7
    STATE_HULL_VULNERABLE = 8
    STATE_ONLINE_DEPRECATED = 9
    STATE_ONLINING_VULNERABLE = 10
    STATE_SHIELD_VULNERABLE = 11
    STATE_UNANCHORED = 12
    STATE_UNKNOWN = 13
        
    STATE_CHOICES = [
        (STATE_NA, 'N/A'),
        (STATE_ANCHOR_VULNERABLE, 'anchor_vulnerable'),
        (STATE_ANCHORING, 'anchoring'),
        (STATE_ARMOR_REINFORCE, 'armor_reinforce'),
        (STATE_ARMOR_VULNERABLE, 'armor_vulnerable'),
        (STATE_DEPLOY_VULNERABLE, 'deploy_vulnerable'),
        (STATE_FITTING_INVULNERABLE, 'fitting_invulnerable'),
        (STATE_HULL_REINFORCE, 'hull_reinforce'),
        (STATE_HULL_VULNERABLE, 'hull_vulnerable'),
        (STATE_ONLINE_DEPRECATED, 'online_deprecated'),
        (STATE_ONLINING_VULNERABLE, 'onlining_vulnerable'),
        (STATE_SHIELD_VULNERABLE, 'shield_vulnerable'),
        (STATE_UNANCHORED, 'unanchored'),
        (STATE_UNKNOWN, 'unknown'),
    ]

    id = models.BigIntegerField(
        primary_key=True,
        help_text='The Item ID of the structure'
    )
    owner = models.ForeignKey(
        Owner, 
        on_delete=models.CASCADE,
        help_text='Corporation that owns the structure'
    )
    eve_type = models.ForeignKey(
        EveType, 
        on_delete=models.CASCADE,
        help_text='type of the structure'
    )
    name = models.CharField(
        max_length=255,
        help_text='The full name of the structure'
    )
    eve_solar_system = models.ForeignKey(EveSolarSystem, on_delete=models.CASCADE)
    position_x = models.FloatField(        
        help_text='x position of the structure in the solar system'
    )
    position_y = models.FloatField(        
        help_text='y position of the structure in the solar system'
    )
    position_z = models.FloatField(        
        help_text='z position of the structure in the solar system'
    )    
    fuel_expires = models.DateTimeField(
        null=True, 
        default=None, 
        blank=True,
        help_text='Date on which the structure will run out of fuel'
    )
    next_reinforce_hour = models.IntegerField(
        null=True, 
        default=None, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text='The requested change to reinforce_hour that will take effect at the time shown by next_reinforce_apply'
    )
    next_reinforce_weekday = models.IntegerField(
        null=True, 
        default=None, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text='The date and time when the structure’s newly requested reinforcement times (e.g. next_reinforce_hour and next_reinforce_day) will take effect'
    )    
    next_reinforce_apply = models.DateTimeField(
        null=True, 
        default=None, 
        blank=True,
        help_text='The requested change to reinforce_weekday that will take effect at the time shown by next_reinforce_apply'
    )
    profile_id = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text='The id of the ACL profile for this citadel'
    )
    reinforce_hour = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text='The hour of day that determines the four hour window when the structure will randomly exit its reinforcement periods and become vulnerable to attack against its armor and/or hull. The structure will become vulnerable at a random time that is +/- 2 hours centered on the value of this property'
    )
    reinforce_weekday = models.IntegerField(
        null=True, 
        default=None, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text='The day of the week when the structure exits its final reinforcement period and becomes vulnerable to attack against its hull. Monday is 0 and Sunday is 6'
    )
    state = models.IntegerField(
        choices=STATE_CHOICES,
        help_text='Current state of the structure'
    )    
    state_timer_start = models.DateTimeField(
        null=True, 
        default=None, 
        blank=True,
        help_text='Date at which the structure will move to it’s next state'
    )
    state_timer_end = models.DateTimeField(
        null=True, 
        default=None, 
        blank=True,
        help_text='Date at which the structure entered it’s current state'
    )
    unanchors_at = models.DateTimeField(
        null=True, 
        default=None, 
        blank=True,
        help_text='Date at which the structure will unanchor'
    )    
    last_updated = models.DateTimeField(
        help_text='The id of the ACL profile for this citadel'
    )

    @property
    def state_str(self):
        msg = [(x, y) for x, y in self.STATE_CHOICES if x == self.state]
        return msg[0][1] if len(msg) > 0 else 'Undefined'

    @property
    def is_low_power(self):
        return not self.fuel_expires

    @property
    def is_reinforced(self):
        return self.state in [
            self.STATE_ARMOR_REINFORCE, 
            self.STATE_HULL_REINFORCE
        ]

    def __str__(self):
        return '{} - {}'.format(self.eve_solar_system, self.name)

    @classmethod
    def get_matching_state(cls, state_name) -> int:
        """returns matching state for given state name"""
        match = cls.STATE_UNKNOWN
        for x in cls.STATE_CHOICES:
            if state_name == x[1]:
                match = x
                break
        
        return match[0]



class StructureService(models.Model):
    """service of a structure"""

    STATE_OFFLINE = 1
    STATE_ONLINE = 2
    
    STATE_CHOICES = [
        (STATE_OFFLINE, 'offline'),        
        (STATE_ONLINE, 'online'),        
    ]

    structure = models.ForeignKey(
        Structure, 
        on_delete=models.CASCADE,
        help_text='Structure this service is installed to'
    )
    name = models.CharField(
        max_length=64,
        help_text='Name of the service'
    )
    state = models.IntegerField(
        choices=STATE_CHOICES,
        help_text='Current state of this service'
    )

    class Meta:
        unique_together = (('structure', 'name'),)

    def __str__(self):
        return '{}-{}'.format(str(self.structure), self.name)

