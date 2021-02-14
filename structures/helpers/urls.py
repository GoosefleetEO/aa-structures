from urllib.parse import urljoin

from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse

from ..utils import get_site_base_url


def static_file_absolute_url(file_path: str) -> str:
    """returns absolute URL to a static file

    Args:
        file_path: relative path to a static file
    """
    return urljoin(get_site_base_url(), staticfiles_storage.url(file_path))


def reverse_absolute(viewname: str) -> str:
    """returns absolute URL for given url"""
    return urljoin(get_site_base_url(), reverse(viewname))
