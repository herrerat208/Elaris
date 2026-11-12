from django import forms
from django.contrib.auth import forms as auth_forms
from django.core.exceptions import ValidationError

from .models import User

class SignupForm(auth_forms.BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta con este email.")
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Email"
        self.fields["email"].widget.attrs.update(
            {
                "autocomplete": "email",
                "placeholder": "tu@email.com",
                "class": "field",
                "autofocus": True,
            }
        )
        self.fields["password1"].label = "Contraseña"
        self.fields["password1"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": "Mínimo 8 caracteres",
                "class": "field",
            }
        )
        self.fields["password2"].label = "Repetí la contraseña"
        self.fields["password2"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": "Repetí tu contraseña",
                "class": "field",
            }
        )


class AdminUserCreationForm(auth_forms.AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class AdminUserChangeForm(auth_forms.UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class LoginForm(auth_forms.AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "autofocus": True,
                "autocomplete": "email",
                "placeholder": "tu@email.com",
                "class": "field",
            }
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Tu contraseña",
                "class": "field",
            }
        ),
    )

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class AccountEmailForm(forms.Form):
    email = forms.EmailField(
        label="Email de la cuenta",
        widget=forms.EmailInput(
            attrs={
                "class": "field",
                "autocomplete": "email",
                "placeholder": "tu@email.com",
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user is not None and not self.is_bound:
            self.initial.setdefault("email", user.email)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        queryset = User.objects.filter(email__iexact=email)
        if self.user is not None:
            queryset = queryset.exclude(pk=self.user.pk)
        if queryset.exists():
            raise ValidationError("Ya existe una cuenta con este email.")
        return email


class StyledPasswordChangeForm(auth_forms.PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("old_password", "new_password1", "new_password2"):
            self.fields[name].widget.attrs.update(
                {
                    "class": "field",
                    "autocomplete": (
                        "current-password" if name == "old_password" else "new-password"
                    ),
                }
            )
