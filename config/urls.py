from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuenta/", include("accounts.urls")),
    path("", include("businesses.urls")),
    path("", include("clients.urls")),
    path("", include("agenda.urls")),
    path("", include("core.urls")),
]
