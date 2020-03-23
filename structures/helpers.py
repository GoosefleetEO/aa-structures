import logging
from time import sleep

from bravado.exception import HTTPBadGateway

from django.conf import settings
from allianceauth.eveonline.providers import provider

from . import __title__
from .utils import LoggerAddTag


logger = LoggerAddTag(logging.getLogger(__name__), __title__)


class EsiSmartRequest:
    """Helper class providing smarter ESI requests with django-esi
    
    Adds these features to all request to ESI:
    - Automatic retry on 502 up to max retries
    - Automatic retrieval of all pages
    - Automatic retrieval of variants for all requested languages
    """

    _ESI_MAX_RETRIES = 3
    _ESI_SLEEP_SECONDS_ON_RETRY = 1

    @classmethod
    def fetch(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,        
        has_pages: bool = False,        
        esi_client: object = None
    ) -> dict:
        """returns an response object from ESI, will retry on bad requests"""
        _, request_object = cls._fetch_with_localization(
            esi_path=esi_path, 
            args=args, 
            add_prefix=add_prefix,
            has_localization=False,
            has_pages=has_pages,                
            esi_client=esi_client
        ).popitem()
        return request_object

    @classmethod
    def fetch_with_localization(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,
        has_localization: bool = False,
        has_pages: bool = False,        
        esi_client: object = None
    ) -> dict:
        """returns dict of response objects from ESI
        will contain one full object items for each language if supported or just one
        will retry on bad request responses from ESI
        will automatically return all pages if requested
        """
        return cls._fetch_with_localization(
            esi_path=esi_path,
            args=args,
            add_prefix=add_prefix,            
            has_localization=has_localization,
            has_pages=has_pages,                
            esi_client=esi_client
        )
    
    @classmethod
    def _fetch_with_localization(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,
        has_localization: bool = False,
        has_pages: bool = False,        
        esi_client: object = None
    ) -> dict:
        """returns dict of response objects from ESI with localization"""
        from .models.eveuniverse import EsiNameLocalization

        if has_localization:
            languages = EsiNameLocalization.ESI_LANGUAGES
        else:
            languages = {EsiNameLocalization.ESI_DEFAULT_LANGUAGE}

        response_objects = dict()
        for language in languages:            
            if has_localization:
                args['language'] = language

            response_objects[language] = cls._fetch_with_paging(
                esi_path=esi_path, 
                args=args, 
                add_prefix=add_prefix,
                has_pages=has_pages,                
                esi_client=esi_client
            )
            
        return response_objects

    @classmethod
    def _fetch_with_paging(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,        
        has_pages: bool = False,        
        esi_client: object = None
    ) -> dict:
        """fetches esi objects incl. all pages if requested and returns them""" 
        response_object, pages = cls._fetch_with_retries(
            esi_path=esi_path, 
            args=args, 
            add_prefix=add_prefix,
            has_pages=has_pages, 
            esi_client=esi_client
        )        
        if has_pages:
            for page in range(2, pages + 1):                        
                response_object_page, _ = cls._fetch_with_retries(
                    esi_path=esi_path, 
                    args=args, 
                    add_prefix=add_prefix,                
                    has_pages=has_pages,
                    page=page,
                    pages=pages,
                    esi_client=esi_client
                )  
                response_object += response_object_page

        return response_object

    @classmethod
    def _fetch_with_retries(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,
        has_pages: bool = False,
        page: int = None,
        pages: int = None,        
        esi_client: object = None
    ) -> tuple:
        """Returns response object and pages from ESI, retries on 502"""
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
            args['page'] = page if page else 1
            log_message_base += ' - Page {}/{}'.format(
                page, pages if pages else '?'
            )
            
        logger.info(add_prefix(log_message_base))
        for retry_count in range(cls._ESI_MAX_RETRIES + 1):
            if retry_count > 0:
                logger.warn(add_prefix(
                    '{} - Retry {} / {}'.format(
                        log_message_base,
                        retry_count, 
                        cls._ESI_MAX_RETRIES
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

            except HTTPBadGateway as ex:                    
                logger.warn(add_prefix(
                    'HTTP error while trying to '
                    'fetch response_object from ESI: {}'.format(ex)
                ))
                if retry_count < cls._ESI_MAX_RETRIES:
                    sleep(cls._ESI_SLEEP_SECONDS_ON_RETRY)
                else:
                    raise ex

        return response_object, pages
