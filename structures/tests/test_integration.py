from unittest.mock import patch

from django.test import TestCase, override_settings

from app_utils.esi_testing import EsiClientStub, EsiEndpoint

from .. import tasks
from .testdata.factories_2 import (
    StructureFactory,
    StructureWentHighPowerEsiNotificationFactory,
)
from .testdata.helpers import load_eveuniverse

OWNERS_PATH = "structures.models.owners"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch("structures.webhooks.core.dhooks_lite.Webhook.execute", spec=True)
@patch(OWNERS_PATH + ".esi")
class TestTasksEnd2End(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_send_new_notification_received_from_esi(
        self, mock_esi, mock_execute
    ):
        # given
        structure = StructureFactory()
        owner = structure.owner
        eve_character = owner.characters.first().character_ownership.character
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_notifications",
                "character_id",
                needs_token=True,
                data={
                    str(eve_character.character_id): [
                        StructureWentHighPowerEsiNotificationFactory(
                            structure=structure
                        )
                    ]
                },
            )
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when
        tasks.fetch_all_notifications()
        # then
        self.assertTrue(mock_execute.called)
