import socket
from datetime import timedelta
import logging
import os

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User, Permission
from django.contrib.messages.constants import DEBUG, ERROR, SUCCESS, WARNING, INFO
from django.contrib import messages
from django.db.models import Q
from django.test import TestCase
from django.utils.functional import lazy
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _

from allianceauth.notifications import notify


# Format for output of datetime for this app
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

format_html_lazy = lazy(format_html, str)


class LoggerAddTag(logging.LoggerAdapter):
    """add custom tag to a logger"""

    def __init__(self, logger, prefix):
        super(LoggerAddTag, self).__init__(logger, {})
        self.prefix = prefix

    def process(self, msg, kwargs):
        return "[%s] %s" % (self.prefix, msg), kwargs


logger = LoggerAddTag(logging.getLogger(__name__), __package__)


def get_swagger_spec_path() -> str:
    """returns the path to the current swagger spec file"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "swagger.json")


def make_logger_prefix(tag: str):
    """creates a function to add logger prefix, which returns tag when used empty"""
    return lambda text="": "{}{}".format(tag, (": " + text) if text else "")


class messages_plus:
    """Pendant to Django messages adding level icons and HTML support

    Careful: Use with safe strings only
    """

    _glyph_map = {
        DEBUG: "eye-open",
        INFO: "info-sign",
        SUCCESS: "ok-sign",
        WARNING: "exclamation-sign",
        ERROR: "alert",
    }

    @classmethod
    def _add_messages_icon(cls, level: int, message: str) -> str:
        """Adds an level based icon to standard Django messages"""
        if level not in cls._glyph_map:
            raise ValueError("glyph for level not defined")
        else:
            glyph = cls._glyph_map[level]

        return format_html(
            '<span class="glyphicon glyphicon-{}" '
            'aria-hidden="true"></span>&nbsp;&nbsp;{}',
            glyph,
            message,
        )

    @classmethod
    def debug(
        cls,
        request: object,
        message: str,
        extra_tags: str = "",
        fail_silently: bool = False,
    ):
        messages.debug(
            request, cls._add_messages_icon(DEBUG, message), extra_tags, fail_silently
        )

    @classmethod
    def info(
        cls,
        request: object,
        message: str,
        extra_tags: str = "",
        fail_silently: bool = False,
    ):
        messages.info(
            request, cls._add_messages_icon(INFO, message), extra_tags, fail_silently
        )

    @classmethod
    def success(
        cls,
        request: object,
        message: str,
        extra_tags: str = "",
        fail_silently: bool = False,
    ):
        messages.success(
            request, cls._add_messages_icon(SUCCESS, message), extra_tags, fail_silently
        )

    @classmethod
    def warning(
        cls,
        request: object,
        message: str,
        extra_tags: str = "",
        fail_silently: bool = False,
    ):
        messages.warning(
            request, cls._add_messages_icon(WARNING, message), extra_tags, fail_silently
        )

    @classmethod
    def error(
        cls,
        request: object,
        message: str,
        extra_tags: str = "",
        fail_silently: bool = False,
    ):
        messages.error(
            request, cls._add_messages_icon(ERROR, message), extra_tags, fail_silently
        )


def notify_admins(message: str, title: str, level="info") -> None:
    """send notification to all admins"""
    try:
        perm = Permission.objects.get(codename="logging_notifications")
        users = User.objects.filter(
            Q(groups__permissions=perm)
            | Q(user_permissions=perm)
            | Q(is_superuser=True)
        ).distinct()

        for user in users:
            notify(user, title=title, message=message, level=level)
    except Permission.DoesNotExist:
        pass


def chunks(lst, size):
    """Yield successive sized chunks from lst."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def clean_setting(
    name: str,
    default_value: object,
    min_value: int = None,
    max_value: int = None,
    required_type: type = None,
):
    """cleans the input for a custom setting

    Will use `default_value` if settings does not exit or has the wrong type
    or is outside define boundaries (for int only)

    Need to define `required_type` if `default_value` is `None`

    Will assume `min_value` of 0 for int (can be overriden)

    Returns cleaned value for setting
    """
    if default_value is None and not required_type:
        raise ValueError("You must specify a required_type for None defaults")

    if not required_type:
        required_type = type(default_value)

    if min_value is None and required_type == int:
        min_value = 0

    if not hasattr(settings, name):
        cleaned_value = default_value
    else:
        if (
            isinstance(getattr(settings, name), required_type)
            and (min_value is None or getattr(settings, name) >= min_value)
            and (max_value is None or getattr(settings, name) <= max_value)
        ):
            cleaned_value = getattr(settings, name)
        else:
            logger.warn(
                "You setting for {} it not valid. Please correct it. "
                "Using default for now: {}".format(name, default_value)
            )
            cleaned_value = default_value
    return cleaned_value


def set_test_logger(logger_name: str, name: str) -> object:
    """set logger for current test module
    
    Args:
    - logger: current logger object
    - name: name of current module, e.g. __file__
    
    Returns:
    - amended logger
    """

    # reconfigure logger so we get logging from tested module
    f_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s"
    )
    f_handler = logging.FileHandler("{}.log".format(os.path.splitext(name)[0]), "w+")
    f_handler.setFormatter(f_format)
    logger = logging.getLogger(logger_name)
    logger.level = logging.DEBUG
    logger.addHandler(f_handler)
    logger.propagate = False
    return logger


def timeuntil_str(duration: timedelta, show_seconds=True) -> str:
    """return the duration as nicely formatted string. 
    Or empty string if duration is negative. 
    
    Format: '[[[999y] [99m]] 99d] 99h 99m 99s'
    """
    seconds = int(duration.total_seconds())
    if seconds > 0:
        periods = [
            # Translators: Abbreviation for years
            (_("y"), 60 * 60 * 24 * 365, False, True),
            # Translators: Abbreviation for months
            (_("mt"), 60 * 60 * 24 * 30, False, True),
            # Translators: Abbreviation for days
            (_("d"), 60 * 60 * 24, False, True),
            # Translators: Abbreviation for hours
            (_("h"), 60 * 60, True, True),
            # Translators: Abbreviation for months
            (_("m"), 60, True, True),
            # Translators: Abbreviation for seconds
            (_("s"), 1, True, show_seconds),
        ]
        strings = list()
        for period_name, period_seconds, period_static, show in periods:
            if seconds >= period_seconds or period_static:
                period_value, seconds = divmod(seconds, period_seconds)
                if show:
                    strings.append("{}{}".format(period_value, period_name))

        result = " ".join(strings)
    else:
        result = ""

    return result


class SocketAccessError(Exception):
    pass


class NoSocketsTestCase(TestCase):
    """Variation of TestCase class that prevents any use of sockets"""

    @classmethod
    def setUpClass(cls):
        cls.socket_original = socket.socket
        socket.socket = cls.guard
        return super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        socket.socket = cls.socket_original
        return super().tearDownClass()

    @staticmethod
    def guard(*args, **kwargs):
        raise SocketAccessError("Attempted to access network")


def app_labels() -> set:
    """returns set of all current app labels"""
    return {x for x in apps.app_configs.keys()}


def add_no_wrap_html(text: str) -> str:
    """add no-wrap HTML to text"""
    return format_html('<span style="white-space: nowrap;">{}</span>', mark_safe(text))


def create_bs_label_html(text: str, style: str) -> str:
    """create Bootstrap label and return HTML"""
    return format_html('<span class="label label-{}">{}</span>', style, text)


def yesno_str(value: bool) -> str:
    """returns yes/no for boolean else empty string and with localization"""
    if value is True:
        return _("yes")
    elif value is False:
        return _("no")
    else:
        return ""
