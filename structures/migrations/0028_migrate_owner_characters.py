"""This migration copies the character ownership relations from the Owner model
to the new OwnerCharacter model.
"""

from django.db import migrations


def migrate_forward(apps, schema_editor):
    Owner = apps.get_model("structures", "Owner")
    OwnerCharacter = apps.get_model("structures", "OwnerCharacter")
    for owner in Owner.objects.all():
        if owner.character_ownership:
            OwnerCharacter.objects.get_or_create(
                owner=owner, character_ownership=owner.character_ownership
            )
            owner.character_ownership = None
            owner.save()


def migrate_backwards(apps, schema_editor):
    Owner = apps.get_model("structures", "Owner")
    for owner in Owner.objects.all():
        owner_character = owner.characters.first()
        if owner_character:
            owner.character_ownership = owner_character.character_ownership
            owner.save()


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0027_create_owner_characters"),
    ]

    operations = [
        migrations.RunPython(migrate_forward, migrate_backwards),
    ]
