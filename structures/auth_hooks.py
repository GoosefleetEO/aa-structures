from django.utils.translation import ugettext_lazy as _

from allianceauth.services.hooks import MenuItemHook, UrlHook
from allianceauth import hooks

from . import urls


class StructuresMenuItem(MenuItemHook):
    """ This class ensures only authorized users will see the menu entry """
    def __init__(self):
        # setup menu entry for sidebar
        MenuItemHook.__init__(
            self,
            _('Alliance Structures'),
            'fa fa-building fa-fw',
            'structures:index',
            navactive=['structures:index']
        )

    def render(self, request):
        if request.user.has_perm('structures.basic_access'):
            return MenuItemHook.render(self, request)
        return ''


@hooks.register('menu_item_hook')
def register_menu():
    return StructuresMenuItem()


@hooks.register('url_hook')
def register_urls():
    return UrlHook(urls, 'structures', r'^structures/')