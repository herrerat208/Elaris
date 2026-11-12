from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("health/", views.health, name="health"),
    path("sw.js", views.service_worker, name="service_worker"),
]
