from app_utils.django import clean_setting

# Whether to automatically add timers for certain notifications
# on the timerboard (will have no effect if aa-timerboard app is not installed)
STRUCTURES_ADD_TIMERS = clean_setting("STRUCTURES_ADD_TIMERS", True)

# whether admins will get notifications about import events like
# when someone adds a structure owner
STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED = clean_setting(
    "STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED", True
)

# Sets the default language to be used in case no language can be determined
# e.g. this language will be used when creating timers
# Please use the language codes as defined in the base.py settings file
STRUCTURES_DEFAULT_LANGUAGE = clean_setting("STRUCTURES_DEFAULT_LANGUAGE", "en")

# whether the structure list has default tags filter enabled by default
STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED = clean_setting(
    "STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED", False
)

# Enables features for developers
# e.g. write access to all models in admin and writing raw data received from ESI
# UNDOCUMENTED SETTING
STRUCTURES_DEVELOPER_MODE = clean_setting("STRUCTURES_DEVELOPER_MODE", False)

# Whether the customs offices feature is active
STRUCTURES_FEATURE_CUSTOMS_OFFICES = clean_setting(
    "STRUCTURES_FEATURE_CUSTOMS_OFFICES", True
)

# Whether the starbases / POSes feature is active
STRUCTURES_FEATURE_STARBASES = clean_setting("STRUCTURES_FEATURE_STARBASES", True)


# defines after how many hours a notification becomes stale
# stale notification will no longer be sent automatically
STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION = clean_setting(
    "STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION", 24
)

# whether to create / remove timers from moon extraction notifications
STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED = clean_setting(
    "STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED", True
)

# Max number of retries for sending a notification if an error occurred
# e.g. rate limiting
STRUCTURES_NOTIFICATION_MAX_RETRIES = clean_setting(
    "STRUCTURES_NOTIFICATION_MAX_RETRIES", 3
)

# Max time in minutes since last successful notification sync
# before service is reported as down
STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES = clean_setting(
    "STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 20
)

# Duration of period in minutes when notifications are synced
STRUCTURES_NOTIFICATION_SYNC_PERIOD_MINUTES = clean_setting(
    "STRUCTURES_NOTIFICATION_SYNC_PERIOD_MINUTES", 2
)

# Default wait time in seconds before retrying to send a notification
# to Discord after an error occurred
STRUCTURES_NOTIFICATION_WAIT_SEC = clean_setting("STRUCTURES_NOTIFICATION_WAIT_SEC", 5)

# Enables archiving of all notifications received from ESI to files
# notifications will by stored into one continuous file per corporations
# UNDOCUMENTED SETTING
STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED = clean_setting(
    "STRUCTURES_NOTIFICATIONS_ARCHIVING_ENABLED", False
)

# Wether structures sets the name and avatar icon of a webhook
# else the webhook will show it's default names as set when defining the webhook
STRUCTURES_NOTIFICATION_SET_AVATAR = clean_setting(
    "STRUCTURES_NOTIFICATION_SET_AVATAR", True
)

# Wether ore details are shown on moon timers
STRUCTURES_NOTIFICATION_SHOW_MOON_ORE = clean_setting(
    "STRUCTURES_NOTIFICATION_SHOW_MOON_ORE", True
)


# how to handle notification about NPC attacks
STRUCTURES_REPORT_NPC_ATTACKS = clean_setting("STRUCTURES_REPORT_NPC_ATTACKS", True)

# whether fuel expires in structures browser is shown as absolute value
STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE = clean_setting(
    "STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE", True
)

# Max time in minutes since last successful structures sync
# before service is reported as down
STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES = clean_setting(
    "STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES", 120
)

# Hard timeout for tasks in seconds to reduce task accumulation during outages
STRUCTURES_TASKS_TIME_LIMIT = clean_setting("STRUCTURES_TASKS_TIME_LIMIT", 7200)

# whether created timers are corp restricted on the timerboard
STRUCTURES_TIMERS_ARE_CORP_RESTRICTED = clean_setting(
    "STRUCTURES_TIMERS_ARE_CORP_RESTRICTED", False
)

# whether ESI timeout is enabled
STRUCTURES_ESI_TIMEOUT_ENABLED = clean_setting("STRUCTURES_ESI_TIMEOUT_ENABLED", True)

# Default page size for structure list.
# Must be an integer value from the current options as seen in the app.
STRUCTURES_DEFAULT_PAGE_LENGTH = clean_setting("STRUCTURES_DEFAULT_PAGE_LENGTH", 10)

# Wether paging is enabled for the structure list
STRUCTURES_PAGING_ENABLED = clean_setting("STRUCTURES_PAGING_ENABLED", True)

# INTERNAL SETTINGS

# Number of notifications to count for short mean turnaround time
STRUCTURES_NOTIFICATION_TURNAROUND_SHORT = clean_setting(
    "STRUCTURES_NOTIFICATION_TURNAROUND_SHORT", 5
)

# Number of notifications to count for medium mean turnaround time
STRUCTURES_NOTIFICATION_TURNAROUND_MEDIUM = clean_setting(
    "STRUCTURES_NOTIFICATION_TURNAROUND_MEDIUM", 15
)

# Number of notifications to count for long mean turnaround time
STRUCTURES_NOTIFICATION_TURNAROUND_LONG = clean_setting(
    "STRUCTURES_NOTIFICATION_TURNAROUND_LONG", 50
)

# Turnaround duration with more than x seconds are regarded as outliers
# and will be ignored when calculating the averages
STRUCTURES_NOTIFICATION_TURNAROUND_MAX_VALID = clean_setting(
    "STRUCTURES_NOTIFICATION_TURNAROUND_MAX_VALID", 3600
)

# Timeout for throttled issue notifications to users and admins in seconds.
STRUCTURES_NOTIFY_THROTTLED_TIMEOUT = clean_setting(
    "STRUCTURES_NOTIFY_THROTTLED_TIMEOUT", 86400
)
