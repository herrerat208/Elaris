from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from businesses.models import Business, Service
from catalog.models import Specialty
from clients.models import Client

from .models import Appointment, ScheduleBlock, TimeOff


class AgendaTestBase(TestCase):
    def setUp(self):
        self.unas = Specialty.objects.get(slug="unas")
        self.user_a = User.objects.create_user(
            email="agenda-a@example.com",
            password="ClaveSegura123!",
        )
        self.user_b = User.objects.create_user(
            email="agenda-b@example.com",
            password="ClaveSegura123!",
        )
        self.business_a = Business.objects.create(owner=self.user_a, name="Agenda A")
        self.business_a.specialties.set([self.unas])
        self.business_b = Business.objects.create(owner=self.user_b, name="Agenda B")
        self.business_b.specialties.set([self.unas])

        self.service_a = Service.objects.create(
            business=self.business_a,
            specialty=self.unas,
            name="Semi permanente",
            duration_minutes=60,
            price=Decimal("12000.00"),
        )
        self.service_b = Service.objects.create(
            business=self.business_b,
            specialty=self.unas,
            name="Servicio de B",
            duration_minutes=60,
            price=Decimal("9000.00"),
        )
        self.client_a = Client.objects.create(
            business=self.business_a,
            name="Cliente A",
            phone="11 5555 1111",
        )
        self.client_b = Client.objects.create(
            business=self.business_b,
            name="Cliente B",
            phone="11 5555 2222",
        )
        self.today = timezone.localdate()
        self.future_day = self.today + timedelta(days=7)

    def _create_week_schedule(self, business=None):
        business = business or self.business_a
        for weekday in range(7):
            ScheduleBlock.objects.create(
                business=business,
                weekday=weekday,
                start_time=time(9, 0),
                end_time=time(19, 0),
            )

    def _start_at(self, day=None, hour=10, minute=0):
        day = day or self.future_day
        return timezone.make_aware(
            datetime.combine(day, time(hour, minute)),
            timezone.get_current_timezone(),
        )

    def _appointment(
        self,
        *,
        day=None,
        hour=10,
        status=Appointment.STATUS_SCHEDULED,
        price=Decimal("12000.00"),
        business=None,
        client=None,
        service=None,
    ):
        business = business or self.business_a
        client = client or self.client_a
        service = service or self.service_a
        start_at = self._start_at(day, hour)
        return Appointment.objects.create(
            business=business,
            client=client,
            service=service,
            service_name=service.name,
            duration_minutes=service.duration_minutes,
            price=price,
            start_at=start_at,
            end_at=start_at + timedelta(minutes=service.duration_minutes),
            status=status,
        )

    def _formset_data(self, rows, initial_forms=0):
        data = {
            "blocks-TOTAL_FORMS": str(len(rows)),
            "blocks-INITIAL_FORMS": str(initial_forms),
            "blocks-MIN_NUM_FORMS": "0",
            "blocks-MAX_NUM_FORMS": "1000",
        }
        for index, row in enumerate(rows):
            for key, value in row.items():
                data[f"blocks-{index}-{key}"] = value
        return data


class AgendaAccessTests(AgendaTestBase):
    def test_agenda_requires_login(self):
        for url in (
            reverse("agenda:week"),
            reverse("agenda:day"),
            reverse("agenda:schedule"),
            reverse("agenda:income"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response.url)

    def test_agenda_requires_business(self):
        user_without_business = User.objects.create_user(
            email="sin-agenda@example.com",
            password="ClaveSegura123!",
        )
        self.client.force_login(user_without_business)

        for url in (
            reverse("agenda:week"),
            reverse("agenda:schedule"),
            reverse("agenda:income"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, reverse("businesses:onboarding"))


class ScheduleTests(AgendaTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user_a)

    def test_schedule_page_renders(self):
        response = self.client.get(reverse("agenda:schedule"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tus horarios")
        self.assertContains(response, "Usar horario sugerido")
        self.assertContains(response, "Días libres")

    def test_schedule_post_creates_block_for_own_business(self):
        data = self._formset_data([{"weekday": "0", "start_time": "09:00", "end_time": "13:00"}])

        response = self.client.post(reverse("agenda:schedule"), data)

        self.assertRedirects(response, reverse("agenda:schedule"))
        block = ScheduleBlock.objects.get(business=self.business_a)
        self.assertEqual(block.weekday, 0)
        self.assertEqual(block.start_time, time(9, 0))
        self.assertEqual(block.end_time, time(13, 0))
        self.assertFalse(ScheduleBlock.objects.filter(business=self.business_b).exists())

    def test_schedule_ignores_blank_extra_form(self):
        data = self._formset_data(
            [
                {"weekday": "0", "start_time": "09:00", "end_time": "13:00"},
                {"weekday": "", "start_time": "", "end_time": ""},
            ]
        )

        response = self.client.post(reverse("agenda:schedule"), data)

        self.assertRedirects(response, reverse("agenda:schedule"))
        self.assertEqual(ScheduleBlock.objects.filter(business=self.business_a).count(), 1)

    def test_schedule_rejects_overlapping_blocks(self):
        data = self._formset_data(
            [
                {"weekday": "0", "start_time": "09:00", "end_time": "12:00"},
                {"weekday": "0", "start_time": "11:00", "end_time": "13:00"},
            ]
        )

        response = self.client.post(reverse("agenda:schedule"), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "se superpone")
        self.assertEqual(ScheduleBlock.objects.filter(business=self.business_a).count(), 0)

    def test_schedule_can_delete_existing_block(self):
        block = ScheduleBlock.objects.create(
            business=self.business_a,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(13, 0),
        )
        data = self._formset_data(
            [
                {
                    "id": str(block.pk),
                    "weekday": "0",
                    "start_time": "09:00",
                    "end_time": "13:00",
                    "DELETE": "on",
                }
            ],
            initial_forms=1,
        )

        response = self.client.post(reverse("agenda:schedule"), data)

        self.assertRedirects(response, reverse("agenda:schedule"))
        self.assertFalse(ScheduleBlock.objects.filter(pk=block.pk).exists())

    def test_suggested_schedule_creates_blocks(self):
        response = self.client.post(reverse("agenda:schedule_suggested"))

        self.assertRedirects(response, reverse("agenda:schedule"))
        blocks = ScheduleBlock.objects.filter(business=self.business_a)
        self.assertEqual(blocks.count(), 11)
        self.assertEqual(blocks.filter(weekday=5).count(), 1)
        self.assertEqual(blocks.filter(weekday=6).count(), 0)

    def test_suggested_schedule_does_not_duplicate_existing_blocks(self):
        ScheduleBlock.objects.create(
            business=self.business_a,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(13, 0),
        )

        response = self.client.post(reverse("agenda:schedule_suggested"))

        self.assertRedirects(response, reverse("agenda:schedule"))
        self.assertEqual(ScheduleBlock.objects.filter(business=self.business_a).count(), 1)

    def test_schedule_only_renders_own_blocks(self):
        own_block = ScheduleBlock.objects.create(
            business=self.business_a,
            weekday=0,
            start_time=time(6, 15),
            end_time=time(8, 0),
        )
        ScheduleBlock.objects.create(
            business=self.business_b,
            weekday=1,
            start_time=time(10, 0),
            end_time=time(12, 0),
        )

        response = self.client.get(reverse("agenda:schedule"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(own_block, response.context["formset"].get_queryset())
        self.assertNotIn(
            ScheduleBlock.objects.get(business=self.business_b),
            response.context["formset"].get_queryset(),
        )

    def test_time_off_create_and_delete(self):
        response = self.client.post(
            reverse("agenda:time_off_create"),
            {
                "start_date": self.future_day.isoformat(),
                "end_date": self.future_day.isoformat(),
                "reason": "Trámite",
            },
        )

        self.assertRedirects(response, reverse("agenda:schedule"))
        time_off = TimeOff.objects.get(business=self.business_a)
        self.assertEqual(time_off.start_date, self.future_day)
        self.assertTrue(time_off.is_single_day)

        response = self.client.post(reverse("agenda:time_off_delete", args=[time_off.pk]))

        self.assertRedirects(response, reverse("agenda:schedule"))
        self.assertFalse(TimeOff.objects.filter(pk=time_off.pk).exists())

    def test_time_off_rejects_end_before_start(self):
        response = self.client.post(
            reverse("agenda:time_off_create"),
            {
                "start_date": self.future_day.isoformat(),
                "end_date": (self.future_day - timedelta(days=1)).isoformat(),
                "reason": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "La fecha de fin no puede ser anterior a la de inicio.",
        )
        self.assertFalse(TimeOff.objects.filter(business=self.business_a).exists())

    def test_time_off_cannot_be_deleted_from_another_business(self):
        time_off_b = TimeOff.objects.create(
            business=self.business_b,
            start_date=self.future_day,
            end_date=self.future_day,
        )

        response = self.client.post(reverse("agenda:time_off_delete", args=[time_off_b.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(TimeOff.objects.filter(pk=time_off_b.pk).exists())

    def test_post_only_schedule_actions_reject_get(self):
        for url in (
            reverse("agenda:schedule_suggested"),
            reverse("agenda:time_off_create"),
            reverse("agenda:time_off_delete", args=[1]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 405)


class AvailabilityTests(AgendaTestBase):
    def setUp(self):
        super().setUp()
        self._create_week_schedule()
        self.client.force_login(self.user_a)

    def test_availability_lists_slots(self):
        response = self.client.get(
            reverse("agenda:availability"),
            {"fecha": self.future_day.isoformat(), "servicio": self.service_a.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "09:00")
        self.assertContains(response, "18:00")
        self.assertContains(response, "Turnos de 60 min")

    def test_availability_excludes_existing_appointment(self):
        self._appointment(day=self.future_day, hour=10)

        response = self.client.get(
            reverse("agenda:availability"),
            {"fecha": self.future_day.isoformat(), "servicio": self.service_a.pk},
        )

        self.assertNotContains(response, "10:00")
        self.assertContains(response, "11:00")

    def test_availability_respects_time_off(self):
        TimeOff.objects.create(
            business=self.business_a,
            start_date=self.future_day,
            end_date=self.future_day,
        )

        response = self.client.get(
            reverse("agenda:availability"),
            {"fecha": self.future_day.isoformat(), "servicio": self.service_a.pk},
        )

        self.assertContains(response, "Este día está marcado como libre")
        self.assertNotContains(response, "09:00")

    def test_availability_ignores_service_from_another_business(self):
        response = self.client.get(
            reverse("agenda:availability"),
            {"fecha": self.future_day.isoformat(), "servicio": self.service_b.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elegí un servicio para ver los horarios disponibles.")
        self.assertNotContains(response, "09:00")

    def test_availability_handles_invalid_service_id(self):
        response = self.client.get(
            reverse("agenda:availability"),
            {"fecha": self.future_day.isoformat(), "servicio": "no-es-un-id"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elegí un servicio para ver los horarios disponibles.")


class AppointmentTests(AgendaTestBase):
    def setUp(self):
        super().setUp()
        self._create_week_schedule()
        self.client.force_login(self.user_a)
        self.create_url = reverse("agenda:appointment_create")

    def _post_data(self, **overrides):
        data = {
            "client": self.client_a.pk,
            "service": self.service_a.pk,
            "start_at": f"{self.future_day.isoformat()}T10:00",
            "price": "",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_create_prefills_client_from_query_param(self):
        response = self.client.get(self.create_url, {"cliente": self.client_a.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["client"], self.client_a)

    def test_create_snapshots_service_data_and_copies_price(self):
        response = self.client.post(self.create_url, self._post_data())

        appointment = Appointment.objects.get(business=self.business_a)
        self.assertRedirects(
            response,
            reverse("agenda:appointment_detail", args=[appointment.pk]),
        )
        self.assertEqual(appointment.service_name, "Semi permanente")
        self.assertEqual(appointment.duration_minutes, 60)
        self.assertEqual(appointment.end_at, self._start_at(self.future_day, 11))
        self.assertEqual(appointment.price, Decimal("12000.00"))
        self.assertEqual(appointment.status, Appointment.STATUS_SCHEDULED)

    def test_create_keeps_explicit_zero_price(self):
        self.client.post(self.create_url, self._post_data(price="0"))

        appointment = Appointment.objects.get(business=self.business_a)
        self.assertEqual(appointment.price, Decimal("0.00"))

    def test_create_rejects_overlap(self):
        self._appointment(day=self.future_day, hour=10)

        response = self.client.post(
            self.create_url,
            self._post_data(start_at=f"{self.future_day.isoformat()}T10:30"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya tenés un turno en ese horario.")
        self.assertEqual(Appointment.objects.filter(business=self.business_a).count(), 1)

    def test_create_rejects_outside_schedule(self):
        response = self.client.post(
            self.create_url,
            self._post_data(start_at=f"{self.future_day.isoformat()}T20:00"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "El turno tiene que entrar completo dentro de un bloque de tu horario.",
        )
        self.assertFalse(Appointment.objects.filter(business=self.business_a).exists())

    def test_create_rejects_day_without_schedule(self):
        ScheduleBlock.objects.filter(
            business=self.business_a,
            weekday=self.future_day.weekday(),
        ).delete()

        response = self.client.post(self.create_url, self._post_data())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ese día no tenés horario de atención.")
        self.assertFalse(Appointment.objects.filter(business=self.business_a).exists())

    def test_create_rejects_day_off(self):
        TimeOff.objects.create(
            business=self.business_a,
            start_date=self.future_day,
            end_date=self.future_day,
        )

        response = self.client.post(self.create_url, self._post_data())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ese día está marcado como libre.")
        self.assertFalse(Appointment.objects.filter(business=self.business_a).exists())

    def test_create_rejects_client_from_another_business(self):
        response = self.client.post(
            self.create_url,
            self._post_data(client=self.client_b.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Appointment.objects.filter(business=self.business_a).exists())

    def test_create_rejects_service_from_another_business(self):
        response = self.client.post(
            self.create_url,
            self._post_data(service=self.service_b.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Appointment.objects.filter(business=self.business_a).exists())

    def test_create_prefills_date_service_and_time(self):
        response = self.client.get(
            self.create_url,
            {
                "fecha": self.future_day.isoformat(),
                "servicio": self.service_a.pk,
                "inicio": "10:00",
            },
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["service"], self.service_a)
        self.assertEqual(form.initial["start_at"], self._start_at(self.future_day, 10))
        self.assertContains(response, "Nuevo turno")

    def test_inactive_client_and_service_are_not_offered_for_new_appointments(self):
        self.client_a.is_active = False
        self.client_a.save(update_fields=("is_active", "updated_at"))
        self.service_a.is_active = False
        self.service_a.save(update_fields=("is_active", "updated_at"))

        response = self.client.get(self.create_url)

        form = response.context["form"]
        self.assertNotIn(self.client_a, form.fields["client"].queryset)
        self.assertNotIn(self.service_a, form.fields["service"].queryset)

    def test_edit_reschedules_appointment(self):
        appointment = self._appointment(day=self.future_day, hour=10)

        response = self.client.post(
            reverse("agenda:appointment_edit", args=[appointment.pk]),
            self._post_data(start_at=f"{self.future_day.isoformat()}T12:00"),
        )

        self.assertRedirects(
            response,
            reverse("agenda:appointment_detail", args=[appointment.pk]),
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.start_at, self._start_at(self.future_day, 12))
        self.assertEqual(appointment.end_at, self._start_at(self.future_day, 13))

    def test_edit_form_renders_local_time(self):
        appointment = self._appointment(day=self.future_day, hour=10)

        response = self.client.get(reverse("agenda:appointment_edit", args=[appointment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.future_day.isoformat()}T10:00"')

    def test_edit_price_does_not_require_current_slot(self):
        appointment = self._appointment(day=self.future_day, hour=10)
        ScheduleBlock.objects.filter(
            business=self.business_a,
            weekday=self.future_day.weekday(),
        ).delete()

        response = self.client.post(
            reverse("agenda:appointment_edit", args=[appointment.pk]),
            self._post_data(price="15000"),
        )

        self.assertRedirects(
            response,
            reverse("agenda:appointment_detail", args=[appointment.pk]),
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.start_at, self._start_at(self.future_day, 10))
        self.assertEqual(appointment.price, Decimal("15000.00"))

    def test_edit_preserves_service_snapshot(self):
        appointment = self._appointment(day=self.future_day, hour=10)
        self.service_a.name = "Semi renombrado"
        self.service_a.duration_minutes = 120
        self.service_a.price = Decimal("20000.00")
        self.service_a.save(update_fields=("name", "duration_minutes", "price", "updated_at"))

        response = self.client.post(
            reverse("agenda:appointment_edit", args=[appointment.pk]),
            self._post_data(price="12000", notes="Nota actualizada"),
        )

        self.assertRedirects(
            response,
            reverse("agenda:appointment_detail", args=[appointment.pk]),
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.service_name, "Semi permanente")
        self.assertEqual(appointment.duration_minutes, 60)
        self.assertEqual(appointment.end_at, self._start_at(self.future_day, 11))
        self.assertEqual(appointment.notes, "Nota actualizada")

    def test_edit_still_validates_when_schedule_changes(self):
        appointment = self._appointment(day=self.future_day, hour=10)

        response = self.client.post(
            reverse("agenda:appointment_edit", args=[appointment.pk]),
            self._post_data(start_at=f"{self.future_day.isoformat()}T20:00"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "El turno tiene que entrar completo dentro de un bloque de tu horario.",
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.start_at, self._start_at(self.future_day, 10))

    def test_edit_rejects_overlap(self):
        appointment = self._appointment(day=self.future_day, hour=10)
        self._appointment(day=self.future_day, hour=12)

        response = self.client.post(
            reverse("agenda:appointment_edit", args=[appointment.pk]),
            self._post_data(start_at=f"{self.future_day.isoformat()}T12:00"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya tenés un turno en ese horario.")
        appointment.refresh_from_db()
        self.assertEqual(appointment.start_at, self._start_at(self.future_day, 10))

    def test_detail_is_scoped_and_includes_reminder(self):
        appointment = self._appointment(day=self.future_day, hour=10)
        other_appointment = self._appointment(
            day=self.future_day,
            hour=10,
            business=self.business_b,
            client=self.client_b,
            service=self.service_b,
        )

        response = self.client.get(reverse("agenda:appointment_detail", args=[appointment.pk]))
        other_response = self.client.get(
            reverse("agenda:appointment_detail", args=[other_appointment.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente A")
        self.assertContains(response, "Hola Cliente A")
        self.assertContains(response, "Semi permanente")
        self.assertContains(response, "10:00")
        self.assertNotContains(response, "13:00")
        self.assertEqual(other_response.status_code, 404)

    def test_edit_is_scoped_to_business(self):
        other_appointment = self._appointment(
            day=self.future_day,
            hour=10,
            business=self.business_b,
            client=self.client_b,
            service=self.service_b,
        )

        response = self.client.get(reverse("agenda:appointment_edit", args=[other_appointment.pk]))

        self.assertEqual(response.status_code, 404)


class AppointmentStatusTests(AgendaTestBase):
    def setUp(self):
        super().setUp()
        self._create_week_schedule()
        self.client.force_login(self.user_a)

    def test_complete_changes_status_and_redirects_to_detail(self):
        appointment = self._appointment(day=self.future_day, hour=10)

        response = self.client.post(reverse("agenda:appointment_complete", args=[appointment.pk]))

        self.assertRedirects(
            response,
            reverse("agenda:appointment_detail", args=[appointment.pk]),
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_COMPLETED)

    def test_cancel_and_reopen(self):
        appointment = self._appointment(day=self.future_day, hour=10)

        self.client.post(reverse("agenda:appointment_cancel", args=[appointment.pk]))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_CANCELLED)

        self.client.post(reverse("agenda:appointment_reopen", args=[appointment.pk]))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_SCHEDULED)

    def test_no_show_and_reopen(self):
        appointment = self._appointment(day=self.future_day, hour=10)

        self.client.post(reverse("agenda:appointment_no_show", args=[appointment.pk]))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_NO_SHOW)

        self.client.post(reverse("agenda:appointment_reopen", args=[appointment.pk]))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_SCHEDULED)

    def test_reopen_fails_if_slot_was_taken(self):
        appointment = self._appointment(day=self.future_day, hour=10)
        self.client.post(reverse("agenda:appointment_cancel", args=[appointment.pk]))
        self._appointment(day=self.future_day, hour=10)

        response = self.client.post(reverse("agenda:appointment_reopen", args=[appointment.pk]))

        self.assertRedirects(
            response,
            reverse("agenda:appointment_detail", args=[appointment.pk]),
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_CANCELLED)

    def test_completed_appointment_cannot_be_reopened(self):
        appointment = self._appointment(
            day=self.future_day,
            hour=10,
            status=Appointment.STATUS_COMPLETED,
        )

        response = self.client.post(reverse("agenda:appointment_reopen", args=[appointment.pk]))

        self.assertRedirects(
            response,
            reverse("agenda:appointment_detail", args=[appointment.pk]),
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_COMPLETED)

    def test_status_actions_are_scoped_to_business(self):
        other_appointment = self._appointment(
            day=self.future_day,
            hour=10,
            business=self.business_b,
            client=self.client_b,
            service=self.service_b,
        )

        response = self.client.post(
            reverse("agenda:appointment_complete", args=[other_appointment.pk])
        )

        self.assertEqual(response.status_code, 404)
        other_appointment.refresh_from_db()
        self.assertEqual(other_appointment.status, Appointment.STATUS_SCHEDULED)

    def test_status_actions_reject_get(self):
        appointment = self._appointment(day=self.future_day, hour=10)

        response = self.client.get(reverse("agenda:appointment_complete", args=[appointment.pk]))

        self.assertEqual(response.status_code, 405)


class CalendarTests(AgendaTestBase):
    def setUp(self):
        super().setUp()
        self._create_week_schedule()
        self.client.force_login(self.user_a)

    def test_week_shows_only_own_appointments(self):
        own = self._appointment(day=self.future_day, hour=10)
        self._appointment(
            day=self.future_day,
            hour=12,
            business=self.business_b,
            client=self.client_b,
            service=self.service_b,
        )

        response = self.client.get(
            reverse("agenda:week"),
            {"semana": self.future_day.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own.client.name)
        self.assertNotContains(response, "Cliente B")
        self.assertContains(response, "1 turno")

    def test_week_does_not_count_cancelled_appointments(self):
        self._appointment(
            day=self.future_day,
            hour=10,
            status=Appointment.STATUS_CANCELLED,
        )

        response = self.client.get(
            reverse("agenda:week"),
            {"semana": self.future_day.isoformat()},
        )

        self.assertEqual(response.context["appointment_count"], 0)

    def test_day_shows_appointments_and_availability(self):
        appointment = self._appointment(day=self.future_day, hour=10)

        response = self.client.get(
            reverse("agenda:day"),
            {"fecha": self.future_day.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, appointment.client.name)
        self.assertContains(response, "Horarios libres")
        self.assertContains(response, "Turnos de 60 min")

    def test_day_is_scoped_to_business(self):
        own = self._appointment(day=self.future_day, hour=10)
        self._appointment(
            day=self.future_day,
            hour=12,
            business=self.business_b,
            client=self.client_b,
            service=self.service_b,
        )

        response = self.client.get(
            reverse("agenda:day"),
            {"fecha": self.future_day.isoformat()},
        )

        self.assertContains(response, own.client.name)
        self.assertNotContains(response, "Cliente B")

    def test_week_handles_invalid_week(self):
        for value in ("no-es-fecha", "2026-13-01", "2026-02-31"):
            with self.subTest(value=value):
                response = self.client.get(
                    reverse("agenda:week"),
                    {"semana": value},
                )

                self.assertEqual(response.status_code, 200)

    def test_day_handles_invalid_date(self):
        for value in ("no-es-fecha", "2026-13-01", "2026-02-31"):
            with self.subTest(value=value):
                response = self.client.get(
                    reverse("agenda:day"),
                    {"fecha": value},
                )

                self.assertEqual(response.status_code, 200)

    def test_availability_handles_invalid_date(self):
        response = self.client.get(
            reverse("agenda:availability"),
            {"fecha": "2026-13-01", "servicio": self.service_a.pk},
        )

        self.assertEqual(response.status_code, 200)


class IncomeTests(AgendaTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user_a)

    def test_income_counts_only_completed_appointments_with_price(self):
        self._appointment(
            day=self.today,
            hour=9,
            status=Appointment.STATUS_COMPLETED,
            price=Decimal("10000.00"),
        )
        self._appointment(
            day=self.today,
            hour=11,
            status=Appointment.STATUS_COMPLETED,
            price=None,
        )
        self._appointment(
            day=self.today,
            hour=12,
            status=Appointment.STATUS_CANCELLED,
            price=Decimal("5000.00"),
        )
        self._appointment(
            day=self.today,
            hour=13,
            status=Appointment.STATUS_NO_SHOW,
            price=Decimal("3000.00"),
        )
        other_business = self._appointment(
            day=self.today,
            hour=14,
            status=Appointment.STATUS_COMPLETED,
            price=Decimal("99000.00"),
            business=self.business_b,
            client=self.client_b,
            service=self.service_b,
        )

        response = self.client.get(reverse("agenda:income"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["completed_count"], 2)
        self.assertEqual(response.context["income_total"], Decimal("10000.00"))
        self.assertEqual(response.context["average_ticket"], Decimal("10000.00"))
        self.assertEqual(response.context["missing_price_count"], 1)
        self.assertEqual(response.context["cancelled_count"], 1)
        self.assertEqual(response.context["no_show_count"], 1)
        self.assertNotIn(
            other_business,
            list(response.context["completed_list"]),
        )
        self.assertContains(response, "$10.000")

    def test_income_with_no_completed_appointments(self):
        response = self.client.get(reverse("agenda:income"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["completed_count"], 0)
        self.assertEqual(response.context["income_total"], Decimal("0.00"))
        self.assertContains(response, "No hay turnos completados")

    def test_income_handles_invalid_month(self):
        for value in ("invalido", "2026-13", "2026-02-31"):
            with self.subTest(value=value):
                response = self.client.get(
                    reverse("agenda:income"),
                    {"mes": value},
                )

                self.assertEqual(response.status_code, 200)
