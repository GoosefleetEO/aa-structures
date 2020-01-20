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
        x = StructureTag(
            name='Super cool tag'
        )
        self.assertEqual(str(x), 'Super cool tag')

    def test_html_default(self):
        x = StructureTag(
            name='Super cool tag'
        )
        self.assertEqual(
            x.html, 
            '<span class="label label-default">Super cool tag</span>'
        )

    def test_html_primary(self):
        x = StructureTag(
            name='Super cool tag',
            style='primary'
        )
        self.assertEqual(
            x.html, 
            '<span class="label label-primary">Super cool tag</span>'
        )
