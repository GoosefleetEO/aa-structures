from collections import defaultdict
from copy import copy
from typing import List

from app_utils.esi_testing import EsiClientStub, EsiEndpoint


def create_esi_client_stub(
    endpoints: List[EsiEndpoint], new_endpoints: List[EsiEndpoint] = None, **kwargs
) -> EsiClientStub:
    """Create an esi client stub.

    Args:
    - endpoints: Endpoints defining the stub
    - new_endpoints: Endpoints replacing endpoints defined in "endpoints"

    Returns:
    Esi client stub
    """
    _endpoints = copy(endpoints)
    if new_endpoints:
        _endpoints_mapped = defaultdict(dict)
        for ep in _endpoints:
            _endpoints_mapped[ep.category][ep.method] = ep
        for new_ep in new_endpoints:
            try:
                ep = _endpoints_mapped[new_ep.category][new_ep.method]
            except KeyError:
                continue
            else:
                _endpoints.remove(ep)
                _endpoints.append(new_ep)
    params = {"testdata": None, "endpoints": _endpoints}
    params.update(kwargs)
    return EsiClientStub(**params)
