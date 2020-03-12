from django.test import TestCase

from allianceauth.tests.auth_utils import AuthUtils

from .auth_utils_2 import AuthUtils2


class TestAddPermissionToUser(TestCase):

    def setUp(self):
        self.user = AuthUtils.create_user('Bruce Wayne')
    
    def test_can_add_permission(self):
        AuthUtils2.add_permission_to_user_by_name(
            'auth.timer_management', self.user
        )
        self.assertTrue(self.user.has_perm('auth.timer_management'))

    def test_raises_exception_on_invalid_permission_format(self):
        with self.assertRaises(ValueError):
            AuthUtils2.add_permission_to_user_by_name(
                'timer_management', self.user
            )
