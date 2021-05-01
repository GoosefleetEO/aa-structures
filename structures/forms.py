from django import forms

from .models import StructureTag


class TagsFilterForm(forms.Form):
    """Generated form with a checkbox for each structure tag"""

    def __init__(self, *args, **kwargs):
        super(TagsFilterForm, self).__init__(*args, **kwargs)

        for tag in StructureTag.objects.all():
            self.fields[tag.name] = forms.BooleanField(required=False)
