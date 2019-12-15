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