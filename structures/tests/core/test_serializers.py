from typing import List

from django.test import RequestFactory

from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from ...core.serializers import PocoListSerializer, StructureListSerializer
from ...models import Structure
from ..testdata.factories import (
    create_owner_from_user,
    create_poco,
    create_starbase,
    create_upwell_structure,
)
from ..testdata.helpers import load_entities
from ..testdata.load_eveuniverse import load_eveuniverse


def to_dict(lst: List[dict], key="id"):
    return {obj[key]: obj for obj in lst}


class TestStructureListSerializer(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()
        load_eveuniverse()
        cls.user, _ = create_user_from_evecharacter(1001)
        cls.owner = create_owner_from_user(cls.user)
        cls.request = cls.factory.get("/")
        cls.request.user = cls.user

    def test_should_show_not_reinforced_for_structure(self):
        # given
        structure = create_upwell_structure(owner=self.owner)
        # when
        data = StructureListSerializer(
            queryset=Structure.objects.all(), request=self.request
        ).to_list()
        # then
        obj = to_dict(data)[structure.id]
        self.assertFalse(obj["is_reinforced"])

    def test_should_show_reinforced_for_structure(self):
        # given
        structure = create_upwell_structure(
            owner=self.owner, state=Structure.State.ARMOR_REINFORCE
        )
        # when
        data = StructureListSerializer(
            queryset=Structure.objects.all(), request=self.request
        ).to_list()
        # then
        obj = to_dict(data)[structure.id]
        self.assertTrue(obj["is_reinforced"])

    def test_should_show_not_reinforced_for_starbase(self):
        # given
        structure = create_starbase(owner=self.owner)
        # when
        data = StructureListSerializer(
            queryset=Structure.objects.all(), request=self.request
        ).to_list()
        # then
        obj = to_dict(data)[structure.id]
        self.assertFalse(obj["is_reinforced"])

    def test_should_show_reinforced_for_starbase(self):
        # given
        structure = create_starbase(
            owner=self.owner, state=Structure.State.POS_REINFORCED
        )
        # when
        data = StructureListSerializer(
            queryset=Structure.objects.all(), request=self.request
        ).to_list()
        # then
        obj = to_dict(data)[structure.id]
        self.assertTrue(obj["is_reinforced"])


class TestPocoListSerializer(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()
        load_eveuniverse()
        cls.user, _ = create_user_from_evecharacter(1001)
        cls.owner = create_owner_from_user(cls.user)
        cls.request = cls.factory.get("/")
        cls.request.user = cls.user

    def test_should_extract_planet_type(self):
        # given
        structure = create_poco(owner=self.owner)
        # when
        data = PocoListSerializer(
            queryset=Structure.objects.all(), request=self.request
        ).to_list()
        # then
        obj = to_dict(data)[structure.id]
        self.assertEqual(obj["planet_type_name"], "Barren")
