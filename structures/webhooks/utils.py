from datetime import datetime
import json
import logging
from typing import Any

from pytz import timezone


class LoggerAddTag(logging.LoggerAdapter):
    """add custom tag to a logger"""

    def __init__(self, my_logger, prefix):
        super(LoggerAddTag, self).__init__(my_logger, {})
        self.prefix = prefix

    def process(self, msg, kwargs):
        return "[%s] %s" % (self.prefix, msg), kwargs


class JSONDateTimeDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs) -> None:
        json.JSONDecoder.__init__(
            self, object_hook=self.dict_to_object, *args, **kwargs
        )

    def dict_to_object(self, dct: dict) -> object:
        if "__type__" not in dct:
            return dct

        type_str = dct.pop("__type__")
        zone, _ = dct.pop("tz")
        dct["tzinfo"] = timezone(zone)
        try:
            dateobj = datetime(**dct)
            return dateobj
        except (ValueError, TypeError):
            dct["__type__"] = type_str
            return dct


class JSONDateTimeEncoder(json.JSONEncoder):
    """Instead of letting the default encoder convert datetime to string,
    convert datetime objects into a dict, which can be decoded by the
    JSONDateTimeDecoder
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return {
                "__type__": "datetime",
                "year": o.year,
                "month": o.month,
                "day": o.day,
                "hour": o.hour,
                "minute": o.minute,
                "second": o.second,
                "microsecond": o.microsecond,
                "tz": (o.tzinfo.tzname(o), o.utcoffset().total_seconds()),
            }
        else:
            return json.JSONEncoder.default(self, o)
