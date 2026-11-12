from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Specialty(models.Model):
    name = models.CharField("nombre", max_length=60, unique=True)
    slug = models.SlugField("slug", max_length=60, unique=True)
    sort_order = models.PositiveSmallIntegerField("orden", default=0)
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name = "rubro"
        verbose_name_plural = "rubros"

    def __str__(self):
        return self.name


class ServiceTemplate(models.Model):
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.CASCADE,
        related_name="service_templates",
        verbose_name="rubro",
    )
    name = models.CharField("nombre", max_length=120)
    default_duration_minutes = models.PositiveSmallIntegerField(
        "duración estimada (minutos)",
        default=60,
        validators=[MinValueValidator(5), MaxValueValidator(600)],
    )
    sort_order = models.PositiveSmallIntegerField("orden", default=0)
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ("specialty__sort_order", "sort_order", "name")
        verbose_name = "servicio del catálogo"
        verbose_name_plural = "servicios del catálogo"
        constraints = [
            models.UniqueConstraint(
                fields=("specialty", "name"),
                name="unique_service_template_per_specialty",
            )
        ]

    def __str__(self):
        return f"{self.specialty.name} · {self.name}"
