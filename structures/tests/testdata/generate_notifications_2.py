# flake8: noqa
"""Script for creating generated notifications for testing."""

import os
import sys
from pathlib import Path

myauth_dir = Path(__file__).parent.parent.parent.parent.parent / "myauth"
sys.path.insert(0, str(myauth_dir))

import django
from django.apps import apps

# init and setup django project
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
django.setup()

"""MAIN"""
import datetime as dt

from django.utils.timezone import now

from allianceauth.eveonline.models import EveCorporationInfo

from structures.models import Owner, Structure, Webhook  # noqa: E402, E501
from structures.tests.testdata.factories_2 import (
    GeneratedNotificationFactory,
    StarbaseFactory,
)

# corporation the notifications will be generated for
CORPORATION_ID = 1000127  # Guristas

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

reinforced_until = now() + dt.timedelta(hours=24)
structure = StarbaseFactory(
    owner=owner,
    state=Structure.State.POS_REINFORCED,
    state_timer_end=reinforced_until,
)
print(f"Created new starbase: {structure}")
notif = GeneratedNotificationFactory(structure=structure)
print(f"Created new generated notification: {notif}")
