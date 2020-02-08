import logging
import os
import sys

from django.conf import settings
from django.contrib.auth.models import User, Permission
from django.contrib.messages.constants import *
from django.contrib import messages
from django.db.models import Q
from django.utils.html import mark_safe

from allianceauth.notifications import notify


# Format for output of datetime for this app
DATETIME_FORMAT = '%Y-%m-%d %H:%M'


def get_swagger_spec_path() -> str:
    """returns the path to the current swagger spec file"""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        'swagger.json'
    )


def make_logger_prefix(tag: str):
    """creates a function to add logger prefix"""
    return lambda text : '{}: {}'.format(tag, text)


class LoggerAddTag(logging.LoggerAdapter):
    """add custom tag to a logger"""
    def __init__(self, logger, prefix):
        super(LoggerAddTag, self).__init__(logger, {})
        self.prefix = prefix

    def process(self, msg, kwargs):
        return '[%s] %s' % (self.prefix, msg), kwargs


class messages_plus():
    """Pendant to Django messages adding level icons and HTML support
    
    Careful: Use with safe strings only
    """

    @classmethod
    def add_messages_icon(cls,level, message):
        """Adds an level based icon to Django messages"""
        glyph_map = {
            DEBUG: 'eye-open',
            INFO: 'info-sign',
            SUCCESS: 'ok-sign',
            WARNING: 'exclamation-sign',
            ERROR: 'alert',
        }
        if level in glyph_map:
            glyph = glyph_map[level]
        else:
            glyph = glyph_map[INFO]

        message = ('<span class="glyphicon glyphicon-{}" '.format(glyph)
            + 'aria-hidden="true"></span>&nbsp;&nbsp;' 
            + message)
        return mark_safe(message)

    @classmethod
    def debug(cls, request, message, extra_tags='', fail_silently=False):
        messages.debug(
            request, 
            cls.add_messages_icon(DEBUG, message), 
            extra_tags, 
            fail_silently
        )

    @classmethod
    def info(cls, request, message, extra_tags='', fail_silently=False):
        messages.info(
            request, 
            cls.add_messages_icon(INFO, message), 
            extra_tags, 
            fail_silently
        )
    @classmethod
    def success(cls, request, message, extra_tags='', fail_silently=False):
        messages.success(
            request, 
            cls.add_messages_icon(SUCCESS, message), 
            extra_tags, 
            fail_silently
        )
    
    @classmethod
    def warning(cls, request, message, extra_tags='', fail_silently=False):
        messages.warning(
            request, 
            cls.add_messages_icon(WARNING, message), 
            extra_tags, 
            fail_silently
        )
    
    @classmethod
    def error(cls, request, message, extra_tags='', fail_silently=False):
        messages.error(
            request, 
            cls.add_messages_icon(ERROR, message), 
            extra_tags, 
            fail_silently
        )


def notify_admins(message: str, title: str, level = 'info') -> None:
    """send notification to all admins"""
    try:
        perm = Permission.objects.get(codename="logging_notifications")
        users = User.objects.filter(
            Q(groups__permissions=perm) 
            | Q(user_permissions=perm) 
            | Q(is_superuser=True)
        ).distinct()

        for user in users:
            notify(
                user,
                title=title,
                message=message,
                level=level
            )
    except Permission.DoesNotExist:
        pass


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def clean_setting(
    name: str,     
    default_value: object,         
    min_value: int = None,
    max_value: int = None,
    required_type: type = None
):
    """cleans the input for a custom setting
    
    Will use `default_value` if settings does not exit or has the wrong type
    or is outside define boundaries (for int only)

    Need to define `required_type` if `default_value` is `None`

    Will assume `min_value` of 0 for int (can be overriden)

    Returns cleaned value for setting
    """                
    if default_value is None and not required_type:
        raise ValueError('You must specify a required_type for None defaults')
    
    if not required_type:
        required_type = type(default_value)

    if min_value is None and required_type == int:
        min_value = 0        
        
    if (hasattr(settings, name)
        and isinstance(getattr(settings, name), required_type)
        and (min_value is None or getattr(settings, name) >= min_value)
        and (max_value is None or getattr(settings, name) <= max_value)
    ):        
        return getattr(settings, name)    
    else:
        return default_value