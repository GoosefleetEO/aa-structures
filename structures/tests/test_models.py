from unittest.mock import Mock, patch

from django.test import TestCase

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo

from . import set_logger
from ..models import Owner, StructureTag


logger = set_logger('structures.views', __file__)

class TestOwner(TestCase):

    def test_to_friendly_error_message(self):
        
        #normal error
        self.assertEqual(
            Owner.to_friendly_error_message(Owner.ERROR_NO_CHARACTER), 
            'No character set for fetching data from ESI'
        )

        #normal error
        self.assertEqual(
            Owner.to_friendly_error_message(0), 
            'No error'
        )

        #undefined error
        self.assertEqual(
            Owner.to_friendly_error_message(9876), 
            'Undefined error'
        )

        #undefined error
        self.assertEqual(
            Owner.to_friendly_error_message(-1), 
            'Undefined error'
        )


class TestStructureTag(TestCase):

    def test_str(self):
        tag_name = 'Super cool tag'
        x = StructureTag(
            name=tag_name
        )
        self.assertEqual(str(x), tag_name)
