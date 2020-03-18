import logging
from time import sleep

from bravado.exception import HTTPBadRequest

from allianceauth.eveonline.providers import provider

from .utils import LoggerAddTag


logger = LoggerAddTag(logging.getLogger(__name__), __package__)


class EsiSmartRequester:
    """Helper class providing smarter ESI requests with django-esi"""

    _ESI_MAX_RETRIES = 3
    _ESI_SLEEP_SECONDS_ON_RETRY = 1

    @classmethod
    def fetch_esi_object_with_retries(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,
        esi_client: object = None
    ) -> dict:
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
        logger.info(add_prefix('Fetching object from ESI'))
        for retry_count in range(cls._ESI_MAX_RETRIES + 1):
            if retry_count > 0:
                logger.warn(add_prefix(
                    'Fetching data from ESI - Retry {} / {}'.format(
                        retry_count, cls._ESI_MAX_RETRIES
                    )
                ))
            try:                  
                response = \
                    getattr(esi_category, esi_method_name)(**args).result()
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

        return response

    @classmethod
    def fetch_esi_objects_with_localization(
        cls, 
        esi_path: str,         
        args: dict,         
        add_prefix: object,
        has_esi_localization: bool,
        esi_client: object = None
    ) -> dict:
        """returns dict of eve data objects from ESI
        will contain one full object items for each language if supported or just one
        will retry on bad request responses from ESI
        """
        from .models.eveuniverse import EsiNameLocalization

        if has_esi_localization:
            languages = EsiNameLocalization.ESI_LANGUAGES
        else:
            languages = {EsiNameLocalization.ESI_DEFAULT_LANGUAGE}

        eve_data_objects = dict()
        for language in languages:            
            if has_esi_localization:
                args['language'] = language

            eve_data_objects[language] = cls.fetch_esi_object_with_retries(
                esi_path, args, add_prefix, esi_client
            )
            
        return eve_data_objects
