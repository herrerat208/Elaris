from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import BaseModelFormSet, modelformset_factory

from .availability import validate_appointment_slot
from .models import Appointment, ScheduleBlock, TimeOff


class ScheduleBlockForm(forms.ModelForm):
    class Meta:
        model = ScheduleBlock
        fields = ("weekday", "start_time", "end_time")
        widgets = {
            "weekday": forms.Select(attrs={"class": "field"}),
            "start_time": forms.TimeInput(
                attrs={"class": "field", "type": "time"},
                format="%H:%M",
            ),
            "end_time": forms.TimeInput(
                attrs={"class": "field", "type": "time"},
                format="%H:%M",
            ),
        }
        labels = {
            "weekday": "Día",
            "start_time": "Desde",
            "end_time": "Hasta",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "DELETE" in self.fields:
            self.fields["DELETE"].widget.attrs["class"] = "h-4 w-4 rounded border-ink/20 accent-ink"

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "La hora de fin tiene que ser posterior a la de inicio.")
        return cleaned_data


class BaseScheduleBlockFormSet(BaseModelFormSet):
    def __init__(self, *args, business=None, **kwargs):
        self.business = business
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.instance.business = business

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        rows = []
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            weekday = form.cleaned_data.get("weekday")
            start_time = form.cleaned_data.get("start_time")
            end_time = form.cleaned_data.get("end_time")
            if weekday is None or start_time is None or end_time is None:
                continue
            rows.append((weekday, start_time, end_time, form))

        for weekday in range(7):
            day_rows = sorted(
                (row for row in rows if row[0] == weekday),
                key=lambda row: row[1],
            )
            for previous, current in zip(day_rows, day_rows[1:], strict=False):
                if current[1] < previous[2]:
                    current[3].add_error(
                        None,
                        "Este bloque se superpone con otro del mismo día.",
                    )


ScheduleBlockFormSet = modelformset_factory(
    ScheduleBlock,
    form=ScheduleBlockForm,
    formset=BaseScheduleBlockFormSet,
    extra=1,
    can_delete=True,
)


class TimeOffForm(forms.ModelForm):
    class Meta:
        model = TimeOff
        fields = ("start_date", "end_date", "reason")
        widgets = {
            "start_date": forms.DateInput(
                attrs={"class": "field", "type": "date"},
                format="%Y-%m-%d",
            ),
            "end_date": forms.DateInput(
                attrs={"class": "field", "type": "date"},
                format="%Y-%m-%d",
            ),
            "reason": forms.TextInput(
                attrs={
                    "class": "field",
                    "placeholder": "Ej. Vacaciones, feriado, trámite…",
                }
            ),
        }
        labels = {
            "start_date": "Desde",
            "end_date": "Hasta",
            "reason": "Motivo",
        }
        help_texts = {
            "end_date": "Para un solo día, repetí la misma fecha.",
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "La fecha de fin no puede ser anterior a la de inicio.")
        return cleaned_data


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ("client", "service", "start_at", "price", "notes")
        widgets = {
            "client": forms.Select(attrs={"class": "field"}),
            "service": forms.Select(attrs={"class": "field"}),
            "start_at": forms.DateTimeInput(
                attrs={"class": "field", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
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
            "notes": forms.Textarea(
                attrs={
                    "class": "field min-h-24",
                    "rows": 3,
                    "placeholder": "Detalles del turno, preferencias, recordatorios…",
                }
            ),
        }
        labels = {
            "client": "Cliente",
            "service": "Servicio",
            "start_at": "Fecha y hora",
            "price": "Precio",
            "notes": "Notas",
        }
        help_texts = {
            "start_at": (
                "El turno tiene que entrar dentro de tu horario y no superponerse con otro."
            ),
            "price": (
                "Si lo dejás vacío, se usa el precio del servicio. "
                "Usá 0 si este turno es sin cargo."
            ),
        }

    def __init__(self, *args, business=None, **kwargs):
        self.business = business or getattr(self.instance, "business", None)
        super().__init__(*args, **kwargs)

        # ModelForm mutates self.instance during _post_clean, so keep the
        # database values to detect real service/time changes on edits.
        self._is_new = not self.instance.pk
        self._original_service_id = self.instance.service_id
        self._original_service_name = self.instance.service_name
        self._original_duration_minutes = self.instance.duration_minutes
        self._original_start_at = self.instance.start_at

        clients = self.business.clients.all()
        if self.instance.pk and self.instance.client_id:
            clients = clients.filter(Q(is_active=True) | Q(pk=self.instance.client_id))
        else:
            clients = clients.filter(is_active=True)
        self.fields["client"].queryset = clients.order_by("name", "id")
        self.fields["client"].empty_label = "Elegí un cliente"

        services = self.business.services.select_related("specialty")
        if self.instance.pk and self.instance.service_id:
            services = services.filter(Q(is_active=True) | Q(pk=self.instance.service_id))
        else:
            services = services.filter(is_active=True)
        self.fields["service"].queryset = services.order_by(
            "specialty__sort_order", "specialty_id", "id"
        )
        self.fields["service"].label_from_instance = lambda service: (
            f"{service.specialty.name} · {service.name} · {service.duration_minutes} min"
        )
        self.fields["service"].empty_label = "Elegí un servicio"

        self.fields["start_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get("service")
        start_at = cleaned_data.get("start_at")
        if service and start_at:
            service_changed = self._is_new or service.pk != self._original_service_id
            schedule_changed = (
                self._is_new or start_at != self._original_start_at or service_changed
            )
            if schedule_changed:
                duration_minutes = (
                    service.duration_minutes if service_changed else self._original_duration_minutes
                )
                try:
                    validate_appointment_slot(
                        self.business,
                        start_at,
                        duration_minutes,
                        exclude_pk=self.instance.pk,
                    )
                except ValidationError as error:
                    self.add_error("start_at", error)
        return cleaned_data

    def save(self, commit=True):
        appointment = super().save(commit=False)
        appointment.business = self.business

        service_changed = self._is_new or appointment.service_id != self._original_service_id
        if service_changed:
            appointment.service_name = appointment.service.name
            appointment.duration_minutes = appointment.service.duration_minutes
        else:
            appointment.service_name = self._original_service_name
            appointment.duration_minutes = self._original_duration_minutes

        appointment.end_at = appointment.start_at + timedelta(minutes=appointment.duration_minutes)
        if appointment.price is None:
            appointment.price = appointment.service.price
        if commit:
            appointment.save()
        return appointment


class PaymentForm(forms.Form):
    amount_paid = forms.DecimalField(
        label="Monto cobrado",
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "field pl-8",
                "min": 0,
                "step": "0.01",
                "inputmode": "decimal",
                "placeholder": "Ej. 12000",
            }
        ),
        help_text="Dejalo vacío para borrar el cobro registrado.",
    )
    payment_method = forms.ChoiceField(
        label="Medio de pago",
        choices=(("", "Sin registrar"),) + Appointment.PAYMENT_METHOD_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "field"}),
    )

    def __init__(self, *args, appointment=None, **kwargs):
        self.appointment = appointment
        super().__init__(*args, **kwargs)
        if appointment is not None and not self.is_bound:
            self.initial.setdefault("amount_paid", appointment.amount_paid)
            self.initial.setdefault("payment_method", appointment.payment_method)

    def clean(self):
        cleaned_data = super().clean()
        amount_paid = cleaned_data.get("amount_paid")
        payment_method = cleaned_data.get("payment_method")

        if amount_paid is not None and payment_method == "":
            self.add_error("payment_method", "Elegí cómo se pagó.")
        if amount_paid is None and payment_method:
            self.add_error("amount_paid", "Ingresá el monto cobrado.")
        if (
            amount_paid is not None
            and self.appointment is not None
            and self.appointment.price is not None
            and amount_paid > self.appointment.price
        ):
            self.add_error(
                "amount_paid",
                "El monto no puede superar el precio del turno.",
            )
        return cleaned_data
