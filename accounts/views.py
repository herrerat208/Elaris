from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import LoginForm, SignupForm


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
