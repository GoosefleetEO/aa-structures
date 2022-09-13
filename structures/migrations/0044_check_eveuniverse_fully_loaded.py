"""This custom migration ensures that all eveuniverse objects exist in the database,
which are needed in the next migration.
"""

from django.db import migrations


def ensure_eveuniverse_objects_exist(apps, schema_editor):
    models_map = [
        ("Notification", "sender", "EveEntity"),
        ("StarbaseDetailFuel", "eve_type", "EveType"),
        ("Structure", "eve_moon", "EveMoon"),
        ("Structure", "eve_planet", "EvePlanet"),
        ("Structure", "eve_solar_system", "EveSolarSystem"),
        ("Structure", "eve_type", "EveType"),
        ("StructureItem", "eve_type", "EveType"),
    ]
    for structures_model_name, structures_field, eveuniverse_model_name in models_map:
        StructuresModel = apps.get_model("structures", structures_model_name)
        needed_ids = {
            value
            for value in StructuresModel.objects.values_list(
                f"{structures_field}_id", flat=True
            )
            if value is not None
        }
        EveUniverseModel = apps.get_model("eveuniverse", eveuniverse_model_name)
        existing_ids = set(EveUniverseModel.objects.values_list("id", flat=True))
        if not needed_ids.issubset(existing_ids):
            missing_ids = needed_ids.difference(existing_ids)
            raise RuntimeError(
                "Migration to 2.x can not proceed, because you are missing "
                f"Eveuniverse objects for {StructuresModel.__name__}.{structures_field} "
                "in your database. "
                "Please run the structures_preload_eveuniverse command "
                "to load those missing objects as instructed in the update notes. "
                "Then retry to migrate. "
                f"Missing ids are: {missing_ids}"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0043_remove_services_localization"),
    ]

    operations = [
        migrations.RunPython(
            ensure_eveuniverse_objects_exist, migrations.RunPython.noop
        ),
    ]
