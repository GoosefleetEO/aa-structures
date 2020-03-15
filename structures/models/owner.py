"""Owner related models"""

import datetime
import logging

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCorporationInfo

from ..app_settings import (    
    STRUCTURES_FEATURE_CUSTOMS_OFFICES,
    STRUCTURES_FEATURE_STARBASES,
    STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES,    
    STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES,            
    STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES,    
)
from ..utils import LoggerAddTag

logger = LoggerAddTag(logging.getLogger(__name__), __package__)


class General(models.Model):
    """Meta model for global app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ('basic_access', _('Can access this app and view')),
            ('view_alliance_structures', _('Can view alliance structures')),
            ('view_all_structures', _('Can view all structures')),
            ('add_structure_owner', _('Can add new structure owner')),
        )


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
            _('No error')
        ),
        (
            ERROR_TOKEN_INVALID,
            _('Invalid token')
        ),
        (
            ERROR_TOKEN_EXPIRED,
            _('Expired token')
        ),
        (
            ERROR_INSUFFICIENT_PERMISSIONS,
            _('Insufficient permissions')
        ),
        (
            ERROR_NO_CHARACTER,
            _('No character set for fetching data from ESI')
        ),
        (
            ERROR_ESI_UNAVAILABLE,
            _('ESI API is currently unavailable')
        ),
        (
            ERROR_OPERATION_MODE_MISMATCH,
            _('Operaton mode does not match with current setting')
        ),
        (
            ERROR_UNKNOWN,
            _('Unknown error')
        ),
    ]

    corporation = models.OneToOneField(
        EveCorporationInfo,
        primary_key=True,
        on_delete=models.CASCADE,
        help_text=_('Corporation owning structures')
    )
    character = models.ForeignKey(
        CharacterOwnership,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        help_text=_('character used for syncing structures')
    )
    structures_last_sync = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('when the last sync happened')
    )
    structures_last_error = models.IntegerField(
        choices=ERRORS_LIST,
        default=ERROR_NONE,
        help_text=_('error that occurred at the last sync atttempt (if any)')
    )
    notifications_last_sync = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('when the last sync happened')
    )
    notifications_last_error = models.IntegerField(
        choices=ERRORS_LIST,
        default=ERROR_NONE,
        help_text=_('error that occurred at the last sync atttempt (if any)')
    )
    forwarding_last_sync = models.DateTimeField(
        null=True,
        default=None,
        blank=True,
        help_text=_('when the last sync happened')
    )
    forwarding_last_error = models.IntegerField(
        choices=ERRORS_LIST,
        default=ERROR_NONE,
        help_text=_('error that occurred at the last sync atttempt (if any)')
    )
    webhooks = models.ManyToManyField(
        'Webhook',
        default=None,
        blank=True,
        help_text=_('notifications are sent to these webhooks. ')
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_(
            'whether this owner is currently included in the sync process'
        )
    )
    is_alliance_main = models.BooleanField(
        default=False,
        help_text=_(
            'whether alliance wide notifications '
            'are forwarded for this owner (e.g. sov notifications)'
        )
    )
    is_included_in_service_status = models.BooleanField(
        default=True,
        help_text=_(
            'whether the sync status of this owner is included in '
            'the overall status of this services'
        )
    )

    def __str__(self) -> str:
        return str(self.corporation.corporation_name)

    def __repr__(self):
        return '{}(id={}, corporation=\'{}\')'.format(
            self.__class__.__name__,
            self.id,
            self.__str__
        )

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
