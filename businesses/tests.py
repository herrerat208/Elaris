from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import ServiceTemplate, Specialty

from .models import Business, Service


class OnboardingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profesional@example.com",
            password="ClaveSegura123!",
        )
        self.unas = Specialty.objects.get(slug="unas")
        self.pestanas = Specialty.objects.get(slug="pestanas")
        self.cejas = Specialty.objects.get(slug="cejas")

    def test_requires_login(self):
        response = self.client.get(reverse("businesses:onboarding"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_onboarding_page_renders(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("businesses:onboarding"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Armemos tu espacio")
        self.assertContains(response, "Uñas")
        self.assertContains(response, "Semi permanente")

    def test_creates_business_and_selected_services(self):
        self.client.force_login(self.user)
        semi = ServiceTemplate.objects.get(
            specialty=self.unas,
            name="Semi permanente",
        )
        lifting = ServiceTemplate.objects.get(
            specialty=self.pestanas,
            name="Lifting",
        )

        response = self.client.post(
            reverse("businesses:onboarding"),
            {
                "business_name": "Nails Aral",
                "specialties": [self.unas.pk, self.pestanas.pk],
                "services": [semi.pk, lifting.pk],
            },
        )

        self.assertRedirects(response, reverse("businesses:dashboard"))
        business = Business.objects.get(owner=self.user)
        self.assertEqual(business.name, "Nails Aral")
        self.assertEqual(
            set(business.specialties.values_list("slug", flat=True)),
            {"unas", "pestanas"},
        )
        self.assertEqual(business.services.count(), 2)

        created_semi = business.services.get(name="Semi permanente")
        self.assertEqual(created_semi.specialty, self.unas)
        self.assertEqual(created_semi.duration_minutes, 60)
        self.assertIsNone(created_semi.price)

        created_lifting = business.services.get(name="Lifting")
        self.assertEqual(created_lifting.duration_minutes, 60)

    def test_requires_at_least_one_service(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("businesses:onboarding"),
            {
                "business_name": "Nails Aral",
                "specialties": [self.unas.pk],
                "services": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elegí al menos un servicio.")
        self.assertFalse(Business.objects.filter(owner=self.user).exists())

    def test_rejects_service_from_unselected_specialty(self):
        self.client.force_login(self.user)
        lifting = ServiceTemplate.objects.get(
            specialty=self.pestanas,
            name="Lifting",
        )

        response = self.client.post(
            reverse("businesses:onboarding"),
            {
                "business_name": "Nails Aral",
                "specialties": [self.unas.pk],
                "services": [lifting.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hay servicios de rubros que no marcaste.")
        self.assertFalse(Business.objects.filter(owner=self.user).exists())

    def test_existing_business_redirects_to_dashboard(self):
        Business.objects.create(owner=self.user, name="Nails Aral")
        self.client.force_login(self.user)

        response = self.client.get(reverse("businesses:onboarding"))

        self.assertRedirects(response, reverse("businesses:dashboard"))

    def test_dashboard_without_business_redirects_to_onboarding(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("businesses:dashboard"))

        self.assertRedirects(response, reverse("businesses:onboarding"))


class DashboardTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            email="a@example.com",
            password="ClaveSegura123!",
        )
        self.user_b = User.objects.create_user(
            email="b@example.com",
            password="ClaveSegura123!",
        )
        self.unas = Specialty.objects.get(slug="unas")
        self.pestanas = Specialty.objects.get(slug="pestanas")

        self.business_a = Business.objects.create(owner=self.user_a, name="Nails Aral")
        self.business_a.specialties.set([self.unas])
        self.service_a = Service.objects.create(
            business=self.business_a,
            specialty=self.unas,
            name="Semi A",
            duration_minutes=60,
            price=None,
        )

        self.business_b = Business.objects.create(owner=self.user_b, name="Lashes B")
        self.business_b.specialties.set([self.pestanas])
        self.service_b = Service.objects.create(
            business=self.business_b,
            specialty=self.pestanas,
            name="Lifting B",
            duration_minutes=60,
            price=15000,
        )

    def test_dashboard_shows_only_own_services(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("businesses:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Semi A")
        self.assertNotContains(response, "Lifting B")
        self.assertContains(response, "sin precio")

    def test_service_list_shows_active_and_archived_services(self):
        archived = Service.objects.create(
            business=self.business_a,
            specialty=self.unas,
            name="Servicio archivado",
            duration_minutes=45,
            is_active=False,
        )
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("businesses:service_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Semi A")
        self.assertContains(response, "Servicio archivado")
        self.assertContains(response, "Reactivar")
        self.assertEqual(response.context["services_count"], 1)
        self.assertEqual(response.context["inactive_count"], 1)
        self.assertIn(archived, response.context["inactive_services"])

    def test_service_create_page_renders(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("businesses:service_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nuevo servicio")
        self.assertContains(response, "Rubro")
        self.assertContains(response, "Uñas")

    def test_service_create_assigns_business_and_redirects(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse("businesses:service_create"),
            {
                "specialty": self.unas.pk,
                "name": "Kapping",
                "duration_minutes": 45,
                "price": "",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("businesses:service_list"))
        service = Service.objects.get(business=self.business_a, name="Kapping")
        self.assertEqual(service.specialty, self.unas)
        self.assertIsNone(service.price)

    def test_service_create_rejects_specialty_from_another_business(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse("businesses:service_create"),
            {
                "specialty": self.pestanas.pk,
                "name": "Lifting",
                "duration_minutes": 60,
                "price": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Service.objects.filter(business=self.business_a, name="Lifting").exists())

    def test_service_edit_page_renders(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("businesses:service_edit", args=[self.service_a.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar servicio")
        self.assertContains(response, "Semi A")

    def test_service_edit_updates_own_service(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse("businesses:service_edit", args=[self.service_a.pk]),
            {
                "specialty": self.unas.pk,
                "name": "Semi A actualizado",
                "duration_minutes": 75,
                "price": "12000",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("businesses:service_list"))
        self.service_a.refresh_from_db()
        self.assertEqual(self.service_a.name, "Semi A actualizado")
        self.assertEqual(self.service_a.duration_minutes, 75)
        self.assertEqual(str(self.service_a.price), "12000.00")
        self.assertTrue(self.service_a.is_active)

    def test_deactivated_service_can_be_reactivated(self):
        self.service_a.is_active = False
        self.service_a.save(update_fields=("is_active", "updated_at"))
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("businesses:service_list"))

        self.assertContains(response, "Todavía no tenés servicios activos")
        self.assertContains(response, "Semi A")
        self.assertContains(response, "Reactivar")

        response = self.client.post(
            reverse("businesses:service_activate", args=[self.service_a.pk])
        )

        self.assertRedirects(response, reverse("businesses:service_list"))
        self.service_a.refresh_from_db()
        self.assertTrue(self.service_a.is_active)

    def test_service_edit_rejects_duplicate_name(self):
        Service.objects.create(
            business=self.business_a,
            specialty=self.unas,
            name="Semi B",
            duration_minutes=60,
        )
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse("businesses:service_edit", args=[self.service_a.pk]),
            {
                "specialty": self.unas.pk,
                "name": "Semi B",
                "duration_minutes": 60,
                "price": "12000",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya tenés un servicio con ese nombre en este rubro.")
        self.service_a.refresh_from_db()
        self.assertEqual(self.service_a.name, "Semi A")

    def test_service_edit_rejects_negative_price(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse("businesses:service_edit", args=[self.service_a.pk]),
            {
                "specialty": self.unas.pk,
                "name": "Semi A",
                "duration_minutes": 60,
                "price": "-100",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.service_a.refresh_from_db()
        self.assertIsNone(self.service_a.price)

    def test_service_edit_cannot_access_other_business_service(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("businesses:service_edit", args=[self.service_b.pk]))

        self.assertEqual(response.status_code, 404)

    def test_cannot_activate_other_business_service(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse("businesses:service_activate", args=[self.service_b.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.service_b.refresh_from_db()
        self.assertTrue(self.service_b.is_active)

    def test_cannot_archive_other_business_service(self):
        self.client.force_login(self.user_a)

        response = self.client.post(reverse("businesses:service_archive", args=[self.service_b.pk]))

        self.assertEqual(response.status_code, 404)
        self.service_b.refresh_from_db()
        self.assertTrue(self.service_b.is_active)
