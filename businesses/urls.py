from django.urls import path

from . import views

app_name = "businesses"

urlpatterns = [
    path("onboarding/", views.onboarding, name="onboarding"),
    path("panel/", views.dashboard, name="dashboard"),
    path("panel/servicios/", views.service_list, name="service_list"),
    path("panel/servicios/nuevo/", views.service_create, name="service_create"),
    path(
        "panel/servicios/<int:pk>/editar/",
        views.service_edit,
        name="service_edit",
    ),
    path(
        "panel/servicios/<int:pk>/archivar/",
        views.service_archive,
        name="service_archive",
    ),
    path(
        "panel/servicios/<int:pk>/activar/",
        views.service_activate,
        name="service_activate",
    ),
    path("panel/configuracion/", views.settings, name="settings"),
    path("panel/exportar/clientes/", views.export_clients, name="export_clients"),
    path(
        "panel/exportar/turnos/",
        views.export_appointments,
        name="export_appointments",
    ),
    path("panel/exportar/ingresos/", views.export_income, name="export_income"),
    path("panel/exportar/respaldo/", views.backup, name="backup"),
]
