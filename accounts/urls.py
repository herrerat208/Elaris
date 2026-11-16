from django.urls import path

from .views import (
    ElarisLoginView,
    ElarisLogoutView,
    ElarisPasswordResetCompleteView,
    ElarisPasswordResetConfirmView,
    ElarisPasswordResetDoneView,
    ElarisPasswordResetView,
    SignupView,
)

app_name = "accounts"

urlpatterns = [
    path("crear/", SignupView.as_view(), name="signup"),
    path("ingresar/", ElarisLoginView.as_view(), name="login"),
    path("salir/", ElarisLogoutView.as_view(), name="logout"),
    path(
        "recuperar/",
        ElarisPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "recuperar/enviado/",
        ElarisPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "recuperar/<uidb64>/<token>/",
        ElarisPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "recuperar/completado/",
        ElarisPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
