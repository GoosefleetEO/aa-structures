from django.urls import path
from . import views


app_name = "structures"

urlpatterns = [
    path("", views.index, name="index"),
    path("list", views.structure_list, name="structure_list"),
    path("list_data", views.structure_list_data, name="structure_list_data"),
    path("add_structure_owner", views.add_structure_owner, name="add_structure_owner"),
    path("poco_list_data", views.poco_list_data, name="poco_list_data"),
    path("service_status", views.service_status, name="service_status"),
]
