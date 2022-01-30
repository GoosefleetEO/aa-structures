import json
from collections import namedtuple
from copy import deepcopy
from pathlib import Path
from typing import List

from app_utils.esi_testing import EsiClientStub, EsiEndpoint


def load_test_data():
    file_path = Path(__file__).parent / "esi_data.json"
    with file_path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


_esi_data = load_test_data()

_endpoints = [
    EsiEndpoint(
        "Assets",
        "get_corporations_corporation_id_assets",
        "corporation_id",
        needs_token=True,
    ),
    EsiEndpoint(
        "Assets",
        "post_corporations_corporation_id_assets_locations",
        "corporation_id",
        needs_token=True,
    ),
    EsiEndpoint(
        "Assets",
        "post_corporations_corporation_id_assets_names",
        "corporation_id",
        needs_token=True,
    ),
    EsiEndpoint(
        "Character",
        "get_characters_character_id_notifications",
        "character_id",
        needs_token=True,
    ),
    EsiEndpoint(
        "Corporation",
        "get_corporations_corporation_id_structures",
        "corporation_id",
        needs_token=True,
    ),
    EsiEndpoint(
        "Corporation",
        "get_corporations_corporation_id_starbases",
        "corporation_id",
        needs_token=True,
    ),
    EsiEndpoint(
        "Corporation",
        "get_corporations_corporation_id_starbases_starbase_id",
        ("corporation_id", "starbase_id"),
        needs_token=True,
    ),
    EsiEndpoint(
        "Planetary_Interaction",
        "get_corporations_corporation_id_customs_offices",
        "corporation_id",
        needs_token=True,
    ),
    EsiEndpoint(
        "Universe",
        "get_universe_structures_structure_id",
        "structure_id",
        needs_token=True,
    ),
]

EsiEndpointCallback = namedtuple(
    "EsiEndpointCallback", ["category", "method", "callback"]
)


def generate_esi_client_stub(callbacks: list = None, **kwargs) -> EsiClientStub:
    endpoints = deepcopy(_endpoints)
    if callbacks:
        for cb in callbacks:
            for endpoint in _endpoints:
                if endpoint.category == cb.category and endpoint.method == cb.method:
                    new_endpoint = EsiEndpoint(
                        category=endpoint.category,
                        method=endpoint.method,
                        primary_key=endpoint.primary_key,
                        needs_token=endpoint.needs_token,
                        callback=cb.callback,
                    )
                    endpoints.remove(endpoint)
                    endpoints.append(new_endpoint)
    params = {"testdata": _esi_data, "endpoints": endpoints}
    params.update(kwargs)
    return EsiClientStub(**params)


def create_esi_client_stub(endpoints: List[EsiEndpoint], **kwargs) -> EsiClientStub:
    params = {"testdata": _esi_data, "endpoints": endpoints}
    params.update(kwargs)
    return EsiClientStub(**params)


esi_client_stub = EsiClientStub(_esi_data, endpoints=_endpoints)
esi_client_error_stub = EsiClientStub(_esi_data, endpoints=_endpoints, http_error=True)
