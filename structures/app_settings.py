from django.conf import settings


# defines after how many hours a notification becomes stale
# stale notification will no longer be sent automatically
STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION = getattr(
    settings, 
    'STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION', 
    24
)

# whether admins will get notifications about import events like
# when someone adds a structure owner
STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED = getattr(
    settings, 
    'STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED', 
    True
)

# Max time in minutes since last successful structures sync 
# before service is reported as down
STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES = getattr(
    settings, 
    'STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES', 
    120
)

# Max time in minutes since last successful notification sync 
# before service is reported as down
STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES = getattr(
    settings, 
    'STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES', 
    15
)

# Max time in minutes since last successful notification forwarding
# before service is reported as down
STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES = getattr(
    settings, 
    'STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES', 
    5
)

# Max number of retries for sending a notification if an error occurred
# e.g. rate limiting
STRUCTURES_NOTIFICATION_MAX_RETRIES = getattr(
    settings, 
    'STRUCTURES_NOTIFICATION_MAX_RETRIES', 
    3
)

# Default wait time in seconds before retrying to send a notification 
# to Discord after an error occurred
STRUCTURES_NOTIFICATION_WAIT_SEC = getattr(
    settings, 
    'STRUCTURES_NOTIFICATION_WAIT_SEC', 
    5
)

# Enables features for developers, e.g. write access to all models in admin
STRUCTURES_DEVELOPER_MODE = getattr(
    settings, 
    'STRUCTURES_DEVELOPER_MODE', 
    False
)

# Enables archiving of all notifications received from ESI to files
# notifications will by stored into one continuous file per corporations
STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED = getattr(
    settings, 
    'STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED', 
    False
)

# Whether to automatically add timers for certain notifications 
# on the timerboard (will have no effect if aa-timerboard app is not installed)
STRUCTURES_ADD_TIMERS = getattr(
    settings, 
    'STRUCTURES_ADD_TIMERS', 
    True
)

# Whether the customs offices feature is active
STRUCTURES_FEATURE_CUSTOMS_OFFICES = getattr(
    settings, 
    'STRUCTURES_FEATURE_CUSTOMS_OFFICES', 
    False
)

# whether fuel expires in structures browser is shown as absolute value
STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE = getattr(
    settings, 
    'STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE', 
    True
)

# whether the structure list has default tags filter enabled by default
STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED = getattr(
    settings, 
    'STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED', 
    False
)

# how to handle notification about NPC attacks
if (hasattr(settings, 'STRUCTURES_REPORT_NPC_ATTACKS')
    and settings.STRUCTURES_REPORT_NPC_ATTACKS in [True, False]       
):
    STRUCTURES_REPORT_NPC_ATTACKS = settings.STRUCTURES_REPORT_NPC_ATTACKS
else:
    STRUCTURES_REPORT_NPC_ATTACKS = True

# whether to create / remove timers from moon extraction notifications
if (hasattr(settings, 'STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED')
    and settings.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED in [True, False] 
):
    STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED \
        = settings.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED
else:
    STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED = False


# whether created timers are corp restricted on the timerboard
if (hasattr(settings, 'STRUCTURES_TIMERS_ARE_CORP_RESTRICTED')
    and settings.STRUCTURES_TIMERS_ARE_CORP_RESTRICTED in [True, False]       
):
    STRUCTURES_TIMERS_ARE_CORP_RESTRICTED \
        = settings.STRUCTURES_TIMERS_ARE_CORP_RESTRICTED
else:
    STRUCTURES_TIMERS_ARE_CORP_RESTRICTED = False