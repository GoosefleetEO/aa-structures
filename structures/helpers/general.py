import datetime as dt

from django.utils.timezone import now


def hours_until_deadline(deadline: dt) -> float:
    """Currently remaining hours until a given deadline."""
    return (deadline - now()).total_seconds() / 3600
