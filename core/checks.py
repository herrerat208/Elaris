from django.conf import settings
from django.core.checks import Warning, register

# locmem is the backend used by the test runner, so it is intentionally ignored.
NON_DELIVERING_BACKENDS = ("console", "filebased", "dummy")


@register()
def email_delivery_check(app_configs, **kwargs):
    """Warn when production is configured to swallow password reset emails."""
    backend = settings.EMAIL_BACKEND
    if settings.DEBUG or not any(name in backend for name in NON_DELIVERING_BACKENDS):
        return []
    return [
        Warning(
            "La recuperación de contraseña no puede enviar emails en producción.",
            hint=(
                "Configurá DJANGO_EMAIL_HOST, DJANGO_EMAIL_PORT, "
                "DJANGO_EMAIL_HOST_USER, DJANGO_EMAIL_HOST_PASSWORD y "
                "DEFAULT_FROM_EMAIL. Sin eso, el link de recuperación solo "
                "se escribe en los logs."
            ),
            id="elaris.W001",
        )
    ]
