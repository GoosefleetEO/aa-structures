# flake8: noqa
"""scripts generates large amount of random structures for load testing"""

import inspect
import os
import sys

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
myauth_dir = (
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(currentdir))))
    + "/myauth"
)
sys.path.insert(0, myauth_dir)

from datetime import timedelta
from random import randrange

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

from allianceauth.eveonline.models import EveAllianceInfo, EveCorporationInfo

from structures.models import (
    EveSolarSystem,
    EveType,
    Owner,
    Structure,
    StructureService,
    StructureTag,
)

# TODO: Add data for assets, e.g. fittings

print(
    "generate_structure - "
    "scripts generates large amount of random structures for load testing "
)

amount = 20

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
    98013740,
]
structure_type_ids = [35825, 35826, 35827, 35832, 35832, 35834, 35835, 35836]
solar_system_ids = [30000142, 30001445, 30002355, 30004046, 30003833, 30045338]
services = [
    "Clone Bay",
    "Moondrilling",
    "Reprocessing",
    "Market Hub",
    "Manufacturing (Standard)",
    "Blueprint Copying",
    "Material Efficiency Research",
    "Time Efficiency Research",
]
tag_names = [
    "Top Secret",
    "Priority",
    "Trash",
    "Needs caretaker",
    "Taskforce Bravo",
    "Not so friendly",
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


print("Connecting to ESI ...")
client = esi_client_factory()

# generating data
print("Creating base data ...")
owners = list()
for corporation_id in corporation_ids:
    try:
        corporation = client.Corporation.get_corporations_corporation_id(
            corporation_id=corporation_id
        ).result()
        try:
            EveAllianceInfo.objects.get(alliance_id=corporation["alliance_id"])
        except EveAllianceInfo.DoesNotExist:
            EveAllianceInfo.objects.create_alliance(corporation["alliance_id"])
    except Exception:
        pass

    try:
        corporation = EveCorporationInfo.objects.get(corporation_id=corporation_id)
    except EveCorporationInfo.DoesNotExist:
        corporation = EveCorporationInfo.objects.create_corporation(corporation_id)

    owner, _ = Owner.objects.get_or_create(corporation=corporation)
    owners.append(owner)

eve_types = list()
for type_id in structure_type_ids:
    eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
    eve_types.append(eve_type)

eve_solar_systems = list()
for system_id in solar_system_ids:
    eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(id=system_id)
    eve_solar_systems.append(eve_solar_system)

tags = list()
for name in tag_names:
    tag, _ = StructureTag.objects.update_or_create(
        name=name,
        defaults={"style": get_random([x[0] for x in StructureTag.Style.choices])},
    )
    tags.append(tag)

# creating structures
print("Creating {} structures ...".format(amount))
Structure.objects.filter(owner__in=owners).delete()
with transaction.atomic():
    for i in range(1, amount + 1):
        state = get_random(
            [
                Structure.State.SHIELD_VULNERABLE,
                Structure.State.SHIELD_VULNERABLE,
                Structure.State.SHIELD_VULNERABLE,
                Structure.State.SHIELD_VULNERABLE,
                Structure.State.SHIELD_VULNERABLE,
                Structure.State.SHIELD_VULNERABLE,
                Structure.State.ARMOR_REINFORCE,
                Structure.State.HULL_REINFORCE,
            ]
        )
        is_low_power = (
            get_random([True, False]) or state == Structure.State.HULL_REINFORCE
        )

        unanchors_at = None

        if not is_low_power:
            fuel_expires_at = now() + timedelta(days=randrange(14), hours=randrange(12))
            last_online_at = now()
            if randrange(1, 10) == 1:
                unanchors_at = now() + timedelta(days=randrange(6), hours=randrange(12))
        else:
            fuel_expires_at = None
            last_online_at = now() - timedelta(days=get_random([1, 2, 3, 10]))
        structure = Structure.objects.create(
            id=1000000000001 + i,
            owner=get_random(owners),
            eve_type=get_random(eve_types),
            name="Generated structure #{:05d}".format(i),
            eve_solar_system=get_random(eve_solar_systems),
            reinforce_hour=randrange(24),
            state=state,
            fuel_expires_at=fuel_expires_at,
            last_online_at=last_online_at,
            unanchors_at=unanchors_at,
        )
        if is_low_power:
            state = StructureService.State.OFFLINE
        else:
            state = StructureService.State.ONLINE
        for name in get_random_subset(services, 3):
            StructureService.objects.create(structure=structure, name=name, state=state)
        structure.tags.add(*get_random_subset(tags))
        if structure.is_reinforced:
            state_timer_start = now() - timedelta(
                days=randrange(3), hours=randrange(12)
            )
            state_timer_end = now() + timedelta(days=randrange(3), hours=randrange(12))
            structure.state_timer_start = state_timer_start
            structure.state_timer_end = state_timer_end

        structure.save()

print("DONE")
