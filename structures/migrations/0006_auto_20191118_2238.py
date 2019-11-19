# Generated by Django 2.2.5 on 2019-11-18 22:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('structures', '0005_auto_20191118_1612'),
    ]

    operations = [
        migrations.AlterField(
            model_name='structure',
            name='position_x',
            field=models.FloatField(blank=True, default=None, help_text='x position of the structure in the solar system', null=True),
        ),
        migrations.AlterField(
            model_name='structure',
            name='position_y',
            field=models.FloatField(blank=True, default=None, help_text='y position of the structure in the solar system', null=True),
        ),
        migrations.AlterField(
            model_name='structure',
            name='position_z',
            field=models.FloatField(blank=True, default=None, help_text='z position of the structure in the solar system', null=True),
        ),
    ]
