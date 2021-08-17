import datetime as dt

from django.utils.timezone import now


def hours_until_deadline(deadline: dt) -> float:
    """Currently remaining hours until a given deadline."""
    return (deadline - now()).total_seconds() / 3600


def datetime_almost_equal(
    first: dt.datetime, second: dt.datetime, threshold: int
) -> bool:
    """True when first and second datetime are within threshold in seconds.
    False when first or second is None.
    """
    if not first or not second:
        return False
    dif = abs((first - second).total_seconds())
    return dif <= abs(threshold)
