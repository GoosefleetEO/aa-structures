"""Main migration for migraing to eveuniverse."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("eveuniverse", "0007_evetype_description"),
        ("structures", "0044_check_eveuniverse_fully_loaded"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="sender",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="eveuniverse.eveentity",
            ),
        ),
        migrations.AlterField(
            model_name="starbasedetailfuel",
            name="eve_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="eveuniverse.evetype",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="eve_moon",
            field=models.ForeignKey(
                blank=True,
                default=None,
                help_text="Moon next to this structure - if any",
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                to="eveuniverse.evemoon",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="eve_planet",
            field=models.ForeignKey(
                blank=True,
                default=None,
                help_text="Planet next to this structure - if any",
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                to="eveuniverse.eveplanet",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="eve_solar_system",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="eveuniverse.evesolarsystem",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="eve_type",
            field=models.ForeignKey(
                help_text="type of the structure",
                on_delete=django.db.models.deletion.CASCADE,
                to="eveuniverse.evetype",
            ),
        ),
        migrations.AlterField(
            model_name="structureitem",
            name="eve_type",
            field=models.ForeignKey(
                help_text="eve type of the item",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="eveuniverse.evetype",
            ),
        ),
        migrations.DeleteModel(
            name="EveMoon",
        ),
        migrations.DeleteModel(
            name="EvePlanet",
        ),
        migrations.DeleteModel(
            name="EveSolarSystem",
        ),
        migrations.DeleteModel(
            name="EveConstellation",
        ),
        migrations.DeleteModel(
            name="EveRegion",
        ),
        migrations.DeleteModel(
            name="EveType",
        ),
        migrations.DeleteModel(
            name="EveGroup",
        ),
        migrations.DeleteModel(
            name="EveCategory",
        ),
        migrations.DeleteModel(
            name="EveEntity",
        ),
    ]
