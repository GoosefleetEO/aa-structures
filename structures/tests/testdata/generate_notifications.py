# flake8: noqa
"""
this scripts create a test owner and adds test notifications to it
"""

import inspect
import json
import os
import sys
from datetime import timedelta

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
myauth_dir = (
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(currentdir))))
    + "/myauth"
)
sys.path.insert(0, myauth_dir)


import django
from django.apps import apps
from django.db import transaction
from django.utils.timezone import now

# init and setup django project
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
django.setup()

if not apps.is_installed("structures"):
    raise RuntimeError("The app structures is not installed")

from esi.clients import esi_client_factory
from eveuniverse.models import EveEntity

from allianceauth.eveonline.models import EveCorporationInfo

from structures.models import Notification, Owner, Structure, Webhook

# corporation / structure the notifications will be added to
CORPORATION_ID = 98587692  # RABIS

print(
    "load_test_notifications - "
    "script loads test notification into the local database "
)

print("Connecting to ESI ...")
client = esi_client_factory()

print("Creating base data ...")
try:
    corporation = EveCorporationInfo.objects.get(corporation_id=CORPORATION_ID)
except EveCorporationInfo.DoesNotExist:
    corporation = EveCorporationInfo.objects.create_corporation(CORPORATION_ID)

owner, created = Owner.objects.get_or_create(
    corporation=corporation, defaults={"is_active": False}
)
if created and not owner.webhooks.exists():
    webhook = Webhook.objects.filter(is_active=True, is_default=True).first()
    if webhook:
        owner.webhooks.add(webhook)

structure = {
    "fuel_expires": None,
    "name": "Test Structure Alpha",
    "next_reinforce_apply": None,
    "next_reinforce_hour": None,
    "position": {"x": 55028384780.0, "y": 7310316270.0, "z": -163686684205.0},
    "profile_id": 101853,
    "reinforce_hour": 18,
    "services": [
        {
            "name": "Clone Bay",
            "name_de": "Clone Bay_de",
            "name_ko": "Clone Bay_ko",
            "state": "online",
        },
        {
            "name": "Market Hub",
            "name_de": "Market Hub_de",
            "name_ko": "Market Hub_ko",
            "state": "offline",
        },
    ],
    "state": "shield_vulnerable",
    "state_timer_end": None,
    "state_timer_start": None,
    "structure_id": 1999999999999,
    "system_id": 30002537,
    "type_id": 35832,
    "unanchors_at": None,
}
structure, _ = Structure.objects.update_or_create_from_dict(structure, owner)

with open(file=currentdir + "/entities.json", mode="r", encoding="utf-8") as fp:
    data = json.load(fp)

notifications = data["Notification"]
for notification in notifications:
    if notification["sender_id"] == 2901:
        notification["sender_id"] = 1000137  # DED
    if notification["sender_id"] == 2902:
        notification["sender_id"] = 1000125  # Concord
    elif notification["sender_id"] == 1011:
        notification["sender_id"] = 3004029
    elif notification["sender_id"] == 2022:
        notification["sender_id"] = 1000127  # Guristas
    elif notification["sender_id"] == 3001:
        notification["sender_id"] = 99010298
    notification["text"] = notification["text"].replace(
        "1000000000001", str(structure.id)
    )
    notification["text"] = notification["text"].replace(
        "35835", str(structure.eve_type_id)
    )
    notification["text"] = notification["text"].replace(
        "35835", str(structure.eve_type_id)
    )
    notification["text"] = notification["text"].replace(
        "30002537", str(structure.eve_solar_system_id)
    )
    notification["text"] = notification["text"].replace("1001", "3004037")
    notification["text"] = notification["text"].replace("1002", "3019491")
    notification["text"] = notification["text"].replace("1011", "3004029")
    notification["text"] = notification["text"].replace("2001", "98394960")
    notification["text"] = notification["text"].replace(
        "2002", "1000134"
    )  # Blood Raiders
    notification["text"] = notification["text"].replace("3001", "99005502")
    notification["text"] = notification["text"].replace("3002", "99009333")
    notification["text"] = notification["text"].replace("3011", "1354830081")

with transaction.atomic():
    timestamp_start = now() - timedelta(hours=2)
    for notification in notifications:
        if notification["sender_type"] != "other":
            continue

        sender, _ = EveEntity.objects.get_or_create_esi(id=notification["sender_id"])
        text = notification["text"] if "text" in notification else None
        is_read = notification["is_read"] if "is_read" in notification else None
        timestamp_start = timestamp_start + timedelta(minutes=5)
        obj = Notification.objects.update_or_create(
            notification_id=notification["notification_id"],
            owner=owner,
            defaults={
                "sender": sender,
                "timestamp": timestamp_start,
                "notif_type": notification["type"],
                "text": text,
                "is_read": is_read,
                "last_updated": now(),
                "is_sent": False,
            },
        )

print("DONE")


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
