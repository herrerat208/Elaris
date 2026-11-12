import csv
import json
from datetime import date, timedelta
from decimal import Decimal
from itertools import groupby

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import AccountEmailForm, StyledPasswordChangeForm
from agenda.availability import day_bounds, get_day_blocks, get_time_off
from agenda.models import Appointment
from catalog.models import ServiceTemplate, Specialty

from .forms import BusinessSettingsForm, OnboardingForm, ServiceForm
from .models import Business, Service
from .utils import business_required, get_business_for


def _group_services(services):
    groups = []
    for _, group_services in groupby(services, key=lambda service: service.specialty_id):
        group = list(group_services)
        groups.append((group[0].specialty, group))
    return groups


def _next_month(month_start):
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1)
    return date(month_start.year, month_start.month + 1, 1)


@login_required
def onboarding(request):
    business = get_business_for(request.user)
    if business is not None:
        return redirect("businesses:dashboard")

    specialties = Specialty.objects.filter(is_active=True).prefetch_related(
        Prefetch(
            "service_templates",
            queryset=ServiceTemplate.objects.filter(is_active=True).order_by("sort_order", "name"),
            to_attr="active_templates",
        )
    )

    if request.method == "POST":
        form = OnboardingForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                business = Business.objects.create(
                    owner=request.user,
                    name=form.cleaned_data["business_name"],
                )
                business.specialties.set(form.cleaned_data["specialties"])

                for template in form.cleaned_data["services"]:
                    Service.objects.create(
                        business=business,
                        specialty=template.specialty,
                        name=template.name,
                        duration_minutes=template.default_duration_minutes,
                    )

            messages.success(
                request,
                "Tu espacio está listo. Ya podés completar precios y configurar tus horarios.",
            )
            return redirect("businesses:dashboard")
    else:
        form = OnboardingForm()

    if request.method == "POST":
        selected_specialties = [
            int(value) for value in request.POST.getlist("specialties") if value.isdigit()
        ]
        selected_services = [
            int(value) for value in request.POST.getlist("services") if value.isdigit()
        ]
    else:
        selected_specialties = []
        selected_services = []

    return render(
        request,
        "businesses/onboarding.html",
        {
            "form": form,
            "specialties": specialties,
            "selected_specialties": selected_specialties,
            "selected_services": selected_services,
        },
    )


@business_required
def dashboard(request):
    business = request.business
    today = timezone.localdate()
    now = timezone.now()

    all_services = list(
        business.services.select_related("specialty").order_by(
            "specialty__sort_order", "specialty_id", "id"
        )
    )
    active_services = [service for service in all_services if service.is_active]
    inactive_services = [service for service in all_services if not service.is_active]
    specialties = list(business.specialties.filter(is_active=True).order_by("sort_order", "name"))
    missing_prices = sum(1 for service in active_services if service.price is None)
    first_pending_service = next(
        (service for service in active_services if service.price is None),
        None,
    )

    today_start, today_end = day_bounds(today)
    today_appointments = list(
        business.appointments.filter(
            start_at__gte=today_start,
            start_at__lt=today_end,
        )
        .exclude(status=Appointment.STATUS_CANCELLED)
        .select_related("client", "service")
        .order_by("start_at")
    )
    next_appointment = (
        business.appointments.filter(
            status=Appointment.STATUS_SCHEDULED,
            start_at__gte=now,
        )
        .select_related("client", "service")
        .order_by("start_at")
        .first()
    )

    month_start = today.replace(day=1)
    month_end = _next_month(month_start)
    month_start_at, _ = day_bounds(month_start)
    month_end_at, _ = day_bounds(month_end)
    month_completed = business.appointments.filter(
        status=Appointment.STATUS_COMPLETED,
        start_at__gte=month_start_at,
        start_at__lt=month_end_at,
    )
    month_income = month_completed.aggregate(total=Sum("price"))["total"] or Decimal("0.00")
    month_completed_count = month_completed.count()
    active_clients_count = business.clients.filter(is_active=True).count()
    has_schedule = business.schedule_blocks.exists()
    has_appointments = business.appointments.exists()
    today_blocks = get_day_blocks(business, today)
    today_time_off = get_time_off(business, today)
    tomorrow = today + timedelta(days=1)
    tomorrow_start, tomorrow_end = day_bounds(tomorrow)
    tomorrow_scheduled = business.appointments.filter(
        status=Appointment.STATUS_SCHEDULED,
        start_at__gte=tomorrow_start,
        start_at__lt=tomorrow_end,
    )
    tomorrow_reminders_count = tomorrow_scheduled.count()
    tomorrow_pending_reminders_count = tomorrow_scheduled.filter(reminded_at__isnull=True).count()

    price_step = {
        "label": "Completar precios",
        "detail": (
            "Listo"
            if active_services and missing_prices == 0
            else f"{missing_prices} por completar"
            if missing_prices
            else "Pendiente"
        ),
        "done": bool(active_services) and missing_prices == 0,
    }
    if first_pending_service is not None:
        price_step["action_url"] = reverse(
            "businesses:service_edit",
            args=[first_pending_service.pk],
        )
        price_step["action_label"] = "Completar"
    elif active_services:
        price_step["action_url"] = reverse("businesses:service_list")
        price_step["action_label"] = "Ver servicios"

    setup_steps = [
        {
            "label": "Cargar tus servicios",
            "detail": "Listo" if active_services else "Pendiente",
            "done": bool(active_services),
            "action_url": reverse("businesses:service_list") if not active_services else "",
            "action_label": "Agregar",
        },
        price_step,
        {
            "label": "Configurar horarios",
            "detail": "Listo" if has_schedule else "Pendiente",
            "done": has_schedule,
            "action_url": reverse("agenda:schedule") if not has_schedule else "",
            "action_label": "Configurar",
        },
        {
            "label": "Cargar tu primer turno",
            "detail": "Listo" if has_appointments else "Pendiente",
            "done": has_appointments,
            "action_url": reverse("agenda:appointment_create") if not has_appointments else "",
            "action_label": "Agendar",
        },
    ]

    return render(
        request,
        "businesses/dashboard.html",
        {
            "business": business,
            "specialties": specialties,
            "service_groups": _group_services(active_services),
            "services_count": len(active_services),
            "inactive_services": inactive_services,
            "inactive_count": len(inactive_services),
            "specialties_count": len(specialties),
            "missing_prices": missing_prices,
            "first_pending_service": first_pending_service,
            "setup_steps": setup_steps,
            "setup_complete": all(step["done"] for step in setup_steps),
            "pending_steps_count": sum(1 for step in setup_steps if not step["done"]),
            "today": today,
            "today_appointments": today_appointments,
            "today_appointments_count": len(today_appointments),
            "next_appointment": next_appointment,
            "today_blocks": today_blocks,
            "today_time_off": today_time_off,
            "tomorrow_reminders_count": tomorrow_reminders_count,
            "tomorrow_pending_reminders_count": tomorrow_pending_reminders_count,
            "reminders_url": reverse("agenda:reminders"),
            "settings_url": reverse("businesses:settings"),
            "has_schedule": has_schedule,
            "active_clients_count": active_clients_count,
            "month_income": month_income,
            "month_completed_count": month_completed_count,
            "new_appointment_url": reverse("agenda:appointment_create"),
            "today_url": f"{reverse('agenda:day')}?fecha={today.isoformat()}",
            "income_url": reverse("agenda:income"),
        },
    )


@business_required
def service_list(request):
    business = request.business
    all_services = list(
        business.services.select_related("specialty").order_by(
            "specialty__sort_order", "specialty_id", "id"
        )
    )
    active_services = [service for service in all_services if service.is_active]
    inactive_services = [service for service in all_services if not service.is_active]
    missing_prices = sum(1 for service in active_services if service.price is None)

    return render(
        request,
        "businesses/service_list.html",
        {
            "business": business,
            "service_groups": _group_services(active_services),
            "active_services": active_services,
            "inactive_services": inactive_services,
            "services_count": len(active_services),
            "inactive_count": len(inactive_services),
            "missing_prices": missing_prices,
            "specialties_count": business.specialties.filter(is_active=True).count(),
        },
    )


@business_required
def service_create(request):
    business = request.business
    initial = {}
    if request.method == "GET":
        first_specialty = business.specialties.filter(is_active=True).first()
        if first_specialty is not None:
            initial["specialty"] = first_specialty
    form = ServiceForm(request.POST or None, business=business, initial=initial)

    if request.method == "POST" and form.is_valid():
        service = form.save(commit=False)
        service.business = business
        service.save()
        messages.success(request, "Servicio agregado.")
        return redirect("businesses:service_list")

    return render(
        request,
        "businesses/service_form.html",
        {
            "business": business,
            "service": None,
            "form": form,
            "is_edit": False,
        },
    )


@business_required
def service_edit(request, pk):
    business = request.business
    service = get_object_or_404(Service, pk=pk, business=business)
    form = ServiceForm(
        request.POST or None,
        instance=service,
        business=business,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Servicio actualizado.")
        return redirect("businesses:service_list")

    return render(
        request,
        "businesses/service_form.html",
        {
            "business": business,
            "service": service,
            "form": form,
            "is_edit": True,
        },
    )


@business_required
@require_POST
def service_archive(request, pk):
    business = request.business
    service = get_object_or_404(Service, pk=pk, business=business)
    service.is_active = False
    service.save(update_fields=("is_active", "updated_at"))
    messages.success(
        request,
        "Servicio archivado. Su historial y sus turnos quedan guardados.",
    )
    return redirect("businesses:service_list")


@business_required
@require_POST
def service_activate(request, pk):
    business = request.business
    service = get_object_or_404(Service, pk=pk, business=business)
    if not business.specialties.filter(pk=service.specialty_id).exists():
        messages.error(
            request,
            f"El rubro {service.specialty.name} no está activo en tu espacio. "
            "Agregalo desde Configuración antes de reactivar el servicio.",
        )
        return redirect("businesses:service_list")
    service.is_active = True
    service.save(update_fields=("is_active", "updated_at"))
    messages.success(request, "Servicio reactivado.")
    return redirect("businesses:service_list")


@business_required
def settings(request):
    business = request.business
    business_form = BusinessSettingsForm(business=business)
    email_form = AccountEmailForm(user=request.user)
    password_form = StyledPasswordChangeForm(user=request.user)

    if request.method == "POST":
        form_name = request.POST.get("form_name")
        if form_name == "business":
            business_form = BusinessSettingsForm(request.POST, business=business)
            if business_form.is_valid():
                business.name = business_form.cleaned_data["name"]
                business.whatsapp = business_form.cleaned_data["whatsapp"]
                business.save(update_fields=("name", "whatsapp", "updated_at"))
                business.specialties.set(business_form.cleaned_data["specialties"])
                messages.success(request, "Configuración del espacio actualizada.")
                return redirect("businesses:settings")
        elif form_name == "account":
            email_form = AccountEmailForm(request.POST, user=request.user)
            if email_form.is_valid():
                request.user.email = email_form.cleaned_data["email"]
                request.user.save(update_fields=("email",))
                messages.success(request, "Email de la cuenta actualizado.")
                return redirect("businesses:settings")
        elif form_name == "password":
            password_form = StyledPasswordChangeForm(
                user=request.user,
                data=request.POST,
            )
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, "Contraseña actualizada.")
                return redirect("businesses:settings")

    if business_form.is_bound:
        selected_specialty_ids = {
            int(value)
            for value in business_form.data.getlist("specialties")
            if value.isdigit()
        }
    else:
        selected_specialty_ids = {
            int(value)
            for value in business_form.initial.get("specialties", [])
        }

    return render(
        request,
        "businesses/settings.html",
        {
            "business": business,
            "business_form": business_form,
            "email_form": email_form,
            "password_form": password_form,
            "specialty_options": business_form.fields["specialties"].queryset,
            "selected_specialty_ids": selected_specialty_ids,
        },
    )


def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    response.write("sep=;\r\n")
    writer = csv.writer(response, delimiter=";", lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return response


def _export_datetime(value):
    if value is None:
        return ""
    return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")


def _export_date(value):
    return value.strftime("%d/%m/%Y") if value else ""


@business_required
def export_clients(request):
    rows = [
        [
            client.name,
            client.phone,
            client.email,
            client.notes,
            "Sí" if client.is_active else "No",
            _export_datetime(client.created_at),
        ]
        for client in request.business.clients.order_by("name", "id")
    ]
    return _csv_response(
        "elaris-clientes.csv",
        [
            "Nombre",
            "Teléfono / WhatsApp",
            "Email",
            "Notas",
            "Activo",
            "Creado",
        ],
        rows,
    )


@business_required
def export_appointments(request):
    rows = []
    appointments = (
        request.business.appointments.select_related("client", "service")
        .order_by("start_at", "id")
    )
    for appointment in appointments:
        rows.append(
            [
                _export_datetime(appointment.start_at),
                _export_datetime(appointment.end_at),
                appointment.client.name,
                appointment.service_name,
                appointment.duration_minutes,
                appointment.price if appointment.price is not None else "",
                appointment.get_status_display(),
                "Sí" if appointment.reminded_at else "No",
                appointment.amount_paid if appointment.amount_paid is not None else "",
                appointment.get_payment_method_display() if appointment.payment_method else "",
                appointment.notes,
            ]
        )
    return _csv_response(
        "elaris-turnos.csv",
        [
            "Inicio",
            "Fin",
            "Cliente",
            "Servicio",
            "Duración (min)",
            "Precio",
            "Estado",
            "Recordado",
            "Monto cobrado",
            "Medio de pago",
            "Notas",
        ],
        rows,
    )


def _parse_export_month(value):
    if not value:
        return None
    try:
        year, month = (int(part) for part in value.split("-", 1))
        return date(year, month, 1)
    except (TypeError, ValueError):
        return None


@business_required
def export_income(request):
    month_start = _parse_export_month(request.GET.get("mes"))
    completed = request.business.appointments.filter(
        status=Appointment.STATUS_COMPLETED
    ).select_related("client")
    if month_start:
        start_at, _ = day_bounds(month_start)
        _, next_month_at = day_bounds(_next_month(month_start))
        completed = completed.filter(start_at__gte=start_at, start_at__lt=next_month_at)
        filename = f"elaris-ingresos-{month_start:%Y-%m}.csv"
    else:
        filename = "elaris-ingresos.csv"
    rows = [
        [
            _export_datetime(appointment.start_at),
            appointment.client.name,
            appointment.service_name,
            appointment.price if appointment.price is not None else "",
            appointment.amount_paid if appointment.amount_paid is not None else "",
            appointment.get_payment_method_display() if appointment.payment_method else "",
        ]
        for appointment in completed.order_by("-start_at", "-id")
    ]
    return _csv_response(
        filename,
        ["Fecha", "Cliente", "Servicio", "Precio", "Monto cobrado", "Medio de pago"],
        rows,
    )


@business_required
def backup(request):
    business = request.business
    payload = {
        "app": "Elaris",
        "version": 1,
        "generated_at": timezone.now().isoformat(),
        "account": {"email": request.user.email},
        "business": {
            "name": business.name,
            "whatsapp": business.whatsapp,
            "created_at": business.created_at.isoformat(),
            "specialties": [
                {"name": specialty.name, "slug": specialty.slug}
                for specialty in business.specialties.order_by("sort_order", "name")
            ],
        },
        "services": [
            {
                "specialty": service.specialty.name,
                "name": service.name,
                "duration_minutes": service.duration_minutes,
                "price": str(service.price) if service.price is not None else None,
                "is_active": service.is_active,
                "created_at": service.created_at.isoformat(),
            }
            for service in business.services.select_related("specialty").order_by("id")
        ],
        "clients": [
            {
                "name": client.name,
                "phone": client.phone,
                "email": client.email,
                "notes": client.notes,
                "is_active": client.is_active,
                "created_at": client.created_at.isoformat(),
            }
            for client in business.clients.order_by("id")
        ],
        "schedule_blocks": [
            {
                "weekday": block.weekday,
                "start_time": block.start_time.isoformat(),
                "end_time": block.end_time.isoformat(),
            }
            for block in business.schedule_blocks.order_by("weekday", "start_time")
        ],
        "time_off": [
            {
                "start_date": day.start_date.isoformat(),
                "end_date": day.end_date.isoformat(),
                "reason": day.reason,
            }
            for day in business.time_off.order_by("start_date")
        ],
        "appointments": [
            {
                "client": appointment.client.name,
                "service": appointment.service_name,
                "duration_minutes": appointment.duration_minutes,
                "price": str(appointment.price) if appointment.price is not None else None,
                "start_at": appointment.start_at.isoformat(),
                "end_at": appointment.end_at.isoformat(),
                "status": appointment.status,
                "notes": appointment.notes,
                "reminded_at": (
                    appointment.reminded_at.isoformat() if appointment.reminded_at else None
                ),
                "amount_paid": (
                    str(appointment.amount_paid) if appointment.amount_paid is not None else None
                ),
                "payment_method": appointment.payment_method,
            }
            for appointment in business.appointments.select_related("client").order_by("id")
        ],
    }
    response = HttpResponse(
        json.dumps(payload, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="elaris-respaldo.json"'
    return response
