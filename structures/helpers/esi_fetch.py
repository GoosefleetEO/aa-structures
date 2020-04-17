"""This module provides helper functions for smarter ESI requests with django-esi
    
    Added features for all ESI requests:
    - Automatic page retry on 502, 503, 504 up to max retries with exponential backoff
    - Automatic retrieval of all pages
    - Automatic retrieval of variants for all requested languages
"""

import logging
from time import sleep

from bravado.exception import HTTPBadGateway
from bravado.exception import HTTPServiceUnavailable
from bravado.exception import HTTPGatewayTimeout

from django.conf import settings

from allianceauth.eveonline.providers import provider
from esi.models import Token

from .. import __title__
from ..utils import LoggerAddTag


logger = LoggerAddTag(logging.getLogger(__name__), __title__)

ESI_MAX_RETRIES = 3
ESI_RETRY_SLEEP_SECS = 1


def esi_fetch(    
    esi_path: str,         
    args: dict,        
    has_pages: bool = False,
    esi_client: object = None,
    token: Token = None,
    logger_tag: str = None
) -> dict:
    """returns an response object from ESI, will retry on bad requests.    
    will automatically return all pages if requested
    """
    _, request_object = _fetch_main(
        esi_path=esi_path, 
        args=args,
        has_pages=has_pages,                
        esi_client=esi_client,
        token=token,
        logger_tag=logger_tag
    ).popitem()
    return request_object


def esi_fetch_with_localization(
    esi_path: str,         
    args: dict,        
    languages: set,
    has_pages: bool = False,
    esi_client: object = None,
    token: Token = None,
    logger_tag: str = None
) -> dict:
    """returns dict of response objects from ESI
    will contain one full object items for each language if supported or just one
    will retry on bad request responses from ESI
    will automatically return all pages if requested
    """
    return _fetch_main(
        esi_path=esi_path,
        args=args,
        languages=languages,
        has_pages=has_pages,                
        esi_client=esi_client,
        token=token,
        logger_tag=logger_tag
    )


def _fetch_main(    
    esi_path: str,         
    args: dict,        
    languages: set = None,
    has_pages: bool = False,        
    esi_client: object = None,
    token: Token = None,
    logger_tag: str = None
) -> dict:
    """returns dict of response objects from ESI with localization"""
            
    if not languages:
        has_localization = False
        languages = {'dummy'}
    else:
        has_localization = True
    
    response_objects = dict()
    for language in languages:
        if has_localization:
            args['language'] = language
        response_objects[language] = _fetch_with_paging(
            esi_path=esi_path, 
            args=args,
            has_pages=has_pages,                
            esi_client=esi_client,
            token=token,
            logger_tag=logger_tag
        )
        
    return response_objects


def _fetch_with_paging(    
    esi_path: str,         
    args: dict,        
    has_pages: bool = False,        
    esi_client: object = None,
    token: Token = None,
    logger_tag: str = None
) -> dict:
    """fetches esi objects incl. all pages if requested and returns them""" 
    response_object, pages = _fetch_with_retries(
        esi_path=esi_path, 
        args=args, 
        has_pages=has_pages, 
        esi_client=esi_client,
        token=token,
        logger_tag=logger_tag
    )        
    if has_pages:
        for page in range(2, pages + 1):                        
            response_object_page, _ = _fetch_with_retries(
                esi_path=esi_path, 
                args=args,
                has_pages=has_pages,
                page=page,
                pages=pages,
                esi_client=esi_client,
                token=token,
                logger_tag=logger_tag
            )  
            response_object += response_object_page

    return response_object


def _fetch_with_retries(
    esi_path: str,         
    args: dict,        
    has_pages: bool = False,
    page: int = None,
    pages: int = None,        
    esi_client: object = None,
    token: Token = None,
    logger_tag: str = None
) -> tuple:
    """Returns response object and pages from ESI, retries on 502s"""
    
    def make_logger_prefix(tag: str = None):
        """creates a function to add logger prefix"""
        return lambda text: '{}{}'.format(
            (tag + ': ') if tag else '', 
            text
        )

    add_prefix = make_logger_prefix(logger_tag)
    esi_path_parts = esi_path.split('.')
    if len(esi_path_parts) != 2:
        raise ValueError('Invalid esi_path')
    esi_category_name = esi_path_parts[0]
    esi_method_name = esi_path_parts[1]
    if not esi_client:
        esi_client = provider.client
    if not hasattr(esi_client, esi_category_name):
        raise ValueError(
            'Invalid ESI category: %s' % esi_category_name
        )
    esi_category = getattr(esi_client, esi_category_name)
    if not hasattr(esi_category, esi_method_name):
        raise ValueError(
            'Invalid ESI method for %s category: %s'
            % (esi_category_name, esi_method_name)
        )              
    log_message_base = 'Fetching from ESI: {}'.format(esi_path)
    if settings.DEBUG:
        log_message_base += '({})'.format(
            ', '.join([str(k) + '=' + str(v) for k, v in args.items()])
        )
    if has_pages:
        if not page:
            page = 1
        args['page'] = page
        log_message_base += ' - Page {}/{}'.format(
            page, pages if pages else '?'
        )
    if token:
        if token.expired:
            token.refresh()
        args['token'] = token.access_token
        
    logger.info(add_prefix(log_message_base))
    for retry_count in range(ESI_MAX_RETRIES + 1):
        if retry_count > 0:
            logger.warn(add_prefix(
                '{} - Retry {} / {}'.format(
                    log_message_base,
                    retry_count, 
                    ESI_MAX_RETRIES
                )
            ))
        try:                  
            operation = getattr(esi_category, esi_method_name)(**args)
            if has_pages:
                operation.also_return_response = True
                response_object, response = operation.result()
                if 'x-pages' in response.headers:
                    pages = int(response.headers['x-pages'])
                else:
                    pages = 0
            else:
                response_object = operation.result()
                pages = 0
            break

        except (HTTPBadGateway, HTTPGatewayTimeout, HTTPServiceUnavailable) as ex:
            logger.warn(add_prefix(
                'HTTP error while trying to '
                'fetch response_object from ESI: {}'.format(ex)
            ))
            if retry_count < ESI_MAX_RETRIES:
                sleep_seconds = (ESI_RETRY_SLEEP_SECS * retry_count) ** 2
                logger.info(add_prefix(
                    'Waiting {} seconds until next retry'.format(sleep_seconds)
                ))
                sleep(sleep_seconds)
            else:
                raise ex

    return response_object, pages