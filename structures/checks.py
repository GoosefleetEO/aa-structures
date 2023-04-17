from django.core.checks import Critical, Tags, register


@register(Tags.database)
def upgrade_from_1_x_check(app_configs, **kwargs):
    """Ensure users are upgrading to 2.0 first, when coming from 1.x"""
    from packaging.version import Version

    errors = []
    if version_text := _fetch_app_version():
        version = Version(version_text)
        if version.major < 2:
            errors.append(
                Critical(
                    "Direct upgrade from 1.x to 2.x not possible",
                    hint=(
                        "Please first upgrade to 2.0 and make sure to follow "
                        "the special upgrade instructions in the 2.0.0(!) change notes. "
                        "Then you can upgrade to the newest version. "
                        "You can install the 2.0 version with the following command: "
                        "pip install aa-structures==2.0.2"
                    ),
                    id="structures.C001",
                )
            )
    return errors


def _fetch_app_version() -> str:
    """Fetch current version string of the app."""
    try:
        from memberaudit import __version__
    except ImportError:
        return ""
    return __version__
