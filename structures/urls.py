from django.conf.urls import url
from . import views


app_name = "structures"

urlpatterns = [
    url(r"^$", views.index, name="index"),
    url(r"^list/$", views.structure_list, name="structure_list"),
    url(r"^list_data/$", views.structure_list_data, name="structure_list_data"),
    url(
        r"^add_structure_owner/$", views.add_structure_owner, name="add_structure_owner"
    ),
    url(r"^service_status/$", views.service_status, name="service_status"),
]
