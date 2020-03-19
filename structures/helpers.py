import logging
from time import sleep

from bravado.exception import HTTPBadRequest

from django.conf import settings
from allianceauth.eveonline.providers import provider

from . import __title__
from .utils import LoggerAddTag


logger = LoggerAddTag(logging.getLogger(__name__), __title__)


class EsiHelper:
    """Helper class providing smarter ESI requests with django-esi"""

    _ESI_MAX_RETRIES = 3
    _ESI_SLEEP_SECONDS_ON_RETRY = 1

    @classmethod
    def fetch_esi_object(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,
        esi_client: object = None
    ) -> dict:
        response, _ = cls._fetch_esi_object_with_retries(
            esi_path=esi_path,
            args=args,
            add_prefix=add_prefix,
            esi_client=esi_client
        )
        return response

    @classmethod
    def _fetch_esi_object_with_retries(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,
        has_pages: bool = False,
        page: int = None,
        pages: int = None,        
        esi_client: object = None
    ) -> tuple:
        """Returns object from ESI, retries on bad requests"""
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
        if page and pages:
            log_message_base += ' - Page {}/{}'.format(page, pages)
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
                    data, response = operation.result()
                    if 'x-pages' in response.headers:
                        pages = int(response.headers['x-pages'])
                    else:
                        pages = 0
                else:
                    data = operation.result()
                    pages = 0
                break

            except HTTPBadRequest as ex:                    
                logger.warn(add_prefix(
                    'HTTP error while trying to '
                    'fetch data from ESI: {}'.format(ex)
                ))
                if retry_count < cls._ESI_MAX_RETRIES:
                    sleep(cls._ESI_SLEEP_SECONDS_ON_RETRY)
                else:
                    raise ex

        return data, pages

    @classmethod
    def fetch_esi_objects_smart(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,
        has_localization: bool = False,        
        esi_client: object = None
    ) -> dict:
        """returns dict of eve data objects from ESI
        will contain one full object items for each language if supported or just one
        will retry on bad request responses from ESI
        """
        from .models.eveuniverse import EsiNameLocalization

        if has_localization:
            languages = EsiNameLocalization.ESI_LANGUAGES
        else:
            languages = {EsiNameLocalization.ESI_DEFAULT_LANGUAGE}

        eve_data_objects = dict()
        for language in languages:            
            if has_localization:
                args['language'] = language

            eve_data_objects[language] = cls.fetch_esi_object(
                esi_path, args, add_prefix, esi_client
            )
            
        return eve_data_objects

    @classmethod
    def fetch_esi_objects_with_pages(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,        
        has_pages: bool = False,
        esi_client: object = None
    ) -> dict:
        """fetches esi objects incl. all pages"""
        
        data, pages = cls._fetch_esi_object_with_retries(
            esi_path=esi_path, 
            args=args, 
            add_prefix=add_prefix,
            has_pages=has_pages, 
            esi_client=esi_client
        )        
        for page in range(2, pages + 1):            
            args['page'] = page
            data_page, _ = cls._fetch_esi_object_with_retries(
                esi_path=esi_path, 
                args=args, 
                add_prefix=add_prefix,                
                has_pages=has_pages,
                page=page,
                pages=pages,
                esi_client=esi_client
            )  
            data += data_page

        return data
