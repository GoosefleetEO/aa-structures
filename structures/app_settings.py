
import sys

from django.conf import settings


def _set_app_setting(
    name: str,     
    default_value: object,         
    min_value: int = None,
    max_value: int = None,
    required_type: type = None
):
    """sets app setting from local setting file with input checks
    
    Will use `default_value` if settings does not exit or has the wrong type
    or is outside define boundaries (for int only)

    Need to define `required_type` if `default_value` is `None`

    Will assume `min_value` of 0 for int (can be overriden)
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
        setattr(sys.modules[__name__], name, getattr(settings, name))        
    
    else:
        setattr(sys.modules[__name__], name, default_value)


# Whether to automatically add timers for certain notifications 
# on the timerboard (will have no effect if aa-timerboard app is not installed)
_set_app_setting('STRUCTURES_ADD_TIMERS', True)

# whether admins will get notifications about import events like
# when someone adds a structure owner
_set_app_setting('STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED', True)

# whether the structure list has default tags filter enabled by default
_set_app_setting('STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED', False)

# Enables features for developers, e.g. write access to all models in admin
# UNDOCUMENTED SETTING
_set_app_setting('STRUCTURES_DEVELOPER_MODE', False)

# Whether the customs offices feature is active
_set_app_setting('STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)

# Max time in minutes since last successful notification forwarding
# before service is reported as down
_set_app_setting('STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES', 5)

# defines after how many hours a notification becomes stale
# stale notification will no longer be sent automatically
_set_app_setting('STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION', 24)

# whether to create / remove timers from moon extraction notifications
_set_app_setting('STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED', False)

# Max number of retries for sending a notification if an error occurred
# e.g. rate limiting
_set_app_setting('STRUCTURES_NOTIFICATION_MAX_RETRIES', 3)

# Max time in minutes since last successful notification sync 
# before service is reported as down
_set_app_setting('STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES', 15)

# Default wait time in seconds before retrying to send a notification 
# to Discord after an error occurred
_set_app_setting('STRUCTURES_NOTIFICATION_WAIT_SEC', 5)

# Enables archiving of all notifications received from ESI to files
# notifications will by stored into one continuous file per corporations
# UNDOCUMENTED SETTING
_set_app_setting('STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED', False)

# how to handle notification about NPC attacks
_set_app_setting('STRUCTURES_REPORT_NPC_ATTACKS', True)

# whether fuel expires in structures browser is shown as absolute value
_set_app_setting('STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE', True)

# Max time in minutes since last successful structures sync 
# before service is reported as down
_set_app_setting('STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES', 120)

# whether created timers are corp restricted on the timerboard
_set_app_setting('STRUCTURES_TIMERS_ARE_CORP_RESTRICTED', False)
