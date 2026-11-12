from django import forms

from .models import Client


def _phone_key(value):
    digits = "".join(character for character in value if character.isdigit())
    digits = digits.lstrip("0")
    if len(digits) >= 10:
        return digits[-10:]
    return digits if len(digits) >= 8 else ""


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ("name", "phone", "email", "notes")
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "field",
                    "placeholder": "Ej. Sofía Pérez",
                    "autocomplete": "name",
                    "autofocus": True,
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "field",
                    "placeholder": "Ej. 11 5555 5555",
                    "autocomplete": "tel",
                    "inputmode": "tel",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "field",
                    "placeholder": "ejemplo@email.com",
                    "autocomplete": "email",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "field min-h-28",
                    "rows": 4,
                    "placeholder": "Preferencias, alergias, cosas a tener en cuenta…",
                }
            ),
        }
        labels = {
            "name": "Nombre y apellido",
            "phone": "Teléfono / WhatsApp",
            "email": "Email",
            "notes": "Notas",
        }
        help_texts = {
            "phone": "Con código de área. Se usa para contactarlo y armar recordatorios.",
            "notes": "Solo lo ves vos.",
        }

    def __init__(self, *args, business=None, **kwargs):
        self.business = business
        super().__init__(*args, **kwargs)

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        phone_key = _phone_key(phone)
        if self.business is not None and phone_key:
            other_clients = self.business.clients.exclude(phone="")
            if self.instance.pk:
                other_clients = other_clients.exclude(pk=self.instance.pk)
            for other in other_clients:
                if _phone_key(other.phone) == phone_key:
                    raise forms.ValidationError(
                        f"Ya tenés un cliente con ese teléfono: {other.name}."
                    )
        return phone

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
