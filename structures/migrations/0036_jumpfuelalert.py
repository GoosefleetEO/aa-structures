# Generated by Django 3.2.9 on 2021-12-10 22:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('structures', '0035_auto_20211210_2208'),
    ]

    operations = [
        migrations.CreateModel(
            name='JumpFuelAlert',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('config', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='jump_fuel_alerts', to='structures.jumpfuelalertconfig')),
                ('structure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='jump_fuel_alerts', to='structures.structure')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
