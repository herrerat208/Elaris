from django.urls import path

from .views import ElarisLoginView, ElarisLogoutView, SignupView

app_name = "accounts"

urlpatterns = [
    path("crear/", SignupView.as_view(), name="signup"),
    path("ingresar/", ElarisLoginView.as_view(), name="login"),
    path("salir/", ElarisLogoutView.as_view(), name="logout"),
]
