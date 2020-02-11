# this scripts adds test notifications to a specified corporation / structure

from datetime import timedelta
import inspect
import json
import os
import sys

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
    inspect.currentframe()
)))
myauth_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(currentdir)))
) + "/myauth"
sys.path.insert(0, myauth_dir)


import django   # noqa: E402
from django.db import transaction   # noqa: E402
from django.apps import apps    # noqa: E402
from django.utils.timezone import now   # noqa: E402

# init and setup django project
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
django.setup()

if not apps.is_installed('structures'):
    raise RuntimeError("The app structures is not installed")    

from allianceauth.eveonline.models import EveCorporationInfo    # noqa: E402
from esi.clients import esi_client_factory  # noqa: E402

from structures.models import Owner, Structure, Notification, EveEntity  # noqa: E402, E501

# corporation / structure the notifications will be added to
CORPORATION_ID = 98612071   # SODIC
STRUCTURE_ID = 1030681055667    # Alpha

print(
    'load_test_notifications - '
    'script loads test notification into the local database '
)

print('Connecting to ESI ...')
client = esi_client_factory()

print('Creating base data ...')
try:
    corporation = EveCorporationInfo.objects.get(
        corporation_id=CORPORATION_ID
    )
except EveCorporationInfo.DoesNotExist:
    corporation = EveCorporationInfo.objects.create_corporation(
        CORPORATION_ID
    )

owner = Owner.objects.get(corporation=corporation)
structure = Structure.objects.get(id=STRUCTURE_ID)

with open(
    file=currentdir + '/td_notifications_2.json', 
    mode='r', 
    encoding='utf-8'
) as f:
    notifications_json = f.read()

notifications_json = notifications_json.replace(
    '1000000000001', str(structure.id)
)
notifications_json = notifications_json.replace(
    '35835', str(structure.eve_type_id)
)
notifications_json = notifications_json.replace(
    '35835', str(structure.eve_type_id)
)
notifications_json = notifications_json.replace(
    '30002537', str(structure.eve_solar_system_id)
)
notifications = json.loads(notifications_json)

with transaction.atomic():                                    
    timestamp_start = now() - timedelta(hours=2)
    for notification in notifications:                        
        notification_type = \
            Notification.get_matching_notification_type(
                notification['type']
            )
        if notification_type:
            sender_type = \
                EveEntity.get_matching_entity_category(
                    notification['sender_type']
                )
            if sender_type != EveEntity.CATEGORY_OTHER:
                sender, _ = EveEntity\
                    .objects.get_or_create_esi(
                        notification['sender_id'],
                        client
                    )
            else:
                sender, _ = EveEntity\
                    .objects.get_or_create(
                        id=notification['sender_id'],
                        defaults={
                            'category': sender_type
                        }
                    )
            text = notification['text'] \
                if 'text' in notification else None
            is_read = notification['is_read'] \
                if 'is_read' in notification else None
            timestamp_start = timestamp_start + timedelta(minutes=5)
            obj = Notification.objects.update_or_create(
                notification_id=notification['notification_id'],
                owner=owner,
                defaults={
                    'sender': sender,
                    'timestamp': timestamp_start,
                    'notification_type': notification_type,
                    'text': text,
                    'is_read': is_read,
                    'last_updated': now(),
                    'is_sent': False
                }
            )                            

print('DONE')


"""
for notification in notifications:
    dt = datetime.datetime.utcfromtimestamp(notification['timestamp'])
    dt = pytz.utc.localize(dt)
    notification['timestamp'] = dt.isoformat()

with open(
    file=currentdir + '/td_notifications_2.json', 
    mode='w', 
    encoding='utf-8'
) as f:
    json.dump(
        notifications, 
        f,         
        sort_keys=True, 
        indent=4
    )

"""
