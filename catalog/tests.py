from django.test import TestCase

from .models import ServiceTemplate, Specialty


class CatalogTests(TestCase):
    def test_seeded_specialties(self):
        self.assertEqual(
            list(Specialty.objects.values_list("name", flat=True)),
            ["Uñas", "Pestañas", "Cejas"],
        )

    def test_seeded_services(self):
        self.assertEqual(ServiceTemplate.objects.count(), 21)

        unas = Specialty.objects.get(slug="unas")
        self.assertEqual(unas.service_templates.count(), 9)
        self.assertEqual(
            unas.service_templates.get(name="Semi permanente").default_duration_minutes,
            60,
        )
        self.assertEqual(
            unas.service_templates.get(name="Belleza de manos").default_duration_minutes,
            45,
        )

        pestanas = Specialty.objects.get(slug="pestanas")
        self.assertEqual(pestanas.service_templates.count(), 9)
        self.assertEqual(
            pestanas.service_templates.get(name="Volumen 5D").default_duration_minutes,
            180,
        )

        cejas = Specialty.objects.get(slug="cejas")
        self.assertEqual(cejas.service_templates.count(), 3)
        self.assertEqual(
            cejas.service_templates.get(name="Perfilado").default_duration_minutes,
            30,
        )
