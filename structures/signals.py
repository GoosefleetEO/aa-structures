from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Structure, StructureTag


@receiver(post_save, sender=Structure)
def add_default_tags_to_new_structures(sender, instance, created, **kwargs):
    if created:
        for tag in StructureTag.objects.filter(is_default=True):
            instance.tags.add(tag)
