"""scripts generates large amount of random structures for load testing"""

import os
import sys
import inspect

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(
    inspect.currentframe()
)))
myauth_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(currentdir)))
) + "/myauth"
sys.path.insert(0, myauth_dir)

from datetime import timedelta  # noqa: E402
from random import randrange    # noqa: E402

import django   # noqa: E402
from django.db import transaction   # noqa: E402
from django.apps import apps    # noqa: E402
from django.utils.timezone import now   # noqa: E402

# init and setup django project
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
django.setup()

if not apps.is_installed('structures'):
    raise RuntimeError("The app structures is not installed")    

from allianceauth.eveonline.models import EveCorporationInfo, \
    EveAllianceInfo     # noqa: E402
from esi.clients import esi_client_factory  # noqa: E402

from structures.models import (
    Structure, Owner, EveType, EveSolarSystem, StructureTag, StructureService
)     # noqa: E402

print(
    'generate_structure - '
    'scripts generates large amount of random structures for load testing '
)

amount = 50

# random pick of most active corporations on zKillboard in Jan 2020
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
tag_names = [
    'Top Secret',
    'Priority',
    'Trash',
    'Needs caretaker',
    'Taskforce Bravo',
    'Not so friendly'
]


def get_random(lst: list) -> object:
    return lst[randrange(len(lst))] 


def get_random_subset(lst: list, max_members: int = None) -> list:
    lst2 = lst.copy()
    subset = list()
    if not max_members:
        max_members = len(lst)
    else:
        max_members = min(max_members, len(lst))

    for x in range(randrange(max_members) + 1):
        m = lst2.pop(randrange(len(lst2)))
        subset.append(m)

    return subset


print('Connecting to ESI ...')
client = esi_client_factory()

# generating data
print('Creating base data ...')
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
    except Exception:
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

tags = list()
for name in tag_names:
    tag, _ = StructureTag.objects.update_or_create(
        name=name,
        defaults={
            'style': get_random([x[0] for x in StructureTag.STYLE_CHOICES])
        }
    )
    tags.append(tag)

# creating structures
print('Creating {} structures ...'.format(amount))
Structure.objects.filter(owner__in=owners).delete()
with transaction.atomic(): 
    for i in range(1, amount + 1):                        
        state = get_random([
            Structure.STATE_SHIELD_VULNERABLE,
            Structure.STATE_SHIELD_VULNERABLE,
            Structure.STATE_SHIELD_VULNERABLE,
            Structure.STATE_SHIELD_VULNERABLE,
            Structure.STATE_SHIELD_VULNERABLE,
            Structure.STATE_SHIELD_VULNERABLE,            
            Structure.STATE_ARMOR_REINFORCE,
            Structure.STATE_HULL_REINFORCE
        ])        
        is_low_power = get_random([True, False]) \
            or state == Structure.STATE_HULL_REINFORCE

        if not is_low_power:
            fuel_expires = \
                now() + timedelta(days=randrange(14), hours=randrange(12))
        else:
            fuel_expires = None
        structure = Structure.objects.create(
            id=1000000000001 + i,
            owner=get_random(owners),
            eve_type=get_random(eve_types),
            name='Generated structure #{:05d}'.format(i),
            eve_solar_system=get_random(eve_solar_systems), 
            reinforce_hour=randrange(24),
            state=state,
            fuel_expires=fuel_expires
        )
        if is_low_power:
            state = StructureService.STATE_OFFLINE
        else:
            state = StructureService.STATE_ONLINE
        for name in get_random_subset(services, 3):            
            StructureService.objects.create(
                structure=structure,
                name=name,
                state=state
            )        
        structure.tags.add(*get_random_subset(tags))        
        if structure.is_reinforced:
            state_timer_start = \
                now() - timedelta(days=randrange(3), hours=randrange(12))
            state_timer_end = \
                now() + timedelta(days=randrange(3), hours=randrange(12))
            structure.state_timer_start = state_timer_start
            structure.state_timer_end = state_timer_end

        structure.save()        

print('DONE')
