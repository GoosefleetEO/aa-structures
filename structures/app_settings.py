from django.conf import settings


# defines after how many hours a notification becomes stale
# stale notification will no longer be sent automatically
STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION = getattr(
    settings, 
    'STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION', 
    24
)
