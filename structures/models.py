import logging
from time import sleep
import yaml
import datetime
import json

import pytz
import dhooks_lite
from multiselectfield import MultiSelectField

from django.db import models, transaction
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.timezone import now

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCorporationInfo
from esi.clients import esi_client_factory

from .app_settings import *
from . import evelinks, __title__
from .managers import EveGroupManager, EveTypeManager, EveRegionManager,\
    EveConstellationManager, EveSolarSystemManager, \
    EveEntityManager, EveMoonManager, StructureManager
from .utils import LoggerAddTag, DATETIME_FORMAT, make_logger_prefix


logger = LoggerAddTag(logging.getLogger(__name__), __package__)

# Notification types
NTYPE_MOONMINING_AUTOMATIC_FRACTURE = 401
NTYPE_MOONMINING_EXTRACTION_CANCELED = 402
NTYPE_MOONMINING_EXTRACTION_FINISHED = 403
NTYPE_MOONMINING_EXTRACTION_STARTED = 404   
NTYPE_MOONMINING_LASER_FIRED = 405

NTYPE_STRUCTURE_ANCHORING = 501
NTYPE_STRUCTURE_DESTROYED = 502
NTYPE_STRUCTURE_FUEL_ALERT = 503
NTYPE_STRUCTURE_LOST_ARMOR = 504
NTYPE_STRUCTURE_LOST_SHIELD = 505
NTYPE_STRUCTURE_ONLINE = 506
NTYPE_STRUCTURE_SERVICES_OFFLINE = 507
NTYPE_STRUCTURE_UNANCHORING = 508
NTYPE_STRUCTURE_UNDER_ATTACK = 509
NTYPE_STRUCTURE_WENT_HIGH_POWER = 510
NTYPE_STRUCTURE_WENT_LOW_POWER = 511  
NTYPE_STRUCTURE_REINFORCE_CHANGED = 512
NTYPE_OWNERSHIP_TRANSFERRED = 513

NTYPE_CHOICES = [
    (NTYPE_MOONMINING_AUTOMATIC_FRACTURE, 'MoonminingAutomaticFracture'),    
    (NTYPE_MOONMINING_EXTRACTION_CANCELED, 'MoonminingExtractionCancelled'),
    (NTYPE_MOONMINING_EXTRACTION_FINISHED, 'MoonminingExtractionFinished'),
    (NTYPE_MOONMINING_EXTRACTION_STARTED, 'MoonminingExtractionStarted'),
    (NTYPE_MOONMINING_LASER_FIRED, 'MoonminingLaserFired'),
            
    (NTYPE_OWNERSHIP_TRANSFERRED, 'OwnershipTransferred'),
    (NTYPE_STRUCTURE_ANCHORING, 'StructureAnchoring'),
    (NTYPE_STRUCTURE_DESTROYED, 'StructureDestroyed'),
    (NTYPE_STRUCTURE_FUEL_ALERT, 'StructureFuelAlert'),
    (NTYPE_STRUCTURE_LOST_ARMOR, 'StructureLostArmor'),
    (NTYPE_STRUCTURE_LOST_SHIELD, 'StructureLostShields'),
    (NTYPE_STRUCTURE_ONLINE, 'StructureOnline'),
    (NTYPE_STRUCTURE_SERVICES_OFFLINE, 'StructureServicesOffline'),
    (NTYPE_STRUCTURE_UNANCHORING, 'StructureUnanchoring'),
    (NTYPE_STRUCTURE_UNDER_ATTACK, 'StructureUnderAttack'),
    (NTYPE_STRUCTURE_WENT_HIGH_POWER, 'StructureWentHighPower'),
    (NTYPE_STRUCTURE_WENT_LOW_POWER, 'StructureWentLowPower'),
]

NTYPE_RELEVANT_FOR_TIMERBOARD = [
    NTYPE_STRUCTURE_LOST_SHIELD,
    NTYPE_STRUCTURE_LOST_ARMOR,
    NTYPE_STRUCTURE_ANCHORING
]

class General(models.Model):
    """Meta model for global app permissions"""

    class Meta:
        managed = False                         
        default_permissions = ()
        permissions = ( 
            ('basic_access', 'Can access this app and view'),
            ('view_alliance_structures', 'Can view alliance structures'),
            ('view_all_structures', 'Can view all structures'),
            ('add_structure_owner', 'Can add new structure owner'), 
        )


def get_default_notification_types():
    """generates a set of all existing notification types as default"""
    return tuple(sorted([str(x[0]) for x in NTYPE_CHOICES]))


class Webhook(models.Model):
    """A destination for forwarding notification alerts"""
    
    TYPE_DISCORD = 1

    TYPE_CHOICES = [
        (TYPE_DISCORD, 'Discord Webhook'),        
    ]
    
    name = models.CharField(
        max_length=64, 
        unique=True,
        help_text='short name to identify this webhook'
    )
    webhook_type = models.IntegerField(
        choices=TYPE_CHOICES,
        default=TYPE_DISCORD,        
        help_text='type of this webhook'
    )
    url = models.CharField(
        max_length=255,      
        unique=True,
        help_text='URL of this webhook, e.g. https://discordapp.com/api/webhooks/123456/abcdef'
    )
    notes = models.TextField(
        null=True, 
        default=None, 
        blank=True,        
        help_text='you can add notes about this webhook here if you want'
    )
    notification_types = MultiSelectField(
        choices=NTYPE_CHOICES,
        default=get_default_notification_types,        
        help_text='only notifications which selected types are sent to this webhook'
    )    
    is_active = models.BooleanField(        
        default=True,
        help_text='whether notifications are currently sent to this webhook'
    )
    is_default = models.BooleanField(        
        default=False,
        help_text='whether newly added owners have this automatically webhook preset'
    )
        
    def __str__(self):
        return self.name

    def send_test_notification(self) -> dict:
        """Sends a test notification to this webhook and returns send report"""
        hook = dhooks_lite.Webhook(
            self.url            
        )
        send_report = hook.execute(
            'This is a test notification from **{}**.\n'.format(__title__)
            + 'The webhook appears to be correctly configured.', 
            wait_for_response=True
        )
        send_report_json = json.dumps(send_report, indent=4, sort_keys=True)
        return send_report_json


class Owner(models.Model):
    """A corporation that owns structures"""

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
        (ERROR_NO_CHARACTER, 'No character set for fetching data from ESI'),
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
        blank=True,
        help_text='character used for syncing structures'
    )    
    structures_last_sync = models.DateTimeField(
        null=True, 
        default=None, 
        blank=True,
        help_text='when the last sync happened'
    )
    structures_last_error = models.IntegerField(
        choices=ERRORS_LIST, 
        default=ERROR_NONE,
        help_text='error that occurred at the last sync atttempt (if any)'
    )
    notifications_last_sync = models.DateTimeField(
        null=True, 
        default=None, 
        blank=True,
        help_text='when the last sync happened'
    )
    notifications_last_error = models.IntegerField(
        choices=ERRORS_LIST, 
        default=ERROR_NONE,
        help_text='error that occurred at the last sync atttempt (if any)'
    )
    forwarding_last_sync = models.DateTimeField(
        null=True, 
        default=None, 
        blank=True,
        help_text='when the last sync happened'
    )
    forwarding_last_error = models.IntegerField(
        choices=ERRORS_LIST, 
        default=ERROR_NONE,
        help_text='error that occurred at the last sync atttempt (if any)'
    )
    webhooks = models.ManyToManyField(
        Webhook,         
        default=None, 
        blank=True,
        help_text='notifications are sent to these webhooks. '
    )
    is_alliance_main =  models.BooleanField(        
        default=False,
        help_text='whether alliance wide notifications ' \
            + '(e.g. sov notifications) are forwarded for this owner'
    )
    is_included_in_service_status =  models.BooleanField(        
        default=True,
        help_text='whether the sync status of this owner is included in '\
            + 'the overall status of this services'
    )

    def __str__(self) -> str:
        return str(self.corporation.corporation_name)

    def is_structure_sync_ok(self) -> bool:
        """returns true if they have been no errors 
        and last syncing occurred within alloted time
        """
        return self.structures_last_error == self.ERROR_NONE \
            and self.structures_last_sync \
            and self.structures_last_sync > (now() - datetime.timedelta(
                minutes=STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES
            ))

    def is_notification_sync_ok(self) -> bool:
        """returns true if they have been no errors 
        and last syncing occurred within alloted time
        """
        return self.notifications_last_error == self.ERROR_NONE \
            and self.notifications_last_sync \
            and self.notifications_last_sync > (now() - datetime.timedelta(
                    minutes=STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES
            ))

    def is_forwarding_sync_ok(self) -> bool:
        """returns true if they have been no errors 
        and last syncing occurred within alloted time
        """
        return self.forwarding_last_error == self.ERROR_NONE \
            and self.forwarding_last_sync \
            and self.forwarding_last_sync > (now() - datetime.timedelta(
                minutes=STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES
            ))

    def is_all_syncs_ok(self) -> bool:
        """returns true if they have been no errors 
        and last syncing occurred within alloted time for all sync categories
        """
        return self.is_structure_sync_ok() \
            and self.is_notification_sync_ok() \
            and self.is_forwarding_sync_ok()
    
    @classmethod
    def get_esi_scopes(cls) -> list:
        return [
            'esi-corporations.read_structures.v1',
            'esi-universe.read_structures.v1',
            'esi-characters.read_notifications.v1'
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


class EveMoon(models.Model):
    id = models.IntegerField(
        primary_key=True,
        validators=[MinValueValidator(0)],
        help_text='Eve Online item ID'
    )
    name = models.CharField(max_length=100)
    position_x = models.FloatField(        
        null=True, 
        default=None, 
        blank=True,
        help_text='x position of the structure in the solar system'
    )
    position_y = models.FloatField(        
        null=True, 
        default=None, 
        blank=True,
        help_text='y position of the structure in the solar system'
    )
    position_z = models.FloatField(        
        null=True, 
        default=None, 
        blank=True,
        help_text='z position of the structure in the solar system'
    )
    eve_solar_system = models.ForeignKey(
        EveSolarSystem, 
        on_delete=models.CASCADE
    )

    objects = EveMoonManager()

    def __str__(self):
        return self.name


class EveGroup(models.Model):
    """group in Eve Online"""
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

    def icon_url(self, size=64):
        return evelinks.get_type_image_url(
            self.id,
            size
        )

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
    eve_solar_system = models.ForeignKey(
        EveSolarSystem, 
        on_delete=models.CASCADE
    )
    position_x = models.FloatField(        
        null=True, 
        default=None, 
        blank=True,
        help_text='x position of the structure in the solar system'
    )
    position_y = models.FloatField(        
        null=True, 
        default=None, 
        blank=True,
        help_text='y position of the structure in the solar system'
    )
    position_z = models.FloatField(        
        null=True, 
        default=None, 
        blank=True,
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
    reinforce_hour = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        null=True, 
        default=None, 
        blank=True,
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
        default=STATE_UNKNOWN,
        blank=True,
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
        null=True, 
        default=None, 
        blank=True,
        help_text='date this structure was last updated from the EVE server'
    )

    objects = StructureManager()

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

    @classmethod
    def get_matching_state(cls, state_name) -> int:
        """returns matching state for given state name"""
        match = cls.STATE_OFFLINE
        for x in cls.STATE_CHOICES:
            if state_name == x[1]:
                match = x
                break
        
        return match[0]


class EveEntity(models.Model):
    """An EVE entity like a character or an alliance"""
    
    CATEGORY_CHARACTER = 1
    CATEGORY_CORPORATION = 2
    CATEGORY_ALLIANCE = 3
    CATEGORY_FACTION = 4
    CATEGORY_OTHER = 5

    CATEGORY_CHOICES = [
        (CATEGORY_CHARACTER, 'character'),
        (CATEGORY_CORPORATION, 'corporation'),
        (CATEGORY_ALLIANCE, 'alliance'),
        (CATEGORY_FACTION, 'faction'),
        (CATEGORY_OTHER, 'other'),
    ]
    
    id = models.IntegerField(
        primary_key=True, 
        validators=[MinValueValidator(0)]
    )
    category = models.IntegerField(
        choices=CATEGORY_CHOICES
    )
    name = models.CharField(
        max_length=255,
        null=True, 
        default=None, 
        blank=True
    )

    objects = EveEntityManager()

    def __str__(self):
        return str(self.name)

    @classmethod
    def get_matching_entity_type(cls, type_name) -> int:
        """returns matching entity type for given state name"""
        match = None
        for x in cls.CATEGORY_CHOICES:
            if type_name == x[1]:
                match = x
                break
        if not match:
            raise ValueError('Invalid entity type: {}'.format(type_name))
        else:
            return match[0]


class Notification(models.Model):
    """An EVE Online notification about structures"""
    
    EMBED_COLOR_INFO = 0x5bc0de
    EMBED_COLOR_SUCCESS = 0x5cb85c
    EMBED_COLOR_WARNING = 0xf0ad4e
    EMBED_COLOR_DANGER = 0xd9534f
    
    notification_id = models.BigIntegerField(        
        validators=[MinValueValidator(0)]
    )
    owner = models.ForeignKey(
        Owner, 
        on_delete=models.CASCADE,
        help_text='Corporation that received this notification'
    )
    sender = models.ForeignKey(EveEntity, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    notification_type = models.IntegerField(
        choices=NTYPE_CHOICES
    )
    text = models.TextField(        
        null=True, 
        default=None, 
        blank=True
    )
    is_read = models.BooleanField(
        null=True, 
        default=None, 
        blank=True
    )
    is_sent = models.BooleanField(
        default=False,
        blank=True,
        help_text='True when this notification has been forwarded to Discord'
    )
    is_timer_added = models.BooleanField(
        null=True, 
        default=None, 
        blank=True,
        help_text='True when a timer has been added for this notification'
    )
    last_updated = models.DateTimeField(
        help_text='Date when this notification has last been updated from ESI'
    )
    created = models.DateTimeField(
        null=True, 
        default=None, 
        blank=True,
        help_text='Date when this notification was first received from ESI'
    )

    class Meta:
        unique_together = (('notification_id', 'owner'),)

    def __str__(self):
        return str(self.notification_id)
    
    def _ldap_datetime_2_dt(self, ldap_dt: int) -> datetime:
        """converts ldap time to datatime"""    
        return pytz.utc.localize(datetime.datetime.utcfromtimestamp(
            (ldap_dt / 10000000) - 11644473600
        ))

    def _ldap_timedelta_2_timedelta(self, ldap_td: int) -> datetime.timedelta:
        """converts a ldap timedelta into a dt timedelta"""
        return datetime.timedelta(microseconds=ldap_td / 10)

    def _generate_embed(self, esi_client: object) -> dhooks_lite.Embed:
        """generates a Discord embed for this notification"""

        def gen_solar_system_text(solar_system: EveSolarSystem) -> str:
            text = '[{}]({}) ({})'.format(
                solar_system.name,
                evelinks.get_entity_profile_url_by_name(
                    evelinks.ESI_CATEGORY_SOLARSYSTEM,
                    solar_system.name
                ),
                solar_system.eve_constellation.eve_region.name
            )
            return text

        def gen_alliance_link(alliance_name):
            return '[{}]({})'.format(
                alliance_name,
                evelinks.get_entity_profile_url_by_name(
                    evelinks.ESI_CATEGORY_ALLIANCE,
                    alliance_name
            ))
        
        def gen_corporation_link(corporation_name):
            return '[{}]({})'.format(
                corporation_name,
                evelinks.get_entity_profile_url_by_name(
                    evelinks.ESI_CATEGORY_CORPORATION,
                    corporation_name
            ))

        def get_attacker_name(parsed_text):
            """returns the attacker name from a parsed_text"""
            if "allianceName" in parsed_text:               
                name = gen_alliance_link(parsed_text['allianceName'])
            elif "corpName" in parsed_text:
                name = gen_corporation_link(parsed_text['corpName'])
            else:
                name = "(unknown)"

            return name

        parsed_text = yaml.safe_load(self.text)
        
        if self.notification_type in [
            NTYPE_STRUCTURE_FUEL_ALERT,
            NTYPE_STRUCTURE_SERVICES_OFFLINE,
            NTYPE_STRUCTURE_WENT_LOW_POWER,
            NTYPE_STRUCTURE_WENT_HIGH_POWER,
            NTYPE_STRUCTURE_UNANCHORING,
            NTYPE_STRUCTURE_UNDER_ATTACK,
            NTYPE_STRUCTURE_LOST_SHIELD,
            NTYPE_STRUCTURE_LOST_ARMOR,
            NTYPE_STRUCTURE_DESTROYED,
            NTYPE_STRUCTURE_ONLINE
        ]:            
            structure, _ = Structure.objects.get_or_create_esi(
                parsed_text['structureID'],
                esi_client
            )
            thumbnail = dhooks_lite.Thumbnail(structure.eve_type.icon_url())

            description = 'The {} **{}** in {} '.format(
                structure.eve_type.name, 
                structure.name,
                gen_solar_system_text(structure.eve_solar_system)
            )

            if self.notification_type == NTYPE_STRUCTURE_ONLINE:
                title = 'Structure online'
                description += 'is now online.'
                color = self.EMBED_COLOR_SUCCESS

            if self.notification_type == NTYPE_STRUCTURE_FUEL_ALERT:
                title = 'Structure fuel alert'
                description += 'has less then 24hrs fuel left.'
                color = self.EMBED_COLOR_WARNING

            elif self.notification_type == NTYPE_STRUCTURE_SERVICES_OFFLINE:                
                title = 'Structure services off-line'
                description += 'has all services off-lined.'
                if structure.structureservice_set.count() > 0:
                    services_list = '\n'.join([
                        x.name 
                        for x in structure.structureservice_set.all().order_by('name')
                    ])
                    description += '\n*{}*'.format(
                        services_list
                    )
                
                color = self.EMBED_COLOR_DANGER

            elif self.notification_type == NTYPE_STRUCTURE_WENT_LOW_POWER:
                title = 'Structure low power'
                description += 'went to **low power** mode.'
                color = self.EMBED_COLOR_WARNING

            elif self.notification_type == NTYPE_STRUCTURE_WENT_HIGH_POWER:
                title = 'Structure full power'
                description += 'went to **full power** mode.'
                color = self.EMBED_COLOR_SUCCESS

            elif self.notification_type == NTYPE_STRUCTURE_UNANCHORING:
                title = 'Structure un-anchoring'            
                unanchored_at = self.timestamp \
                    + self._ldap_timedelta_2_timedelta(parsed_text['timeLeft'])
                description += 'has started un-anchoring. '\
                    + 'It will be fully un-anchored at: {}'.format(
                        unanchored_at.strftime(DATETIME_FORMAT))
                color = self.EMBED_COLOR_INFO

            elif self.notification_type == NTYPE_STRUCTURE_UNDER_ATTACK:
                title = 'Structure under attack'
                description += 'is under attack by {}.'.format(
                    get_attacker_name(parsed_text)
                )
                color = self.EMBED_COLOR_DANGER

            elif self.notification_type == NTYPE_STRUCTURE_LOST_SHIELD:
                title = 'Structure lost shield'
                timer_ends_at = self.timestamp \
                    + self._ldap_timedelta_2_timedelta(parsed_text['timeLeft'])
                description += 'has lost its shields. Armor timer end at: {}'.format(
                    timer_ends_at.strftime(DATETIME_FORMAT)
                )
                color = self.EMBED_COLOR_DANGER

            elif self.notification_type == NTYPE_STRUCTURE_LOST_ARMOR:
                title = 'Structure lost armor'
                timer_ends_at = self.timestamp \
                    + self._ldap_timedelta_2_timedelta(parsed_text['timeLeft'])
                description += 'has lost its armor. Hull timer end at: {}'.format(
                    timer_ends_at.strftime(DATETIME_FORMAT)
                )
                color = self.EMBED_COLOR_DANGER

            elif self.notification_type == NTYPE_STRUCTURE_DESTROYED:
                title = 'Structure destroyed'
                description += 'has been destroyed.'
                color = self.EMBED_COLOR_DANGER

        elif self.notification_type in [
            NTYPE_MOONMINING_AUTOMATIC_FRACTURE,
            NTYPE_MOONMINING_EXTRACTION_CANCELED,
            NTYPE_MOONMINING_EXTRACTION_FINISHED,
            NTYPE_MOONMINING_EXTRACTION_STARTED,
            NTYPE_MOONMINING_LASER_FIRED
        ]:
            structure, _ = Structure.objects.get_or_create_esi(
                parsed_text['structureID'],
                esi_client
            )
            moon, _ = EveMoon.objects.get_or_create_esi(
                parsed_text['moonID'], 
                esi_client
            )
            thumbnail = dhooks_lite.Thumbnail(structure.eve_type.icon_url())
            solar_system_link = gen_solar_system_text(
                structure.eve_solar_system
            )

            if self.notification_type == \
                NTYPE_MOONMINING_EXTRACTION_STARTED:   
                                
                started_by, _ = EveEntity.objects.get_or_create_esi(
                    parsed_text['startedBy']
                )
                ready_time = self._ldap_datetime_2_dt(parsed_text['readyTime'])
                auto_time = self._ldap_datetime_2_dt(parsed_text['autoTime'])
                title = 'Moon mining extraction started'
                description = 'A moon mining extraction has been started ' \
                    + 'for **{}** at {} in {}.\n'.format(
                        structure.name,
                        moon.name,
                        solar_system_link
                    ) + 'Extraction was started by {}.\n'.format(started_by) \
                        +  'The chunk will be ready on ' + 'location at {}, '.format(
                            ready_time.strftime(DATETIME_FORMAT)
                    ) + 'and will autofracture on {}.\n'.format(
                        auto_time.strftime(DATETIME_FORMAT)
                    )
                color = self.EMBED_COLOR_INFO

            elif self.notification_type == \
                NTYPE_MOONMINING_EXTRACTION_FINISHED:   
                
                auto_time = self._ldap_datetime_2_dt(parsed_text['autoTime'])
                title = 'Extraction finished'
                description = 'The extraction for {} at {} in {}'.format(
                        structure.name,
                        moon.name,
                        solar_system_link
                    ) + ' is finished and the chunk is ready to be shot at.\n'\
                        +  'The chunk will automatically fracture on {}'\
                            .format(auto_time.strftime(DATETIME_FORMAT)
                    )
                color = self.EMBED_COLOR_INFO


            elif self.notification_type == \
                NTYPE_MOONMINING_AUTOMATIC_FRACTURE:   
                                
                title = 'Automatic Fracture'
                description = 'The moondrill fitted to **{}** at {} in {}'.format(
                        structure.name,
                        moon.name,
                        solar_system_link
                    ) + ' has automatically been fired and the moon ' \
                        + 'products are ready to be harvested.\n'
                color = self.EMBED_COLOR_SUCCESS


            elif self.notification_type == \
                NTYPE_MOONMINING_EXTRACTION_CANCELED:   
                
                if parsed_text['cancelledBy']:
                    cancelled_by, _ = EveEntity.objects.get_or_create_esi(
                        parsed_text['cancelledBy']
                    )
                else:
                    cancelled_by = '(unknown)'
                title = 'Extraction cancelled'
                description = 'An ongoing extraction for **{}** at {}'.format(
                    structure.name,
                    moon.name
                ) + ' in {} has been cancelled by {}.'.format(
                    solar_system_link,
                    cancelled_by
                )
                color = self.EMBED_COLOR_WARNING


            elif self.notification_type == \
                NTYPE_MOONMINING_LASER_FIRED:
                
                fired_by, _ = EveEntity.objects.get_or_create_esi(
                    parsed_text['firedBy']
                )
                title = 'Moondrill fired'
                description = 'The moondrill fitted to **{}** at {}'.format(
                    structure.name,
                    moon.name
                ) + ' in {} has been fired by {} '.format(
                    solar_system_link,
                    fired_by
                ) + 'and the moon products are ready to be harvested.'
                color = self.EMBED_COLOR_SUCCESS

        else:
            if self.notification_type == NTYPE_OWNERSHIP_TRANSFERRED:                
                structure_type, _ = EveType.objects.get_or_create_esi(
                    parsed_text['structureTypeID'],
                    esi_client
                )
                thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())
                solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                    parsed_text['solarSystemID'],
                    esi_client
                )
                description = 'The {} **{}** in {} '.format(
                    structure_type.name,
                    parsed_text['structureName'],
                    gen_solar_system_text(solar_system)
                )
                from_corporation, _ = \
                    EveEntity.objects.get_or_create_esi(
                        parsed_text['oldOwnerCorpID'],
                        esi_client
                    )
                to_corporation, _ = \
                    EveEntity.objects.get_or_create_esi(
                        parsed_text['newOwnerCorpID'],
                        esi_client
                    )
                character, _ = \
                    EveEntity.objects.get_or_create_esi(
                        parsed_text['charID'],
                        esi_client
                    )
                description += 'has been transferred from {} to {} by {}.'\
                    .format(
                        gen_corporation_link(from_corporation.name),
                        gen_corporation_link(to_corporation.name),
                        character.name
                )
                title = 'Ownership transferred'
                color = self.EMBED_COLOR_INFO                
            
            elif self.notification_type == NTYPE_STRUCTURE_ANCHORING:                
                structure_type, _ = EveType.objects.get_or_create_esi(
                    parsed_text['structureTypeID'],
                    esi_client
                )
                thumbnail = dhooks_lite.Thumbnail(structure_type.icon_url())
                solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                    parsed_text['solarsystemID'],
                    esi_client
                )
                description = '**{}** has started anchoring in {}. '.format(
                    structure_type.name,
                    gen_solar_system_text(solar_system)
                )                
                unanchored_at = self.timestamp \
                    + self._ldap_timedelta_2_timedelta(parsed_text['timeLeft'])
                description += 'The anchoring timer ends at: {}'.format(
                    unanchored_at.strftime(DATETIME_FORMAT)
                )
                
                title = 'Structure anchoring'
                color = self.EMBED_COLOR_INFO

            else:
                raise NotImplementedError('type: {}'.format(
                    self.notification_type
                ))
                
        if STRUCTURES_DEVELOPER_MODE:
            footer = dhooks_lite.Footer(self.notification_id)
        else:
            footer = None
        
        return dhooks_lite.Embed(
            title=title,
            description=description,
            color=color,
            thumbnail=thumbnail,
            timestamp=self.timestamp,
            footer=footer
        )


    def send_to_webhook(self, webhook: Webhook, esi_client: object = None):
        """sends this notification to the configured webhook"""        
    
        add_prefix = make_logger_prefix(
            'notification:{}'.format(self.notification_id)
        )            
        username = '{} Notification'.format(
            self.owner.corporation.corporation_ticker
        )
        avatar_url = self.owner.corporation.logo_url()

        hook = dhooks_lite.Webhook(
            webhook.url, 
            username=username,
            avatar_url=avatar_url
        )                        
        with transaction.atomic():
            logger.info(add_prefix(
                'Trying to sent to webhook: {}'.format(
                    webhook
            )))                
            
            desc = self.text
            try:
                embed = self._generate_embed(esi_client)         
            except Exception as ex:
                logger.warning(add_prefix(
                    'Failed to generate embed: {}'.format(ex)
                ))
                raise ex
            else:                                                
                if embed.color == self.EMBED_COLOR_DANGER:
                    content = '@everyone'
                elif embed.color == self.EMBED_COLOR_WARNING:
                    content = '@here'
                else:
                    content = None
                hook.execute(
                    content=content, 
                    embeds=[embed], 
                    wait_for_response=True
                )
                self.is_sent = True
                self.save()

    def add_to_timerboard(self, esi_client: object = None) -> bool:
        """add a timer for this notification if the type is right
        returns True when timer was added, else False
        """
        success = False
        if self.notification_type in NTYPE_RELEVANT_FOR_TIMERBOARD \
            and 'allianceauth.timerboard' in settings.INSTALLED_APPS:
            
            from allianceauth.timerboard.models import Timer
                        
            parsed_text = yaml.safe_load(self.text)
            
            try:
                if self.notification_type in [
                    NTYPE_STRUCTURE_LOST_ARMOR,
                    NTYPE_STRUCTURE_LOST_SHIELD,
                ]:
                    structure_obj, _ = Structure.objects.get_or_create_esi(
                        parsed_text['structureID'],
                        esi_client
                    )                      
                    system = structure_obj.eve_solar_system.name
                    structure = structure_obj.eve_type.name
                    objective = 'Friendly'
                    eve_time = timer_ends_at = self.timestamp \
                        + self._ldap_timedelta_2_timedelta(parsed_text['timeLeft'])            
                    eve_corp = self.owner.corporation            

                    if self.notification_type == NTYPE_STRUCTURE_LOST_SHIELD:
                        details = "Armor timer"

                    elif self.notification_type == NTYPE_STRUCTURE_LOST_ARMOR:
                        details = "Final timer"
                
                elif self.notification_type == NTYPE_STRUCTURE_ANCHORING:                
                    structure_type, _ = EveType.objects.get_or_create_esi(
                        parsed_text['structureTypeID'],
                        esi_client
                    )                
                    solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                        parsed_text['solarsystemID'],
                        esi_client
                    )                                
                    system =  solar_system.name
                    structure = structure_type.name
                    objective = 'Friendly'
                    eve_time = timer_ends_at = self.timestamp \
                        + self._ldap_timedelta_2_timedelta(parsed_text['timeLeft'])            
                    eve_corp = self.owner.corporation
                    details = "Anchor timer"

                else:
                    raise NotImplementedError()

                with transaction.atomic():                  
                    Timer.objects.create(
                        details=details,
                        system=system,
                        structure=structure,
                        objective=objective,
                        eve_time=eve_time,                            
                        eve_corp=eve_corp,     
                    )
                    logger.info('{}: added timer from notification'.format(
                        self.notification_id
                    ))
                  
                    self.is_timer_added = True
                    self.save()
                    success = True
                    
            except Exception as ex:
                logger.exception('{}: Failed to add timer from notification: {}'\
                    .format(
                        self.notification_id,
                        ex
                    ))
        
        return success


    @classmethod
    def get_matching_notification_type(cls, type_name) -> int:
        """returns matching notification type for given name or None"""
        match = None
        for x in NTYPE_CHOICES:
            if type_name == x[1]:
                match = x
                break
        if match:
            return match[0]
        else:
            return None

