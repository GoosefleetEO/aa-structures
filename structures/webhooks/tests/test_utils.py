import json

from django.test import TestCase
from django.utils.timezone import now

from app_utils.json import JSONDateTimeDecoder, JSONDateTimeEncoder


class TestJsonSerializer(TestCase):
    def test_encode_decode(self):
        my_dict = {"alpha": "hello", "bravo": now()}
        my_json = json.dumps(my_dict, cls=JSONDateTimeEncoder)
        my_dict_new = json.loads(my_json, cls=JSONDateTimeDecoder)
        self.assertDictEqual(my_dict, my_dict_new)
