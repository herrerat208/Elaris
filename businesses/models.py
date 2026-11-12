from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Business(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business",
        verbose_name="profesional",
    )
    name = models.CharField("nombre del negocio", max_length=120)
    whatsapp = models.CharField("WhatsApp del negocio", max_length=40, blank=True)
    specialties = models.ManyToManyField(
        "catalog.Specialty",
        related_name="businesses",
        blank=True,
        verbose_name="rubros",
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        verbose_name = "negocio"
        verbose_name_plural = "negocios"

    def __str__(self):
        return self.name


class Service(models.Model):
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name="negocio",
    )
    specialty = models.ForeignKey(
        "catalog.Specialty",
        on_delete=models.PROTECT,
        related_name="services",
        verbose_name="rubro",
    )
    name = models.CharField("nombre", max_length=120)
    duration_minutes = models.PositiveSmallIntegerField(
        "duración (minutos)",
        default=60,
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
    is_active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ("specialty__sort_order", "name")
        verbose_name = "servicio"
        verbose_name_plural = "servicios"
        constraints = [
            models.UniqueConstraint(
                fields=("business", "specialty", "name"),
                name="unique_service_per_business_specialty",
            )
        ]

    def __str__(self):
        return f"{self.business.name} · {self.name}"

    @property
    def price_display(self) -> str:
        if self.price is None:
            return "A completar"
        if self.price == self.price.to_integral():
            return "$" + f"{self.price:,.0f}".replace(",", ".")
        return "$" + f"{self.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @property
    def duration_display(self) -> str:
        return f"{self.duration_minutes} min"
