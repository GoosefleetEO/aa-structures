# scripts generates large amount of random structures for load testing
import os
import sys
import inspect

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
    inspect.currentframe()
)))
myauth_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(currentdir)))) + "/myauth"
sys.path.insert(0, myauth_dir)

import json
import logging
from datetime import datetime
import pytz
from random import randrange

import django
from django.db import transaction
from django.apps import apps
from django.utils.timezone import now

# init and setup django project
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
django.setup()

if not apps.is_installed('structures'):
    raise RuntimeError("The app structures is not installed")    

from allianceauth.eveonline.models import EveCorporationInfo, EveAllianceInfo
from esi.clients import esi_client_factory

from structures.models import *

print('generate_structure - scripts generates large amount of random structures for load testing ')

corporation_ids = [
    98388312, 
    98558506, 
    98370861, 
    98410772, 
    98148549, 
    98431483, 
    667531913, 
    427125032, 
    98514543, 
    98013740
]
structure_type_ids = [
    35825,
    35826,
    35827,    
    35832,
    35832,
    35834,
    35835,
    35836    
]
solar_system_ids = [
    30000142,
    30001445,
    30002355,
    30004046,
    30003833,
    30045338
]
services = [
    'Clone Bay',
    'Moondrilling',
    'Reprocessing',
    'Market Hub',
    'Manufacturing (Standard)',
    'Blueprint Copying',
    'Material Efficiency Research',
    'Time Efficiency Research'
]

def get_random(lst: list) -> object:
    return lst[randrange(len(lst))] 

# create structures
print('Creating base data ...')
print('Connecting to ESI ...')
client = esi_client_factory()

owners = list()
for corporation_id in corporation_ids:
    try:
        corporation = client.Corporation\
            .get_corporations_corporation_id(corporation_id=corporation_id)\
            .result()
        try:
            EveAllianceInfo.objects.get(
                alliance_id=corporation['alliance_id']
            )
        except EveAllianceInfo.DoesNotExist:
            EveAllianceInfo.objects.create_alliance(
                corporation['alliance_id']
            )
    except:
        pass
    
    try:
        corporation = EveCorporationInfo.objects.get(
            corporation_id=corporation_id
        )
    except EveCorporationInfo.DoesNotExist:
        corporation = EveCorporationInfo.objects.create_corporation(
            corporation_id
        )

    owner, _ = Owner.objects.get_or_create(corporation=corporation)
    owners.append(owner)


eve_types = list()
for type_id in structure_type_ids:
    eve_type, _ = EveType.objects.get_or_create_esi(type_id, client)
    eve_types.append(eve_type)
    
eve_solar_systems = list()
for system_id in solar_system_ids:
    eve_solar_system, _ = \
        EveSolarSystem.objects.get_or_create_esi(system_id, client)
    eve_solar_systems.append(eve_solar_system)

last_updated = now()

amount = 10
print('Creating {} structures ...'.format(amount))
Structure.objects.filter(owner__in=owners).delete()
with transaction.atomic(): 
    for i in range(1, amount + 1):                
        structure = Structure.objects.create(
            id=1000000000001 + i,
            owner=get_random(owners),
            eve_type=get_random(eve_types),
            name='Test structure #{:05d}'.format(i),
            eve_solar_system=get_random(eve_solar_systems), 
            reinforce_hour=12,
            state=Structure.STATE_SHIELD_VULNERABLE
        )
        for x in range(randrange(0, 1) + 1):
            StructureService.objects.create(
                structure=structure,
                name=get_random(services),
                state=get_random([
                    StructureService.STATE_ONLINE, 
                    StructureService.STATE_OFFLINE
                ])
            )

print('DONE')