import logging
from time import sleep
import yaml
import datetime
import json
import urllib

import pytz
import dhooks_lite
from multiselectfield import MultiSelectField

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.html import escape, format_html
from django.utils.timezone import now

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCorporationInfo
from esi.clients import esi_client_factory

from .app_settings import (
    STRUCTURES_DEVELOPER_MODE,
    STRUCTURES_FEATURE_CUSTOMS_OFFICES,
    STRUCTURES_FEATURE_STARBASES,
    STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES,
    STRUCTURES_NOTIFICATION_MAX_RETRIES,
    STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES,
    STRUCTURES_NOTIFICATION_WAIT_SEC,
    STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED,
    STRUCTURES_REPORT_NPC_ATTACKS,
    STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES,
    STRUCTURES_TIMERS_ARE_CORP_RESTRICTED,
)
from . import evelinks, __title__
from .managers import (
    EveCategoryManager,
    EveEntityManager,
    EveGroupManager,
    EveMoonManager,
    EvePlanetManager,
    EveRegionManager,
    EveConstellationManager,
    EveSolarSystemManager,
    EveTypeManager,
    StructureManager
)
from .utils import \
    LoggerAddTag, DATETIME_FORMAT, make_logger_prefix, get_swagger_spec_path

if 'allianceauth.timerboard' in settings.INSTALLED_APPS:
    from allianceauth.timerboard.models import Timer


logger = LoggerAddTag(logging.getLogger(__name__), __package__)

# Notification types
NTYPE_MOONS_AUTOMATIC_FRACTURE = 401
NTYPE_MOONS_EXTRACTION_CANCELED = 402
NTYPE_MOONS_EXTRACTION_FINISHED = 403
NTYPE_MOONS_EXTRACTION_STARTED = 404
NTYPE_MOONS_LASER_FIRED = 405

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

NTYPE_ORBITAL_ATTACKED = 601
NTYPE_ORBITAL_REINFORCED = 602

NTYPE_TOWER_ALERT_MSG = 701
NTYPE_TOWER_RESOURCE_ALERT_MSG = 702

NTYPE_SOV_ENTOSIS_CAPTURE_STARTED = 801
NTYPE_SOV_COMMAND_NODE_EVENT_STARTED = 802
NTYPE_SOV_ALL_CLAIM_ACQUIRED_MSG = 803
NTYPE_SOV_STRUCTURE_REINFORCED = 804
NTYPE_SOV_STRUCTURE_DESTROYED = 805

NTYPE_CHOICES = [
    # moon mining
    (NTYPE_MOONS_AUTOMATIC_FRACTURE, 'MoonminingAutomaticFracture'),
    (NTYPE_MOONS_EXTRACTION_CANCELED, 'MoonminingExtractionCancelled'),
    (NTYPE_MOONS_EXTRACTION_FINISHED, 'MoonminingExtractionFinished'),
    (NTYPE_MOONS_EXTRACTION_STARTED, 'MoonminingExtractionStarted'),
    (NTYPE_MOONS_LASER_FIRED, 'MoonminingLaserFired'),

    # upwell structures general
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

    # custom offices only
    (NTYPE_ORBITAL_ATTACKED, 'OrbitalAttacked'),
    (NTYPE_ORBITAL_REINFORCED, 'OrbitalReinforced'),

    # starbases only
    (NTYPE_TOWER_ALERT_MSG, 'TowerAlertMsg'),
    (NTYPE_TOWER_RESOURCE_ALERT_MSG, 'TowerResourceAlertMsg'),

    # sov
    (NTYPE_SOV_ENTOSIS_CAPTURE_STARTED, 'EntosisCaptureStarted'),
    (NTYPE_SOV_COMMAND_NODE_EVENT_STARTED, 'SovCommandNodeEventStarted'),
    (NTYPE_SOV_ALL_CLAIM_ACQUIRED_MSG, 'SovAllClaimAquiredMsg'),
    (NTYPE_SOV_STRUCTURE_REINFORCED, 'SovStructureReinforced'),
    (NTYPE_SOV_STRUCTURE_DESTROYED, 'SovStructureDestroyed'),
]

_NTYPE_RELEVANT_FOR_TIMERBOARD = [
    NTYPE_STRUCTURE_LOST_SHIELD,
    NTYPE_STRUCTURE_LOST_ARMOR,
    NTYPE_STRUCTURE_ANCHORING,
    NTYPE_ORBITAL_REINFORCED,
    NTYPE_MOONS_EXTRACTION_STARTED,
    NTYPE_MOONS_EXTRACTION_CANCELED,
    NTYPE_SOV_STRUCTURE_REINFORCED
]

NTYPE_FOR_ALLIANCE_LEVEL = [
    NTYPE_SOV_ENTOSIS_CAPTURE_STARTED,
    NTYPE_SOV_COMMAND_NODE_EVENT_STARTED,
    NTYPE_SOV_ALL_CLAIM_ACQUIRED_MSG,
    NTYPE_SOV_STRUCTURE_REINFORCED,
    NTYPE_SOV_STRUCTURE_DESTROYED
]


def get_default_notification_types():
    """generates a set of all existing notification types as default"""
    return tuple(sorted([str(x[0]) for x in NTYPE_CHOICES]))


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
        help_text='URL of this webhook, e.g. '
        'https://discordapp.com/api/webhooks/123456/abcdef'
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
        help_text='only notifications which selected types '
        'are sent to this webhook'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='whether notifications are currently sent to this webhook'
    )
    is_default = models.BooleanField(
        default=False,
        help_text='whether newly added owners have this automatically '
        'webhook preset'
    )

    def __str__(self):
        return self.name

    def send_test_notification(self) -> str:
        """Sends a test notification to this webhook and returns send report"""
        hook = dhooks_lite.Webhook(
            self.url
        )
        response = hook.execute(
            'This is a test notification from **{}**.\n'.format(__title__)
            + 'The webhook appears to be correctly configured.',
            wait_for_response=True
        )
        if response.status_ok:
            send_report_json = json.dumps(
                response.content,
                indent=4,
                sort_keys=True
            )
        else:
            send_report_json = 'HTTP status code {}'.format(
                response.status_code
            )
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
        (
            ERROR_NONE,
            'No error'
        ),
        (
            ERROR_TOKEN_INVALID,
            'Invalid token'
        ),
        (
            ERROR_TOKEN_EXPIRED,
            'Expired token'
        ),
        (
            ERROR_INSUFFICIENT_PERMISSIONS,
            'Insufficient permissions'
        ),
        (
            ERROR_NO_CHARACTER,
            'No character set for fetching data from ESI'
        ),
        (
            ERROR_ESI_UNAVAILABLE,
            'ESI API is currently unavailable'
        ),
        (
            ERROR_OPERATION_MODE_MISMATCH,
            'Operaton mode does not match with current setting'
        ),
        (
            ERROR_UNKNOWN,
            'Unknown error'
        ),
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
    is_active = models.BooleanField(
        default=True,
        help_text='whether this owner is currently included '
        'in the sync process'
    )
    is_alliance_main = models.BooleanField(
        default=False,
        help_text='whether alliance wide notifications '
        'are forwarded for this owner (e.g. sov notifications)'
    )
    is_included_in_service_status = models.BooleanField(
        default=True,
        help_text='whether the sync status of this owner is included in '
        'the overall status of this services'
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
    def to_friendly_error_message(cls, error) -> str:
        msg = [(x, y) for x, y in cls.ERRORS_LIST if x == error]
        return msg[0][1] if len(msg) > 0 else 'Undefined error'

    @classmethod
    def get_esi_scopes(cls) -> list:
        scopes = [
            'esi-corporations.read_structures.v1',
            'esi-universe.read_structures.v1',
            'esi-characters.read_notifications.v1',
        ]
        if STRUCTURES_FEATURE_CUSTOMS_OFFICES:
            scopes += [
                'esi-planets.read_customs_offices.v1',
                'esi-assets.read_corporation_assets.v1'
            ]
        if STRUCTURES_FEATURE_STARBASES:
            scopes += [
                'esi-corporations.read_starbases.v1'
            ]
        return scopes


class EveCategory(models.Model):
    """group in Eve Online"""

    # named category IDs
    EVE_CATEGORY_ID_ORBITAL = 46
    EVE_CATEGORY_ID_STARBASE = 23
    EVE_CATEGORY_ID_STRUCTURE = 65

    id = models.IntegerField(
        primary_key=True,
        validators=[MinValueValidator(0)],
        help_text='Eve Online category ID'
    )
    name = models.CharField(max_length=100)

    objects = EveCategoryManager()

    @property
    def is_starbase(self):
        return self.id == self.EVE_CATEGORY_ID_STARBASE

    @property
    def is_upwell_structure(self):
        return self.id == self.EVE_CATEGORY_ID_STRUCTURE

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
    eve_category = models.ForeignKey(
        EveCategory,
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True
    )

    objects = EveGroupManager()

    def __str__(self):
        return self.name


class EveType(models.Model):
    """type in Eve Online"""

    # named type IDs
    EVE_TYPE_ID_POCO = 2233
    EVE_TYPE_ID_TCU = 32226
    EVE_TYPE_ID_IHUB = 32458

    EVE_IMAGESERVER_BASE_URL = 'https://images.evetech.net'

    id = models.IntegerField(
        primary_key=True,
        validators=[MinValueValidator(0)],
        help_text='Eve Online type ID'
    )
    name = models.CharField(max_length=100)
    eve_group = models.ForeignKey(EveGroup, on_delete=models.CASCADE)

    objects = EveTypeManager()

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

    def __str__(self):
        return self.name

    def icon_url(self, size=64):
        return self.generic_icon_url(self.id, size)


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


class EvePlanet(models.Model):
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
    eve_type = models.ForeignKey(
        EveType,
        on_delete=models.CASCADE
    )

    objects = EvePlanetManager()

    def __str__(self):
        return self.name


class StructureTag(models.Model):
    """tag for organizing structures"""

    STYLE_CHOICES = [
        ('default', 'grey'),
        ('primary', 'dark blue'),
        ('success', 'green'),
        ('info', 'light blue'),
        ('warning', 'yellow'),
        ('danger', 'red'),
    ]

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text='name of the tag - must be unique'
    )
    description = models.TextField(
        null=True,
        default=None,
        blank=True,
        help_text='description for this tag'
    )
    style = models.CharField(
        max_length=16,
        choices=STYLE_CHOICES,
        default='default',
        blank=True,
        help_text='color style of tag'
    )
    is_default = models.BooleanField(
        default=False,
        help_text='if true this tag will automatically added to new structures'
    )

    def __str__(self) -> str:
        return self.name

    @property
    def html(self) -> str:
        return format_html('<span class="label label-{}">{}</span>'.format(
            self.style,
            escape(self.name)
        ))

    @classmethod
    def sorted(cls, tags: list, reverse: bool = False) -> list:
        """returns a sorted copy of the provided list of tags"""
        return sorted(tags, key=lambda x: x.name.lower(), reverse=reverse)


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

    STATE_POS_OFFLINE = 21
    STATE_POS_ONLINE = 22
    STATE_POS_ONLINING = 23
    STATE_POS_REINFORCED = 24
    STATE_POS_UNANCHORING = 25

    STATE_CHOICES = [
        # states Upwell structures
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

        # starbases
        (STATE_POS_OFFLINE, 'offline'),
        (STATE_POS_ONLINE, 'online'),
        (STATE_POS_ONLINING, 'onlining'),
        (STATE_POS_REINFORCED, 'reinforced'),
        (STATE_POS_UNANCHORING, 'unanchoring '),

        # other
        (STATE_NA, 'N/A'),
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
    eve_planet = models.ForeignKey(
        EvePlanet,
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True,
        help_text='Planet next to this structure - if any'
    )
    eve_moon = models.ForeignKey(
        EveMoon,
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True,
        help_text='Moon next to this structure - if any'
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
        help_text='The requested change to reinforce_hour that will take '
        'effect at the time shown by next_reinforce_apply'
    )
    next_reinforce_weekday = models.IntegerField(
        null=True,
        default=None,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text='The date and time when the structure’s newly requested '
        'reinforcement times (e.g. next_reinforce_hour and next_reinforce_day)'
        ' will take effect'
    )
    next_reinforce_apply = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text='The requested change to reinforce_weekday that will take '
        'effect at the time shown by next_reinforce_apply'
    )
    reinforce_hour = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        null=True,
        default=None,
        blank=True,
        help_text='The hour of day that determines the four hour window '
        'when the structure will randomly exit its reinforcement periods '
        'and become vulnerable to attack against its armor and/or hull. '
        'The structure will become vulnerable at a random time that '
        'is +/- 2 hours centered on the value of this property'
    )
    reinforce_weekday = models.IntegerField(
        null=True,
        default=None,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text='The day of the week when the structure exits its '
        'final reinforcement period and becomes vulnerable to attack '
        'against its hull. Monday is 0 and Sunday is 6'
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
    tags = models.ManyToManyField(
        StructureTag,
        default=None,
        blank=True,
        help_text='list of tags for this structure'
    )

    objects = StructureManager()

    @property
    def state_str(self):
        msg = [(x, y) for x, y in self.STATE_CHOICES if x == self.state]
        return msg[0][1].replace('_', ' ') if len(msg) > 0 else 'undefined'

    @property
    def is_low_power(self):
        if self.eve_type.is_poco:
            return False
        else:
            return not self.fuel_expires

    @property
    def is_reinforced(self):
        return self.state in [
            self.STATE_ARMOR_REINFORCE,
            self.STATE_HULL_REINFORCE,
            self.STATE_ANCHOR_VULNERABLE,
            self.STATE_HULL_VULNERABLE
        ]

    def __str__(self):
        return '{} - {}'.format(self.eve_solar_system, self.name)

    @classmethod
    def get_matching_state(cls, state_name) -> int:
        """returns matching state for given state name for Upwell structures"""
        match = [cls.STATE_UNKNOWN]
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
        return '{} - {}'.format(str(self.structure), self.name)

    @classmethod
    def get_matching_state(cls, state_name) -> int:
        """returns matching state for given state name"""
        match = [cls.STATE_OFFLINE]
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

    @property
    def esi_category_name(self):
        return self.get_matching_entity_category(self.category)

    def profile_url(self) -> str:
        """returns link to website with profile info about this entity"""
        if self.category == self.CATEGORY_CORPORATION:
            return evelinks.get_entity_profile_url_by_name(
                evelinks.ESI_CATEGORY_CORPORATION,
                self.name
            )
        elif self.category == self.CATEGORY_ALLIANCE:
            return evelinks.get_entity_profile_url_by_name(
                evelinks.ESI_CATEGORY_ALLIANCE,
                self.name
            )
        else:
            return ''

    @classmethod
    def get_matching_entity_category(cls, type_name) -> int:
        """returns category for given ESI name"""
        match = None
        for x in cls.CATEGORY_CHOICES:
            if type_name == x[1]:
                match = x
                break
        if match:
            return match[0]
        else:
            return cls.CATEGORY_OTHER


class Notification(models.Model):
    """An EVE Online notification about structures"""

    # embed colors
    EMBED_COLOR_INFO = 0x5bc0de
    EMBED_COLOR_SUCCESS = 0x5cb85c
    EMBED_COLOR_WARNING = 0xf0ad4e
    EMBED_COLOR_DANGER = 0xd9534f

    HTTP_CODE_TOO_MANY_REQUESTS = 429

    # event type structure map
    MAP_CAMPAIGN_EVENT_2_TYPE_ID = {
        1: EveType.EVE_TYPE_ID_TCU,
        2: EveType.EVE_TYPE_ID_IHUB
    }

    MAP_TYPE_ID_2_TIMER_STRUCTURE_NAME = {
        2233: 'POCO',
        32226: 'TCU',
        32458: 'I-HUB'
    }

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
    notification_type = models.IntegerField(choices=NTYPE_CHOICES)
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

    @property
    def is_alliance_level(self):
        """ whether this is an alliance level notification"""
        return self.notification_type in NTYPE_FOR_ALLIANCE_LEVEL

    @classmethod
    def _ldap_datetime_2_dt(cls, ldap_dt: int) -> datetime:
        """converts ldap time to datatime"""
        return pytz.utc.localize(datetime.datetime.utcfromtimestamp(
            (ldap_dt / 10000000) - 11644473600
        ))

    @classmethod
    def _ldap_timedelta_2_timedelta(cls, ldap_td: int) -> datetime.timedelta:
        """converts a ldap timedelta into a dt timedelta"""
        return datetime.timedelta(microseconds=ldap_td / 10)

    def __str__(self):
        return str(self.notification_id)

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
                )
            )

        def gen_corporation_link(corporation_name):
            return '[{}]({})'.format(
                corporation_name,
                evelinks.get_entity_profile_url_by_name(
                    evelinks.ESI_CATEGORY_CORPORATION,
                    corporation_name
                )
            )

        def get_attacker_link(parsed_text):
            """returns the attacker link from a parsed_text
            For Upwell structures only
            """
            if "allianceName" in parsed_text:
                name = gen_alliance_link(parsed_text['allianceName'])
            elif "corpName" in parsed_text:
                name = gen_corporation_link(parsed_text['corpName'])
            else:
                name = "(unknown)"

            return name

        def get_aggressor_link(parsed_text: dict, esi_client: object) -> str:
            """returns the aggressor link from a parsed_text
            for POS and POCOs only
            """
            if 'aggressorAllianceID' in parsed_text:
                key = 'aggressorAllianceID'
            elif 'aggressorCorpID' in parsed_text:
                key = 'aggressorCorpID'
            elif 'aggressorID' in parsed_text:
                key = 'aggressorID'
            else:
                return '(Unknown aggressor)'

            entity, _ = EveEntity.objects.get_or_create_esi(
                parsed_text[key],
                esi_client
            )
            return '[{}]({})'.format(entity.name, entity.profile_url())

        def get_type_id_from_event_type(event_type: int) -> int:
            if event_type in self.MAP_CAMPAIGN_EVENT_2_TYPE_ID:
                return self.MAP_CAMPAIGN_EVENT_2_TYPE_ID[event_type]
            else:
                return None

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
                    qs = structure.structureservice_set.all().order_by('name')
                    services_list = '\n'.join([x.name for x in qs])
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
                    get_attacker_link(parsed_text)
                )
                color = self.EMBED_COLOR_DANGER

            elif self.notification_type == NTYPE_STRUCTURE_LOST_SHIELD:
                title = 'Structure lost shield'
                timer_ends_at = self.timestamp \
                    + self._ldap_timedelta_2_timedelta(parsed_text['timeLeft'])
                description += 'has lost its shields. ' + \
                    'Armor timer end at: {}'.format(
                        timer_ends_at.strftime(DATETIME_FORMAT)
                    )
                color = self.EMBED_COLOR_DANGER

            elif self.notification_type == NTYPE_STRUCTURE_LOST_ARMOR:
                title = 'Structure lost armor'
                timer_ends_at = self.timestamp \
                    + self._ldap_timedelta_2_timedelta(parsed_text['timeLeft'])
                description += 'has lost its armor. ' + \
                    'Hull timer end at: {}'.format(
                        timer_ends_at.strftime(DATETIME_FORMAT)
                    )
                color = self.EMBED_COLOR_DANGER

            elif self.notification_type == NTYPE_STRUCTURE_DESTROYED:
                title = 'Structure destroyed'
                description += 'has been destroyed.'
                color = self.EMBED_COLOR_DANGER

        elif self.notification_type in [
            NTYPE_MOONS_AUTOMATIC_FRACTURE,
            NTYPE_MOONS_EXTRACTION_CANCELED,
            NTYPE_MOONS_EXTRACTION_FINISHED,
            NTYPE_MOONS_EXTRACTION_STARTED,
            NTYPE_MOONS_LASER_FIRED
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

            if self.notification_type == NTYPE_MOONS_EXTRACTION_STARTED:
                started_by, _ = EveEntity.objects.get_or_create_esi(
                    parsed_text['startedBy']
                )
                ready_time = self._ldap_datetime_2_dt(parsed_text['readyTime'])
                auto_time = self._ldap_datetime_2_dt(parsed_text['autoTime'])
                title = 'Moon mining extraction started'
                description = (
                    'A moon mining extraction has been started '
                    'for **{}** at {} in {}. Extraction was started by {}.\n'
                    'The chunk will be ready on location at {}, '
                    'and will autofracture on {}.\n'.format(
                        structure.name,
                        moon.name,
                        solar_system_link,
                        started_by,
                        ready_time.strftime(DATETIME_FORMAT),
                        auto_time.strftime(DATETIME_FORMAT)
                    )
                )
                color = self.EMBED_COLOR_INFO

            elif (
                self.notification_type == NTYPE_MOONS_EXTRACTION_FINISHED
            ):
                auto_time = self._ldap_datetime_2_dt(parsed_text['autoTime'])
                title = 'Extraction finished'
                description = (
                    'The extraction for {} at {} in {}'
                    ' is finished and the chunk is ready to be shot at.\n'
                    'The chunk will automatically fracture on {}'.format(
                        structure.name,
                        moon.name,
                        solar_system_link,
                        auto_time.strftime(DATETIME_FORMAT)
                    )
                )
                color = self.EMBED_COLOR_INFO

            elif self.notification_type == NTYPE_MOONS_AUTOMATIC_FRACTURE:
                title = 'Automatic Fracture'
                description = (
                    'The moondrill fitted to **{}** at {} in {} '
                    'has automatically been fired and the moon '
                    'products are ready to be harvested.\n'.format(
                        structure.name,
                        moon.name,
                        solar_system_link
                    )
                )
                color = self.EMBED_COLOR_SUCCESS

            elif (
                self.notification_type == NTYPE_MOONS_EXTRACTION_CANCELED
            ):
                if parsed_text['cancelledBy']:
                    cancelled_by, _ = EveEntity.objects.get_or_create_esi(
                        parsed_text['cancelledBy']
                    )
                else:
                    cancelled_by = '(unknown)'
                title = 'Extraction cancelled'
                description = (
                    'An ongoing extraction for **{}** at {} '
                    'in {} has been cancelled by {}.'.format(
                        structure.name,
                        moon.name,
                        solar_system_link,
                        cancelled_by
                    )
                )
                color = self.EMBED_COLOR_WARNING

            elif self.notification_type == NTYPE_MOONS_LASER_FIRED:
                fired_by, _ = EveEntity.objects.get_or_create_esi(
                    parsed_text['firedBy']
                )
                title = 'Moondrill fired'
                description = (
                    'The moondrill fitted to **{}** at {} in {} '
                    'has been fired by {} and the moon products are '
                    'ready to be harvested.'.format(
                        structure.name,
                        moon.name,
                        solar_system_link,
                        fired_by
                    )
                )
                color = self.EMBED_COLOR_SUCCESS

        elif self.notification_type in [
            NTYPE_ORBITAL_ATTACKED,
            NTYPE_ORBITAL_REINFORCED,
        ]:
            if not esi_client:
                esi_client = esi_client_factory(
                    spec_file=get_swagger_spec_path()
                )

            planet, _ = EvePlanet.objects.get_or_create_esi(
                parsed_text['planetID'],
                esi_client
            )
            structure_type, _ = EveType.objects.get_or_create_esi(
                EveType.EVE_TYPE_ID_POCO,
                esi_client
            )
            thumbnail = dhooks_lite.Thumbnail(
                structure_type.icon_url()
            )
            solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                parsed_text['solarSystemID'],
                esi_client
            )
            solar_system_link = gen_solar_system_text(
                solar_system
            )
            aggressor_link = get_aggressor_link(parsed_text, esi_client)

            if self.notification_type == NTYPE_ORBITAL_ATTACKED:
                title = 'Orbital under attack'
                description = (
                    'The {} **{}** in {} '
                    'is under attack by {}.'.format(
                        structure_type.name,
                        planet.name,
                        solar_system_link,
                        aggressor_link
                    )
                )
                color = self.EMBED_COLOR_WARNING

            elif self.notification_type == NTYPE_ORBITAL_REINFORCED:
                reinforce_exit_time = \
                    self._ldap_datetime_2_dt(parsed_text['reinforceExitTime'])
                title = 'Orbital reinforced'
                description = (
                    'The {} **{}** at {} has been '
                    'reinforced by {} and will come out at: {}.'.format(
                        structure_type.name,
                        planet.name,
                        solar_system_link,
                        aggressor_link,
                        reinforce_exit_time.strftime(DATETIME_FORMAT)
                    )
                )
                color = self.EMBED_COLOR_DANGER

        elif self.notification_type in [
            NTYPE_TOWER_ALERT_MSG,
            NTYPE_TOWER_RESOURCE_ALERT_MSG,
        ]:
            if not esi_client:
                esi_client = esi_client_factory(
                    spec_file=get_swagger_spec_path()
                )

            eve_moon, _ = EveMoon.objects.get_or_create_esi(
                parsed_text['moonID'],
                esi_client
            )
            structure_type, _ = EveType.objects.get_or_create_esi(
                parsed_text['typeID'],
                esi_client
            )
            thumbnail = dhooks_lite.Thumbnail(
                structure_type.icon_url()
            )
            solar_system_link = gen_solar_system_text(
                eve_moon.eve_solar_system
            )
            qs_structures = Structure.objects.filter(eve_moon=eve_moon)
            if qs_structures.exists():
                structure_name = qs_structures.first().name
            else:
                structure_name = structure_type.name

            if self.notification_type == NTYPE_TOWER_ALERT_MSG:
                aggressor_link = get_aggressor_link(parsed_text, esi_client)
                damage_parts = list()
                for prop in ['shield', 'armor', 'hull']:
                    prop_yaml = prop + 'Value'
                    if prop_yaml in parsed_text:
                        damage_parts.append(
                            '{}: {:.0f}%'.format(
                                prop,
                                parsed_text[prop_yaml] * 100
                            )
                        )
                damage_text = ' | '.join(damage_parts)
                title = 'Starbase under attack'
                description = (
                    'The starbase **{}** at {} in {} '
                    'is under attack by {}.\n{}'.format(
                        structure_name,
                        eve_moon.name,
                        solar_system_link,
                        aggressor_link,
                        damage_text
                    )
                )
                color = self.EMBED_COLOR_WARNING

            elif self.notification_type == NTYPE_TOWER_RESOURCE_ALERT_MSG:
                quantity = parsed_text['wants'][0]['quantity']
                title = 'Starbase low on fuel'
                description = (
                    'The starbase **{}** at {} in {} '
                    'is low on fuel. It has *{:,}* fuel blocks left.'.format(
                        structure_name,
                        eve_moon.name,
                        solar_system_link,
                        quantity
                    )
                )
                color = self.EMBED_COLOR_WARNING

        elif self.notification_type in [
            NTYPE_SOV_ENTOSIS_CAPTURE_STARTED,
            NTYPE_SOV_COMMAND_NODE_EVENT_STARTED,
            NTYPE_SOV_ALL_CLAIM_ACQUIRED_MSG,
            NTYPE_SOV_STRUCTURE_REINFORCED,
            NTYPE_SOV_STRUCTURE_DESTROYED
        ]:
            if not esi_client:
                esi_client = esi_client_factory(
                    spec_file=get_swagger_spec_path()
                )

            solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
                parsed_text['solarSystemID'],
                esi_client
            )
            solar_system_link = gen_solar_system_text(solar_system)

            if 'structureTypeID' in parsed_text:
                structure_type_id = parsed_text['structureTypeID']
            elif 'campaignEventType' in parsed_text:
                structure_type_id = get_type_id_from_event_type(
                    parsed_text['campaignEventType']
                )
            else:
                structure_type_id = EveType.EVE_TYPE_ID_TCU

            structure_type, _ = EveType.objects.get_or_create_esi(
                structure_type_id,
                esi_client
            )
            structure_type_name = structure_type.name
            thumbnail = dhooks_lite.Thumbnail(
                structure_type.icon_url()
            )
            sov_owner_link = gen_alliance_link(
                self.owner.corporation.alliance.alliance_name
            )
            if self.notification_type == NTYPE_SOV_ENTOSIS_CAPTURE_STARTED:
                title = '{} in {} is being captured'.format(
                    structure_type_name,
                    solar_system.name
                )
                description = (
                    'A capsuleer has started to influence the '
                    '**{}** in {} belonging to {} '
                    'with an Entosis Link.'.format(
                        structure_type_name,
                        solar_system_link,
                        sov_owner_link
                    )
                )
                color = self.EMBED_COLOR_WARNING

            elif (
                self.notification_type == NTYPE_SOV_COMMAND_NODE_EVENT_STARTED
            ):
                title = (
                    'Command nodes for {} in {} have begun '
                    'to decloak'.format(
                        structure_type_name,
                        solar_system.name
                    )
                )
                description = (
                    'Command nodes for **{}** in {} can now be found '
                    'throughout the {} constellation'.format(
                        structure_type_name,
                        solar_system_link,
                        solar_system.eve_constellation.name
                    )
                )
                color = self.EMBED_COLOR_WARNING

            elif self.notification_type == NTYPE_SOV_ALL_CLAIM_ACQUIRED_MSG:
                alliance, _ = EveEntity.objects.get_or_create_esi(
                    parsed_text['allianceID']
                )
                corporation, _ = EveEntity.objects.get_or_create_esi(
                    parsed_text['corpID']
                )
                title = 'DED Sovereignty claim acknowledgment: {}'.format(
                    solar_system.name
                )
                description = (
                    'DED now officially acknowledges that your '
                    'member corporation {} has claimed sovereignty on '
                    'behalf of {} in {}.'.format(
                        gen_corporation_link(corporation.name),
                        gen_alliance_link(alliance.name),
                        solar_system_link
                    )
                )
                color = self.EMBED_COLOR_SUCCESS

            elif self.notification_type == NTYPE_SOV_STRUCTURE_REINFORCED:
                timer_starts = self._ldap_datetime_2_dt(
                    parsed_text['decloakTime']
                )
                title = '{} in {} has entered reinforced mode'.format(
                    structure_type_name,
                    solar_system.name
                )
                description = (
                    'The **{}** in {} belonging to {} has been '
                    'reinforced by hostile forces and command nodes '
                    'will begin decloaking at {}'.format(
                        structure_type_name,
                        solar_system_link,
                        sov_owner_link,
                        timer_starts.strftime(DATETIME_FORMAT)
                    )
                )
                color = self.EMBED_COLOR_DANGER

            elif self.notification_type == NTYPE_SOV_STRUCTURE_DESTROYED:
                title = '{} in {} has been destroyed'.format(
                    structure_type_name,
                    solar_system.name
                )
                description = (
                    'The command nodes for **{}** in {} belonging '
                    'to {} have been destroyed by hostile forces.'.format(
                        structure_type_name,
                        solar_system_link,
                        sov_owner_link
                    )
                )
                color = self.EMBED_COLOR_DANGER

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
                description += (
                    'has been transferred from {} to {} by {}.'.format(
                        gen_corporation_link(from_corporation.name),
                        gen_corporation_link(to_corporation.name),
                        character.name
                    )
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

    def send_to_webhook(
        self,
        webhook: Webhook,
        esi_client: object = None
    ) -> bool:
        """sends this notification to the configured webhook
        returns True if successful, else False
        """
        success = False
        add_prefix = make_logger_prefix(
            'notification:{}'.format(self.notification_id)
        )
        if self.is_alliance_level:
            avatar_url = self.owner.corporation.alliance.logo_url()
            ticker = self.owner.corporation.alliance.alliance_ticker
        else:
            avatar_url = self.owner.corporation.logo_url()
            ticker = self.owner.corporation.corporation_ticker

        username = '{} Notification'.format(ticker)
        hook = dhooks_lite.Webhook(
            webhook.url,
            username=username,
            avatar_url=avatar_url
        )

        logger.info(add_prefix(
            'Trying to sent to webhook: {}'.format(
                webhook
            )
        ))
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

            max_retries = STRUCTURES_NOTIFICATION_MAX_RETRIES
            for retry_count in range(max_retries + 1):
                if retry_count > 0:
                    logger.warn(add_prefix('Retry {} / {}'.format(
                        retry_count, max_retries
                    )))
                try:
                    res = hook.execute(
                        content=content,
                        embeds=[embed],
                        wait_for_response=True
                    )
                    if res.status_ok:
                        self.is_sent = True
                        self.save()
                        success = True
                        break

                    elif res.status_code == self.HTTP_CODE_TOO_MANY_REQUESTS:
                        if 'retry_after' in res.content:
                            retry_after = \
                                res.content['retry_after'] / 1000
                        else:
                            retry_after = STRUCTURES_NOTIFICATION_WAIT_SEC
                        logger.warn(add_prefix(
                            'rate limited - retry after {} secs'.format(
                                retry_after
                            )
                        ))
                        sleep(retry_after)

                    else:
                        logger.warn(add_prefix(
                            'HTTP error {} while trying '.format(
                                res.status_code
                            ) + 'to send notifications'
                        ))
                        if retry_count < max_retries + 1:
                            sleep(STRUCTURES_NOTIFICATION_WAIT_SEC)

                except Exception as ex:
                    logger.warn(add_prefix(
                        'Unexpected issue when trying to'
                        ' send message: {}'.format(ex)
                    ))
                    if settings.DEBUG:
                        raise ex
                    else:
                        break
        return success

    def _gen_timer_structure_reinforcement(self, parsed_text, esi_client):
        """generate timer for structure reinforcements"""
        structure_obj, _ = Structure.objects.get_or_create_esi(
            parsed_text['structureID'],
            esi_client
        )
        eve_time = self.timestamp \
            + self._ldap_timedelta_2_timedelta(
                parsed_text['timeLeft']
            )
        if self.notification_type == NTYPE_STRUCTURE_LOST_SHIELD:
            details = "Armor timer"
        elif self.notification_type == NTYPE_STRUCTURE_LOST_ARMOR:
            details = "Final timer"

        return Timer(
            details=details,
            system=structure_obj.eve_solar_system.name,
            planet_moon='',
            structure=structure_obj.eve_type.name,
            objective='Friendly',
            eve_time=eve_time,
            eve_corp=self.owner.corporation,
            corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
        )

    def _gen_timer_structure_anchoring(self, parsed_text, esi_client):
        """generate timer for structure anchoring"""
        structure_type, _ = EveType.objects.get_or_create_esi(
            parsed_text['structureTypeID'],
            esi_client
        )
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text['solarsystemID'],
            esi_client
        )
        eve_time = self.timestamp \
            + self._ldap_timedelta_2_timedelta(
                parsed_text['timeLeft']
            )
        return Timer(
            details='Anchor timer',
            system=solar_system.name,
            planet_moon='',
            structure=structure_type.name,
            objective='Friendly',
            eve_time=eve_time,
            eve_corp=self.owner.corporation,
            corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
        )

    def _gen_timer_sov_reinforcements(self, parsed_text, esi_client):
        """generate timer for sov reinforcements"""
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text['solarSystemID'],
            esi_client
        )
        event_type = parsed_text['campaignEventType']
        if event_type in self.MAP_CAMPAIGN_EVENT_2_TYPE_ID:
            structure_type_name = \
                self.MAP_TYPE_ID_2_TIMER_STRUCTURE_NAME[
                    self.MAP_CAMPAIGN_EVENT_2_TYPE_ID[event_type]
                ]
        else:
            structure_type_name = 'Other'

        eve_time = self._ldap_datetime_2_dt(parsed_text['decloakTime'])
        return Timer(
            details='Sov timer',
            system=solar_system.name,
            planet_moon='',
            structure=structure_type_name,
            objective='Friendly',
            eve_time=eve_time,
            eve_corp=self.owner.corporation,
            corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
        )

    def _gen_timer_orbital_reinforcements(self, parsed_text, esi_client):
        """generate timer for orbital reinforcements"""
        solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            parsed_text['solarSystemID'],
            esi_client
        )
        planet, _ = EvePlanet.objects.get_or_create_esi(
            parsed_text['planetID'],
            esi_client
        )
        eve_time = self._ldap_datetime_2_dt(
            parsed_text['reinforceExitTime']
        )
        return Timer(
            details='Final timer',
            system=solar_system.name,
            planet_moon=planet.name,
            structure='POCO',
            objective='Friendly',
            eve_time=eve_time,
            eve_corp=self.owner.corporation,
            corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
        )

    def _gen_timer_moon_extraction(self, parsed_text, esi_client):
        """generate timer for moon mining extractions"""
        solar_system, _ = \
            EveSolarSystem.objects.get_or_create_esi(
                parsed_text['solarSystemID'],
                esi_client
            )
        moon, _ = EveMoon.objects.get_or_create_esi(
            parsed_text['moonID'],
            esi_client
        )
        if 'readyTime' in parsed_text:
            eve_time = self._ldap_datetime_2_dt(
                parsed_text['readyTime']
            )
        else:
            eve_time = None
        details = 'Extraction ready'
        system = solar_system.name
        planet_moon = moon.name
        structure_type_name = 'Moon Mining Cycle'
        objective = 'Friendly'

        if self.notification_type == NTYPE_MOONS_EXTRACTION_STARTED:
            timer = Timer(
                details=details,
                system=system,
                planet_moon=planet_moon,
                structure=structure_type_name,
                objective=objective,
                eve_time=eve_time,
                eve_corp=self.owner.corporation,
                corp_timer=STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
            )
        elif self.notification_type == NTYPE_MOONS_EXTRACTION_CANCELED:
            timer = None
            notifications_qs = Notification.objects\
                .filter(
                    notification_type=NTYPE_MOONS_EXTRACTION_STARTED,
                    owner=self.owner,
                    is_timer_added=True,
                    timestamp__lte=self.timestamp
                )\
                .order_by('-timestamp')

            for x in notifications_qs:
                parsed_text_2 = yaml.safe_load(x.text)
                my_structure_type_id = parsed_text_2['structureTypeID']
                if my_structure_type_id == parsed_text['structureTypeID']:
                    eve_time = self._ldap_datetime_2_dt(
                        parsed_text_2['readyTime']
                    )
                    timer_query = Timer.objects\
                        .filter(
                            details=details,
                            system=system,
                            planet_moon=planet_moon,
                            structure=structure_type_name,
                            objective=objective,
                            eve_time=eve_time
                        )
                    deleted_count, _ = timer_query.delete()
                    logger.info(
                        '{}: removed {} timer related '
                        'to notification'.format(
                            deleted_count,
                            self.notification_id
                        )
                    )
                    self.is_timer_added = False
                    self.save()

        return timer

    def process_for_timerboard(self, esi_client: object = None) -> bool:
        """add/removes a timer related to this notification for some types
        returns True when a timer was processed, else False
        """
        success = False
        if self.notification_type in _NTYPE_RELEVANT_FOR_TIMERBOARD:
            parsed_text = yaml.safe_load(self.text)
            try:
                if self.notification_type in [
                    NTYPE_STRUCTURE_LOST_ARMOR,
                    NTYPE_STRUCTURE_LOST_SHIELD,
                ]:
                    timer = self._gen_timer_structure_reinforcement(
                        parsed_text, esi_client
                    )
                elif self.notification_type == NTYPE_STRUCTURE_ANCHORING:
                    timer = self._gen_timer_structure_anchoring(
                        parsed_text, esi_client
                    )
                elif self.notification_type == NTYPE_SOV_STRUCTURE_REINFORCED:
                    timer = self._gen_timer_sov_reinforcements(
                        parsed_text, esi_client
                    )
                elif self.notification_type == NTYPE_ORBITAL_REINFORCED:
                    timer = self._gen_timer_orbital_reinforcements(
                        parsed_text, esi_client
                    )
                elif self.notification_type in [
                    NTYPE_MOONS_EXTRACTION_STARTED,
                    NTYPE_MOONS_EXTRACTION_CANCELED
                ]:
                    if not STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED:
                        timer = None
                    else:
                        timer = self._gen_timer_moon_extraction(
                            parsed_text, esi_client
                        )
                else:
                    raise NotImplementedError()

                if timer:
                    timer.save()
                    logger.info(
                        '{}: added timer related notification'.format(
                            self.notification_id
                        )
                    )
                    self.is_timer_added = True
                    self.save()
                    success = True

            except Exception as ex:
                logger.exception(
                    '{}: Failed to add timer from notification: {}'.format(
                        self.notification_id,
                        ex
                    )
                )
                if settings.DEBUG:
                    raise ex

        return success

    def is_npc_attacking(self):
        """ whether this notification is about a NPC attacking"""
        result = False
        if self.notification_type in [
            NTYPE_ORBITAL_ATTACKED,
            NTYPE_STRUCTURE_UNDER_ATTACK
        ]:
            parsed_text = yaml.safe_load(self.text)
            corporation_id = None
            if self.notification_type == NTYPE_STRUCTURE_UNDER_ATTACK:
                if ('corpLinkData' in parsed_text
                    and len(parsed_text['corpLinkData']) >= 3
                ):
                    corporation_id = int(parsed_text['corpLinkData'][2])

            if self.notification_type == NTYPE_ORBITAL_ATTACKED:
                if 'aggressorCorpID' in parsed_text:
                    corporation_id = int(parsed_text['aggressorCorpID'])

            if corporation_id >= 1000000 and corporation_id <= 2000000:
                result = True

        return result

    def filter_for_npc_attacks(self):
        """true when notification to be filtered out due to npc attacks"""
        return not STRUCTURES_REPORT_NPC_ATTACKS and self.is_npc_attacking()

    def filter_for_alliance_level(self):
        """true when notification to be filtered out due to alliance level"""
        return self.is_alliance_level and not self.owner.is_alliance_main

    @classmethod
    def get_all_types(cls):
        """returns a set with all supported notification types"""
        return {x[0] for x in NTYPE_CHOICES}

    @classmethod
    def get_all_type_names(cls):
        """returns a set with names of all supported notification types"""
        return {x[1] for x in NTYPE_CHOICES}

    @classmethod
    def get_types_for_timerboard(cls):
        """returns set of types relevant for the timerboard"""
        return _NTYPE_RELEVANT_FOR_TIMERBOARD

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
