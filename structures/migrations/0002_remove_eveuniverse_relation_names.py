# Generated by Django 4.0.7 on 2022-09-16 12:31

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eveuniverse", "0007_evetype_description"),
        ("structures", "0001_initial_new"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="sender",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="eveuniverse.eveentity",
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
                related_name="+",
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
                related_name="+",
                to="eveuniverse.eveplanet",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="eve_solar_system",
            field=models.ForeignKey(
                help_text="Solar System the structure is located",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="eveuniverse.evesolarsystem",
            ),
        ),
        migrations.AlterField(
            model_name="structure",
            name="eve_type",
            field=models.ForeignKey(
                help_text="Type of the structure",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="eveuniverse.evetype",
            ),
        ),
    ]
