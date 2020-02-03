
from .utils import set_app_setting

set_app_setting.my_module = __name__

# Whether to automatically add timers for certain notifications 
# on the timerboard (will have no effect if aa-timerboard app is not installed)
set_app_setting('STRUCTURES_ADD_TIMERS', True)

# whether admins will get notifications about import events like
# when someone adds a structure owner
set_app_setting('STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED', True)

# whether the structure list has default tags filter enabled by default
set_app_setting('STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED', False)

# Enables features for developers, e.g. write access to all models in admin
# UNDOCUMENTED SETTING
set_app_setting('STRUCTURES_DEVELOPER_MODE', False)

# Whether the customs offices feature is active
set_app_setting('STRUCTURES_FEATURE_CUSTOMS_OFFICES', False)

# Max time in minutes since last successful notification forwarding
# before service is reported as down
set_app_setting('STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES', 5)

# defines after how many hours a notification becomes stale
# stale notification will no longer be sent automatically
set_app_setting('STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION', 24)

# whether to create / remove timers from moon extraction notifications
set_app_setting('STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED', False)

# Max number of retries for sending a notification if an error occurred
# e.g. rate limiting
set_app_setting('STRUCTURES_NOTIFICATION_MAX_RETRIES', 3)

# Max time in minutes since last successful notification sync 
# before service is reported as down
set_app_setting('STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES', 15)

# Default wait time in seconds before retrying to send a notification 
# to Discord after an error occurred
set_app_setting('STRUCTURES_NOTIFICATION_WAIT_SEC', 5)

# Enables archiving of all notifications received from ESI to files
# notifications will by stored into one continuous file per corporations
# UNDOCUMENTED SETTING
set_app_setting('STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED', False)

# how to handle notification about NPC attacks
set_app_setting('STRUCTURES_REPORT_NPC_ATTACKS', True)

# whether fuel expires in structures browser is shown as absolute value
set_app_setting('STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE', True)

# Max time in minutes since last successful structures sync 
# before service is reported as down
set_app_setting('STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES', 120)

# whether created timers are corp restricted on the timerboard
set_app_setting('STRUCTURES_TIMERS_ARE_CORP_RESTRICTED', False)
