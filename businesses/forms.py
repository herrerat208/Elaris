from django import forms
from django.db.models import Q

from catalog.models import ServiceTemplate, Specialty

from .models import Service


class BusinessSettingsForm(forms.Form):
    name = forms.CharField(
        label="Nombre del negocio",
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": "field",
                "placeholder": "Ej. Nails Aral",
                "autocomplete": "organization",
            }
        ),
    )
    whatsapp = forms.CharField(
        label="WhatsApp del negocio",
        max_length=40,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "field",
                "placeholder": "Ej. 11 5555 5555",
                "autocomplete": "tel",
                "inputmode": "tel",
            }
        ),
        help_text="Se incluye al final de los recordatorios para que tus clientes puedan responderte.",
    )
    specialties = forms.ModelMultipleChoiceField(
        label="Rubros que ofrecés",
        queryset=Specialty.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        error_messages={"required": "Elegí al menos un rubro."},
    )

    def __init__(self, *args, business=None, **kwargs):
        self.business = business
        super().__init__(*args, **kwargs)
        self.fields["specialties"].queryset = Specialty.objects.filter(is_active=True).order_by(
            "sort_order", "name"
        )
        if business is not None and not self.is_bound:
            self.initial.setdefault("name", business.name)
            self.initial.setdefault("whatsapp", business.whatsapp)
            self.initial.setdefault(
                "specialties",
                list(business.specialties.values_list("pk", flat=True)),
            )

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean_whatsapp(self):
        return self.cleaned_data["whatsapp"].strip()

    def clean_specialties(self):
        specialties = self.cleaned_data["specialties"]
        if self.business is None:
            return specialties

        current_ids = set(self.business.specialties.values_list("pk", flat=True))
        selected_ids = {specialty.pk for specialty in specialties}
        removed_ids = current_ids - selected_ids
        if removed_ids and Service.objects.filter(
            business=self.business,
            specialty_id__in=removed_ids,
            is_active=True,
        ).exists():
            raise forms.ValidationError(
                "No podés quitar un rubro con servicios activos. "
                "Archivá o mové esos servicios primero."
            )
        return specialties


class OnboardingForm(forms.Form):
    business_name = forms.CharField(
        label="Nombre del negocio",
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": "field",
                "placeholder": "Ej. Nails Aral",
                "autocomplete": "organization",
                "autofocus": True,
            }
        ),
        help_text="Solo para identificar tu espacio. No cambia la marca ni la estética de Elaris.",
    )
    specialties = forms.ModelMultipleChoiceField(
        label="¿Qué hacés?",
        queryset=Specialty.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        error_messages={"required": "Elegí al menos un rubro."},
    )
    services = forms.ModelMultipleChoiceField(
        label="Servicios",
        queryset=ServiceTemplate.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        error_messages={"required": "Elegí al menos un servicio."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["specialties"].queryset = Specialty.objects.filter(is_active=True).order_by(
            "sort_order", "name"
        )
        self.fields["services"].queryset = (
            ServiceTemplate.objects.filter(is_active=True)
            .select_related("specialty")
            .order_by("specialty__sort_order", "sort_order", "name")
        )

    def clean_business_name(self):
        return self.cleaned_data["business_name"].strip()

    def clean(self):
        cleaned_data = super().clean()
        specialties = cleaned_data.get("specialties")
        services = cleaned_data.get("services")

        if specialties and services:
            selected_specialty_ids = {specialty.id for specialty in specialties}
            invalid_services = [
                service
                for service in services
                if service.specialty_id not in selected_specialty_ids
            ]
            if invalid_services:
                self.add_error(
                    "services",
                    "Hay servicios de rubros que no marcaste. Revisá la selección.",
                )

        return cleaned_data


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ("specialty", "name", "duration_minutes", "price", "is_active")
        widgets = {
            "specialty": forms.Select(attrs={"class": "field"}),
            "name": forms.TextInput(
                attrs={
                    "class": "field",
                    "placeholder": "Ej. Semi permanente",
                    "autocomplete": "off",
                }
            ),
            "duration_minutes": forms.NumberInput(
                attrs={
                    "class": "field",
                    "min": 5,
                    "max": 600,
                    "step": 5,
                    "inputmode": "numeric",
                }
            ),
            "price": forms.NumberInput(
                attrs={
                    "class": "field pl-8",
                    "min": 0,
                    "step": "0.01",
                    "inputmode": "decimal",
                    "placeholder": "Ej. 12000",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-ink/20 accent-ink focus:ring-celeste",
                }
            ),
        }
        labels = {
            "specialty": "Rubro",
            "name": "Nombre del servicio",
            "duration_minutes": "Duración (minutos)",
            "price": "Precio",
            "is_active": "Servicio activo",
        }
        help_texts = {
            "specialty": "Solo podés elegir entre los rubros de tu espacio.",
            "price": (
                "Ingresá el número sin separadores. Podés dejarlo vacío y completarlo más adelante."
            ),
            "is_active": ("Si lo archivás, no se borra el historial y podés reactivarlo después."),
        }

    def __init__(self, *args, business=None, **kwargs):
        self.business = business or getattr(self.instance, "business", None)
        super().__init__(*args, **kwargs)
        specialties = (
            Specialty.objects.filter(businesses=self.business, is_active=True).distinct()
            if self.business
            else Specialty.objects.none()
        )
        if self.instance.pk and self.instance.specialty_id:
            specialties = Specialty.objects.filter(
                Q(pk=self.instance.specialty_id) | Q(businesses=self.business, is_active=True)
            ).distinct()
        self.fields["specialty"].queryset = specialties.order_by("sort_order", "name")

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        specialty = self.cleaned_data.get("specialty")
        if specialty is None and self.instance.pk and self.instance.specialty_id:
            specialty = self.instance.specialty
        if self.business and specialty:
            duplicate = (
                Service.objects.filter(
                    business=self.business,
                    specialty=specialty,
                    name__iexact=name,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate:
                raise forms.ValidationError("Ya tenés un servicio con ese nombre en este rubro.")
        return name

    def clean_duration_minutes(self):
        duration = self.cleaned_data["duration_minutes"]
        if duration < 5:
            raise forms.ValidationError("La duración mínima es de 5 minutos.")
        if duration > 600:
            raise forms.ValidationError("La duración máxima es de 600 minutos.")
        return duration
