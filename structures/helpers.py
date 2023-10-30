"""Helpers for Structures."""

import datetime as dt
from typing import Any, Optional
from urllib.parse import urlparse

from django.utils.timezone import now


def hours_until_deadline(
    deadline: dt.datetime, start: Optional[dt.datetime] = None
) -> float:
    """Currently remaining hours until a given deadline."""
    if not isinstance(deadline, dt.datetime):
        raise TypeError("deadline must be of type datetime")
    if not start:
        start = now()
    return (deadline - start).total_seconds() / 3600


def datetime_almost_equal(
    first: Optional[dt.datetime], second: Optional[dt.datetime], threshold: int
) -> bool:
    """True when first and second datetime are within threshold in seconds.
    False when first or second is None.
    """
    if not first or not second:
        return False
    dif = abs((first - second).total_seconds())
    return dif <= abs(threshold)


def is_absolute_url(url: str) -> bool:
    """Return True if URL is absolute else False."""
    return bool(urlparse(url).netloc)


def get_or_create_esi_obj(model_class: type, *args, **kwargs) -> Any:
    """Get or create an object from ESI and return it."""
    obj, _ = model_class.objects.get_or_create_esi(*args, **kwargs)
    return obj
