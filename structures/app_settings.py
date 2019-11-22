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

# Enables features for developers, e.g. write access to all models in admin
STRUCTURES_DEVELOPER_MODE = getattr(
    settings, 
    'STRUCTURES_DEVELOPER_MODE', 
    False
)