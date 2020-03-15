"""Structure related models"""

import logging

from django.db import models
from django.core.validators import MaxValueValidator
from django.utils.html import escape, format_html
from django.utils.translation import gettext_lazy as _

from ..managers import StructureManager

from ..utils import LoggerAddTag
from .eveuniverse import EveType, EveSolarSystem, EvePlanet, EveMoon
from .owner import Owner

logger = LoggerAddTag(logging.getLogger(__name__), __package__)


class StructureTag(models.Model):
    """tag for organizing structures"""

    STYLE_CHOICES = [
        ('default', _('grey')),
        ('primary', _('dark blue')),
        ('success', _('green')),
        ('info', _('light blue')),
        ('warning', _('yellow')),
        ('danger', _('red')),
    ]

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text=_('name of the tag - must be unique')
    )
    description = models.TextField(
        null=True,
        default=None,
        blank=True,
        help_text=_('description for this tag')
    )
    style = models.CharField(
        max_length=16,
        choices=STYLE_CHOICES,
        default='default',
        blank=True,
        help_text=_('color style of tag')
    )
    is_default = models.BooleanField(
        default=False,
        help_text=_(
            'if true this tag will automatically be ' 
            'added to new structures'
        )
    )

    def __str__(self) -> str:
        return self.name

    def __repr__(self):
        return '{}(id={}, name=\'{}\')'.format(
            self.__class__.__name__,
            self.id,
            self.name
        )

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
        (STATE_NA, _('N/A')),
        (STATE_UNKNOWN, _('unknown')),
    ]

    id = models.BigIntegerField(
        primary_key=True,
        help_text=_('The Item ID of the structure')
    )
    owner = models.ForeignKey(
        Owner,
        on_delete=models.CASCADE,
        help_text=_('Corporation that owns the structure')
    )
    eve_type = models.ForeignKey(
        EveType,
        on_delete=models.CASCADE,
        help_text=_('type of the structure')
    )
    name = models.CharField(
        max_length=255,
        help_text=_('The full name of the structure')
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
        help_text=_('Planet next to this structure - if any')
    )
    eve_moon = models.ForeignKey(
        EveMoon,
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True,
        help_text=_('Moon next to this structure - if any')
    )
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
    fuel_expires = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('Date on which the structure will run out of fuel')
    )
    next_reinforce_hour = models.PositiveIntegerField(
        null=True,
        default=None,
        blank=True,
        validators=[MaxValueValidator(23)],
        help_text=_(
            'The requested change to reinforce_hour that will take '
            'effect at the time shown by next_reinforce_apply'
        )
    )
    next_reinforce_weekday = models.PositiveIntegerField(
        null=True,
        default=None,
        blank=True,
        validators=[MaxValueValidator(6)],
        help_text=_(
            'The date and time when the structure’s newly requested '
            'reinforcement times (e.g. next_reinforce_hour and '
            'next_reinforce_day) will take effect'
        )
    )
    next_reinforce_apply = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_(
            'The requested change to reinforce_weekday that will take '
            'effect at the time shown by next_reinforce_apply'
        )
    )
    reinforce_hour = models.PositiveIntegerField(
        validators=[MaxValueValidator(23)],
        null=True,
        default=None,
        blank=True,
        help_text=_(
            'The hour of day that determines the four hour window '
            'when the structure will randomly exit its reinforcement periods '
            'and become vulnerable to attack against its armor and/or hull. '
            'The structure will become vulnerable at a random time that '
            'is +/- 2 hours centered on the value of this property'
        )
    )
    reinforce_weekday = models.PositiveIntegerField(
        null=True,
        default=None,
        blank=True,
        validators=[MaxValueValidator(6)],
        help_text='(no longer used)'
    )
    state = models.IntegerField(
        choices=STATE_CHOICES,
        default=STATE_UNKNOWN,
        blank=True,
        help_text=_('Current state of the structure')
    )
    state_timer_start = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('Date at which the structure will move to it’s next state')
    )
    state_timer_end = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('Date at which the structure entered it’s current state')
    )
    unanchors_at = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('Date at which the structure will unanchor')
    )
    last_updated = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('date this structure was last updated from the EVE server')
    )
    tags = models.ManyToManyField(
        StructureTag,
        default=None,
        blank=True,
        help_text=_('list of tags for this structure')
    )

    objects = StructureManager()

    @property
    def state_str(self):
        msg = [(x, y) for x, y in self.STATE_CHOICES if x == self.state]
        return msg[0][1].replace('_', ' ') if len(msg) > 0 else _('undefined')

    @property
    def is_low_power(self):
        return False if self.eve_type.is_poco else not self.fuel_expires

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

    def __repr__(self):
        return '{}(id={}, name=\'{}\')'.format(
            self.__class__.__name__,
            self.id,
            self.name
        )

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
        help_text=_('Structure this service is installed to')
    )
    name = models.CharField(
        max_length=64,
        help_text=_('Name of the service')
    )
    state = models.IntegerField(
        choices=STATE_CHOICES,
        help_text=_('Current state of this service')
    )

    class Meta:
        unique_together = (('structure', 'name'),)

    def __str__(self):
        return '{} - {}'.format(str(self.structure), self.name)

    def __repr__(self):
        return '{}(id={}, name=\'{}\')'.format(
            self.__class__.__name__,
            self.id,
            self.name
        )

    @classmethod
    def get_matching_state(cls, state_name) -> int:
        """returns matching state for given state name"""
        match = [cls.STATE_OFFLINE]
        for x in cls.STATE_CHOICES:
            if state_name == x[1]:
                match = x
                break

        return match[0]
