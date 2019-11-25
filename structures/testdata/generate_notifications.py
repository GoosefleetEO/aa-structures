import os
import sys
import inspect

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
    inspect.currentframe()
)))
myauth_dir = os.path.dirname(os.path.dirname(os.path.dirname(currentdir))) \
    + "/myauth"
sys.path.insert(0, myauth_dir)

import json
import logging
from datetime import datetime

import django
from django.db import transaction
from django.apps import apps
from django.utils.timezone import now

# init and setup django project
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
django.setup()

if not apps.is_installed('structures'):
    raise RuntimeError("The app structures is not installed")    

from allianceauth.eveonline.models import EveCorporationInfo
from esi.clients import esi_client_factory

from structures.models import *

print('load_test_notifications - script loads test notification into the local database ')

print('Connecting to ESI ...')
client = esi_client_factory()

print('Creating base data ...')
corporation_id = 1000127
try:
    corporation = EveCorporationInfo.objects.get(
        corporation_id=corporation_id
    )
except EveCorporationInfo.DoesNotExist:
    corporation = EveCorporationInfo.objects.create_corporation(
        corporation_id
    )

owner, _ = Owner.objects.get_or_create(corporation=corporation)
webhook = Webhook.objects.first()
if webhook:
    owner.webhooks.add(webhook)

eve_type, _ = EveType.objects.get_or_create_esi(35834, client)
eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(30000142, client)

structure, _ = Structure.objects.update_or_create(
    id=1000000000001,
    defaults={
        "owner": owner,
        "eve_type": eve_type,
        "name": 'Test structure for notifications',
        "eve_solar_system": eve_solar_system,                        
        "reinforce_hour": 12,
        "reinforce_weekday": 4,
        "state":Structure.STATE_SHIELD_VULNERABLE
    }
)


with open(
    file=currentdir + '/td_notifications_2.json', 
    mode='r', 
    encoding='utf-8'
) as f:
    notifications = json.load(f)

with transaction.atomic():                                    
    for notification in notifications:                        
        notification_type = \
            Notification.get_matching_notification_type(
                notification['type']
            )
        if notification_type:
            sender_type = \
                EveEntity.get_matching_entity_type(
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
            obj = Notification.objects.update_or_create(
                notification_id=notification['notification_id'],
                owner=owner,
                defaults={
                    'sender': sender,
                    'timestamp': now(),
                    'notification_type': notification_type,
                    'text': text,
                    'is_read': is_read,
                    'last_updated': now(),
                    'is_sent': True
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
