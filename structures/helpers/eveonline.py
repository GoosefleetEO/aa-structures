import datetime as dt
import pytz


def ldap_datetime_2_dt(ldap_dt: int) -> dt.datetime:
    """converts ldap time to datatime"""
    return pytz.utc.localize(
        dt.datetime.utcfromtimestamp((ldap_dt / 10000000) - 11644473600)
    )


def ldap_timedelta_2_timedelta(ldap_td: int) -> dt.timedelta:
    """converts a ldap timedelta into a dt timedelta"""
    return dt.timedelta(microseconds=ldap_td / 10)
