from decimal import Decimal
from urllib.parse import quote

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

WEEKDAY_CHOICES = (
    (0, "Lunes"),
    (1, "Martes"),
    (2, "Miércoles"),
    (3, "Jueves"),
    (4, "Viernes"),
    (5, "Sábado"),
    (6, "Domingo"),
)


class ScheduleBlock(models.Model):
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="schedule_blocks",
        verbose_name="negocio",
    )
    weekday = models.PositiveSmallIntegerField("día", choices=WEEKDAY_CHOICES)
    start_time = models.TimeField("desde")
    end_time = models.TimeField("hasta")
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ("weekday", "start_time")
        verbose_name = "bloque de horario"
        verbose_name_plural = "bloques de horario"
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="schedule_block_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(weekday__gte=0, weekday__lte=6),
                name="schedule_block_valid_weekday",
            ),
        ]

    def __str__(self):
        day = dict(WEEKDAY_CHOICES).get(self.weekday, "?")
        return f"{day} {self.start_time:%H:%M}–{self.end_time:%H:%M}"


class TimeOff(models.Model):
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="time_off",
        verbose_name="negocio",
    )
    start_date = models.DateField("desde")
    end_date = models.DateField("hasta")
    reason = models.CharField("motivo", max_length=160, blank=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)

    class Meta:
        ordering = ("-start_date", "-id")
        verbose_name = "día libre"
        verbose_name_plural = "días libres"
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="time_off_end_on_or_after_start",
            )
        ]

    def __str__(self):
        if self.start_date == self.end_date:
            return self.start_date.strftime("%d/%m/%Y")
        return f"{self.start_date:%d/%m/%Y}–{self.end_date:%d/%m/%Y}"

    @property
    def is_single_day(self) -> bool:
        return self.start_date == self.end_date


class Appointment(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_NO_SHOW = "no_show"
    STATUS_CHOICES = (
        (STATUS_SCHEDULED, "Programado"),
        (STATUS_COMPLETED, "Completado"),
        (STATUS_CANCELLED, "Cancelado"),
        (STATUS_NO_SHOW, "No asistió"),
    )
    PAYMENT_METHOD_CASH = "cash"
    PAYMENT_METHOD_TRANSFER = "transfer"
    PAYMENT_METHOD_OTHER = "other"
    PAYMENT_METHOD_CHOICES = (
        (PAYMENT_METHOD_CASH, "Efectivo"),
        (PAYMENT_METHOD_TRANSFER, "Transferencia"),
        (PAYMENT_METHOD_OTHER, "Otro"),
    )

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name="negocio",
    )
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="cliente",
    )
    service = models.ForeignKey(
        "businesses.Service",
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="servicio",
    )
    service_name = models.CharField("servicio (histórico)", max_length=120)
    duration_minutes = models.PositiveSmallIntegerField(
        "duración (minutos)",
        validators=[MinValueValidator(5), MaxValueValidator(600)],
    )
    price = models.DecimalField(
        "precio",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    start_at = models.DateTimeField("inicio")
    end_at = models.DateTimeField("fin")
    status = models.CharField(
        "estado",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
        db_index=True,
    )
    notes = models.TextField("notas", blank=True)
    reminded_at = models.DateTimeField("recordatorio marcado", null=True, blank=True)
    amount_paid = models.DecimalField(
        "monto cobrado",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    payment_method = models.CharField(
        "medio de pago",
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ("start_at", "id")
        verbose_name = "turno"
        verbose_name_plural = "turnos"
        indexes = [
            models.Index(
                fields=("business", "start_at"),
                name="appt_business_start_idx",
            ),
            models.Index(
                fields=("business", "status", "start_at"),
                name="appt_business_status_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")),
                name="appointment_end_after_start",
            )
        ]
        # PostgreSQL also gets an EXCLUDE constraint for overlapping
        # appointments. It is added with raw SQL in migration 0003 because
        # SQLite (used for local development) does not support EXCLUDE.

    def __str__(self):
        if timezone.is_aware(self.start_at):
            local_start = timezone.localtime(self.start_at)
        else:
            local_start = self.start_at
        return f"{self.client.name} · {local_start:%d/%m/%Y %H:%M}"

    @property
    def price_display(self) -> str:
        if self.price is None:
            return "Sin precio"
        if self.price == self.price.to_integral():
            return "$" + f"{self.price:,.0f}".replace(",", ".")
        return "$" + f"{self.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @property
    def status_badge_class(self) -> str:
        return {
            self.STATUS_SCHEDULED: "badge-scheduled",
            self.STATUS_COMPLETED: "badge-completed",
            self.STATUS_CANCELLED: "badge-cancelled",
            self.STATUS_NO_SHOW: "badge-no-show",
        }.get(self.status, "badge-scheduled")

    @property
    def is_reminded(self) -> bool:
        return self.reminded_at is not None

    @property
    def payment_status_key(self) -> str:
        if self.amount_paid is None:
            return "unregistered"
        if self.price is not None and self.amount_paid >= self.price:
            return "paid"
        if self.amount_paid > 0:
            return "deposit"
        return "pending"

    @property
    def payment_status_label(self) -> str:
        return {
            "unregistered": "Sin registrar",
            "paid": "Pagado",
            "deposit": "Seña",
            "pending": "Pendiente",
        }[self.payment_status_key]

    @property
    def payment_badge_class(self) -> str:
        return {
            "unregistered": "badge-neutral",
            "paid": "badge-completed",
            "deposit": "badge-scheduled",
            "pending": "badge-no-show",
        }[self.payment_status_key]

    @property
    def reminder_text(self) -> str:
        if timezone.is_naive(self.start_at):
            local_start = timezone.make_aware(self.start_at)
        else:
            local_start = timezone.localtime(self.start_at)
        text = (
            f"Hola {self.client.name}, te recuerdo tu turno de "
            f"{self.service_name} en {self.business.name} el "
            f"{local_start:%d/%m/%Y} a las {local_start:%H:%M}. ¡Te espero!"
        )
        if self.business.whatsapp:
            text += f" Cualquier consulta, escribime al {self.business.whatsapp}."
        return text

    @property
    def whatsapp_reminder_url(self) -> str:
        number = self.client.whatsapp_number
        if not number:
            return ""
        return f"https://wa.me/{number}?text={quote(self.reminder_text)}"
