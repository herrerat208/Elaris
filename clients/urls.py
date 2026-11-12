from django.urls import path

from . import views

app_name = "clients"

urlpatterns = [
    path("panel/clientes/", views.client_list, name="list"),
    path("panel/clientes/nuevo/", views.client_create, name="create"),
    path("panel/clientes/<int:pk>/", views.client_detail, name="detail"),
    path("panel/clientes/<int:pk>/editar/", views.client_edit, name="edit"),
    path("panel/clientes/<int:pk>/archivar/", views.client_archive, name="archive"),
    path("panel/clientes/<int:pk>/activar/", views.client_activate, name="activate"),
]
