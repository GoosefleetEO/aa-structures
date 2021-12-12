from django_webtest import WebTest

from allianceauth.tests.auth_utils import AuthUtils

from .testdata import create_structures, set_owner_character


class TestUI(WebTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.user = AuthUtils.add_permission_to_user_by_name(
            "structures.basic_access", cls.user
        )

    def test_should_show_structures_list(self):
        # given
        self.app.set_user(self.user)
        # when
        response = self.app.get("/structures/list")
        # then
        self.assertEqual(response.status_code, 200)
        self.assertInHTML("Structures", response.text)
