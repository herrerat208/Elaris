from urllib.parse import quote

from django.db import models


class Client(models.Model):
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="clients",
        verbose_name="negocio",
    )
    name = models.CharField("nombre y apellido", max_length=120)
    phone = models.CharField("teléfono / WhatsApp", max_length=40, blank=True)
    email = models.EmailField("email", blank=True)
    notes = models.TextField("notas", blank=True)
    is_active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        indexes = [
            models.Index(
                fields=("business", "name"),
                name="client_business_name_idx",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def phone_digits(self) -> str:
        return "".join(character for character in self.phone if character.isdigit())

    @property
    def whatsapp_number(self) -> str:
        digits = self.phone_digits
        if not digits:
            return ""
        if digits.startswith("54"):
            return digits
        digits = digits.lstrip("0")
        if len(digits) == 10:
            return f"549{digits}"
        if len(digits) == 11 and digits.startswith("9"):
            return f"54{digits}"
        return digits

    @property
    def whatsapp_url(self) -> str:
        if not self.whatsapp_number:
            return ""
        text = f"Hola {self.name}, te escribo de {self.business.name}."
        return f"https://wa.me/{self.whatsapp_number}?text={quote(text)}"
