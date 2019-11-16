# scripts generates large amount of random structures for load testing
import os
import sys
import inspect

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
    inspect.currentframe()
)))
myauth_dir = os.path.dirname(os.path.dirname(os.path.dirname(currentdir))) + "/myauth"
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

print('generate_structure - scripts generates large amount of random structures for load testing ')

# create structures
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

print('Connecting to ESI ...')
client = esi_client_factory()
eve_type, _ = EveType.objects.get_or_create_esi(client, 35834)
eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(client, 30000142)
last_updated = now()

amount = 1000
print('Creating {} structures ...'.format(amount))
Structure.objects.filter(owner=owner).delete()
with transaction.atomic(): 
    for i in range(1, amount + 1):
        Structure.objects.create(
            id=1000000000001 + i,
            owner=owner,
            eve_type=eve_type,
            name='Test structure #{:05d}'.format(i),
            eve_solar_system=eve_solar_system,
            position_x=0,
            position_y=0,
            position_z=0,
            profile_id=0,
            reinforce_hour=12,
            state=Structure.STATE_SHIELD_VULNERABLE,
            last_updated=last_updated
        )

print('DONE')