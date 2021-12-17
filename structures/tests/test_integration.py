# import datetime as dt
# from unittest.mock import patch

# from django.test import TestCase, override_settings
# from django.utils.timezone import now

# from .. import constants, tasks
# from ..models import FuelAlertConfig, JumpFuelAlertConfig, Structure, Webhook
# from .testdata import create_structures, load_notification_entities, set_owner_character


# @override_settings(CELERY_ALWAYS_EAGER=True)
# @patch("structures.webhooks.core.dhooks_lite.Webhook", autospec=True)
# class TestFuelNotifications(TestCase):
#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()
#         create_structures()
#         _, cls.owner = set_owner_character(character_id=1001)
#         load_notification_entities(cls.owner)
#         cls.webhook = Webhook.objects.get(name="Test Webhook 1")

#     def test_should_send_structure_fuel_alert(self, mock_Webhook):
#         # given
#         config = FuelAlertConfig.objects.create(start=48, end=0, repeat=12)
#         structure = Structure.objects.get(id=1000000000001)
#         structure.fuel_expires_at = now() + dt.timedelta(hours=25)
#         structure.save()
#         # when
#         tasks.send_structure_fuel_notifications_for_config.delay(config.pk)
#         # then
#         self.assertTrue(mock_Webhook.return_value.execute.called)

#     def test_should_send_jump_fuel_alert(self, mock_Webhook):
#         # given
#         config = JumpFuelAlertConfig.objects.create(threshold=100)
#         structure = Structure.objects.get(id=1000000000004)
#         structure.items.create(
#             id=1,
#             eve_type_id=constants.EveTypeId.LIQUID_OZONE,
#             location_flag="StructureFuel",
#             is_singleton=False,
#             quantity=99,
#         )
#         # when
#         tasks.send_jump_fuel_notifications_for_config.delay(config.pk)
#         # then
#         self.assertTrue(mock_Webhook.return_value.execute.called)
