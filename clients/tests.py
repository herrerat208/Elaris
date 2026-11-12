from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from agenda.models import Appointment
from businesses.models import Business, Service
from catalog.models import Specialty

from .models import Client


class ClientViewTests(TestCase):
    def setUp(self):
        self.unas = Specialty.objects.get(slug="unas")
        self.user_a = User.objects.create_user(
            email="clientes-a@example.com",
            password="ClaveSegura123!",
        )
        self.user_b = User.objects.create_user(
            email="clientes-b@example.com",
            password="ClaveSegura123!",
        )
        self.business_a = Business.objects.create(owner=self.user_a, name="Nails A")
        self.business_a.specialties.set([self.unas])
        self.business_b = Business.objects.create(owner=self.user_b, name="Nails B")
        self.business_b.specialties.set([self.unas])

        self.client_a = Client.objects.create(
            business=self.business_a,
            name="Sofía Pérez",
            phone="11 5555 1111",
            email="sofia@example.com",
        )
        self.other_client = Client.objects.create(
            business=self.business_b,
            name="Otro Cliente",
            phone="11 5555 9999",
        )
        self.service_a = Service.objects.create(
            business=self.business_a,
            specialty=self.unas,
            name="Semi permanente",
            duration_minutes=60,
            price="12000",
        )

    def test_requires_login(self):
        response = self.client.get(reverse("clients:list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_requires_business(self):
        user_without_business = User.objects.create_user(
            email="sin-negocio@example.com",
            password="ClaveSegura123!",
        )
        self.client.force_login(user_without_business)

        response = self.client.get(reverse("clients:list"))

        self.assertRedirects(response, reverse("businesses:onboarding"))

    def test_list_shows_only_own_clients_and_appointment_count(self):
        start = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(10, 0)),
            timezone.get_current_timezone(),
        )
        Appointment.objects.create(
            business=self.business_a,
            client=self.client_a,
            service=self.service_a,
            service_name=self.service_a.name,
            duration_minutes=60,
            price=self.service_a.price,
            start_at=start,
            end_at=start + timedelta(minutes=60),
        )
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("clients:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sofía Pérez")
        self.assertContains(response, "1 turno")
        self.assertContains(response, "Tus clientes")
        self.assertNotContains(response, "Clienta")
        self.assertNotContains(response, "Otro Cliente")

    def test_search_by_name_phone_and_email(self):
        self.client.force_login(self.user_a)

        for query in ("sofía", "5555 1111", "sofia@example.com"):
            with self.subTest(query=query):
                response = self.client.get(reverse("clients:list"), {"q": query})
                self.assertContains(response, "Sofía Pérez")

        response = self.client.get(reverse("clients:list"), {"q": "no-existe"})
        self.assertContains(response, "No encontramos clientes con esa búsqueda")

    def test_archived_filter_shows_only_archived_clients(self):
        self.client_a.is_active = False
        self.client_a.save(update_fields=("is_active", "updated_at"))
        self.client.force_login(self.user_a)

        active_response = self.client.get(reverse("clients:list"))
        archived_response = self.client.get(reverse("clients:list"), {"archivadas": "1"})

        self.assertNotContains(active_response, "Sofía Pérez")
        self.assertContains(archived_response, "Sofía Pérez")
        self.assertContains(archived_response, "Archivado")

    def test_create_assigns_business_and_redirects_to_detail(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse("clients:create"),
            {
                "name": "  Carla Gómez  ",
                "phone": " 11 4444 2222 ",
                "email": "CARLA@EXAMPLE.COM",
                "notes": "Prefiere turnos de mañana.",
            },
        )

        created = Client.objects.get(business=self.business_a, name="Carla Gómez")
        self.assertRedirects(response, reverse("clients:detail", args=[created.pk]))
        self.assertEqual(created.phone, "11 4444 2222")
        self.assertEqual(created.email, "carla@example.com")
        self.assertEqual(created.business, self.business_a)

    def test_create_rejects_blank_name(self):
        self.client.force_login(self.user_a)

        response = self.client.post(reverse("clients:create"), {"name": " "})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Client.objects.filter(business=self.business_a, name=" ").exists())

    def test_detail_is_scoped_to_business(self):
        self.client.force_login(self.user_a)

        own_response = self.client.get(reverse("clients:detail", args=[self.client_a.pk]))
        other_response = self.client.get(reverse("clients:detail", args=[self.other_client.pk]))

        self.assertEqual(own_response.status_code, 200)
        self.assertContains(own_response, "Sofía Pérez")
        self.assertContains(own_response, 'href="tel:1155551111"')
        self.assertEqual(other_response.status_code, 404)

    def test_detail_separates_upcoming_and_past_history(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        yesterday = timezone.localdate() - timedelta(days=1)
        tz = timezone.get_current_timezone()

        def appointment(day, hour, service_name, status):
            start = timezone.make_aware(datetime.combine(day, time(hour, 0)), tz)
            return Appointment.objects.create(
                business=self.business_a,
                client=self.client_a,
                service=self.service_a,
                service_name=service_name,
                duration_minutes=60,
                price="12000",
                start_at=start,
                end_at=start + timedelta(minutes=60),
                status=status,
            )

        past = appointment(
            yesterday,
            10,
            "Servicio del pasado",
            Appointment.STATUS_COMPLETED,
        )
        upcoming = appointment(
            tomorrow,
            10,
            "Servicio futuro",
            Appointment.STATUS_SCHEDULED,
        )
        appointment(
            tomorrow,
            12,
            "Servicio futuro no asistido",
            Appointment.STATUS_NO_SHOW,
        )
        appointment(
            tomorrow,
            14,
            "Servicio futuro cancelado",
            Appointment.STATUS_CANCELLED,
        )
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("clients:detail", args=[self.client_a.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["upcoming"]), [upcoming])
        self.assertEqual(list(response.context["history"]), [past])
        self.assertNotContains(response, "Servicio futuro no asistido")
        self.assertNotContains(response, "Servicio futuro cancelado")

    def test_edit_is_scoped_to_business_and_updates_data(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse("clients:edit", args=[self.client_a.pk]),
            {
                "name": "Sofía Actualizada",
                "phone": "11 0000 0000",
                "email": "",
                "notes": "",
            },
        )

        self.assertRedirects(
            response,
            reverse("clients:detail", args=[self.client_a.pk]),
        )
        self.client_a.refresh_from_db()
        self.assertEqual(self.client_a.name, "Sofía Actualizada")
        self.assertEqual(self.client_a.phone, "11 0000 0000")
        self.assertEqual(self.client_a.email, "")

        other_response = self.client.get(reverse("clients:edit", args=[self.other_client.pk]))
        self.assertEqual(other_response.status_code, 404)

    def test_archive_and_activate_are_scoped_to_business(self):
        self.client.force_login(self.user_a)

        archive_response = self.client.post(reverse("clients:archive", args=[self.client_a.pk]))

        self.assertRedirects(
            archive_response,
            reverse("clients:detail", args=[self.client_a.pk]),
        )
        self.client_a.refresh_from_db()
        self.assertFalse(self.client_a.is_active)

        other_archive_response = self.client.post(
            reverse("clients:archive", args=[self.other_client.pk])
        )
        self.assertEqual(other_archive_response.status_code, 404)

        activate_response = self.client.post(reverse("clients:activate", args=[self.client_a.pk]))
        self.assertRedirects(
            activate_response,
            reverse("clients:detail", args=[self.client_a.pk]),
        )
        self.client_a.refresh_from_db()
        self.assertTrue(self.client_a.is_active)

    def test_post_only_actions_reject_get(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("clients:archive", args=[self.client_a.pk]))

        self.assertEqual(response.status_code, 405)
