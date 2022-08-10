from app_utils.testing import NoSocketsTestCase

from ..testdata.factories_2 import StructuresNotificationFactory


class TestStructuresNotification(NoSocketsTestCase):
    def test_should_have_str(self):
        # given
        notif = StructuresNotificationFactory()
        # when/then
        self.assertTrue(str(notif))
        print(notif.owner.webhooks.first())
