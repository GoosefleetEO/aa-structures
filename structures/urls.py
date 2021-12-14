from django.urls import path

from . import views

app_name = "structures"

urlpatterns = [
    path("", views.index, name="index"),
    path("list", views.main, name="main"),
    path("list_data", views.structure_list_data, name="structure_list_data"),
    path("summary_data", views.structure_summary_data, name="structure_summary_data"),
    path("add_structure_owner", views.add_structure_owner, name="add_structure_owner"),
    path("poco_list_data", views.poco_list_data, name="poco_list_data"),
    path(
        "jump_gates_list_data", views.jump_gates_list_data, name="jump_gates_list_data"
    ),
    path("service_status", views.service_status, name="service_status"),
    path(
        "<int:structure_id>/structure_details",
        views.structure_details,
        name="structure_details",
    ),
    path(
        "<int:structure_id>/poco_details",
        views.poco_details,
        name="poco_details",
    ),
]
