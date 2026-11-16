from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import (
    LoginForm,
    SignupForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)


class SignupView(CreateView):
    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("businesses:onboarding")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("businesses:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(
            self.request,
            "Tu cuenta está creada. Ahora armemos tu espacio en Elaris.",
        )
        return response


class ElarisLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class ElarisLogoutView(LogoutView):
    next_page = reverse_lazy("core:landing")


class ElarisPasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    form_class = StyledPasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")
    extra_email_context = {
        "timeout_hours": max(1, settings.PASSWORD_RESET_TIMEOUT // 3600),
    }


class ElarisPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["timeout_hours"] = max(1, settings.PASSWORD_RESET_TIMEOUT // 3600)
        return context


class ElarisPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class ElarisPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
