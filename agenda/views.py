from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from businesses.utils import business_required

from .availability import (
    available_slots,
    day_bounds,
    get_day_appointments,
    get_day_blocks,
    get_time_off,
    validate_appointment_slot,
)
from .forms import AppointmentForm, PaymentForm, ScheduleBlockFormSet, TimeOffForm
from .models import WEEKDAY_CHOICES, Appointment, ScheduleBlock, TimeOff


def _parse_date(value):
    if not value:
        return None
    try:
        return parse_date(value)
    except (TypeError, ValueError):
        return None


def _parse_time(value):
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _parse_pk(value):
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_month(value):
    if value:
        try:
            year, month = (int(part) for part in value.split("-", 1))
            return date(year, month, 1)
        except (TypeError, ValueError):
            pass
    return timezone.localdate().replace(day=1)


def _month_bounds(month_start):
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    return month_start, next_month


def _day_url(day):
    return f"{reverse('agenda:day')}?fecha={day.isoformat()}"


def _day_context(business, selected_date, service_id=None):
    schedule_blocks = get_day_blocks(business, selected_date)
    time_off = get_time_off(business, selected_date)
    appointments = list(get_day_appointments(business, selected_date))
    active_services = list(
        business.services.filter(is_active=True)
        .select_related("specialty")
        .order_by("specialty__sort_order", "specialty_id", "id")
    )

    selected_service = None
    if service_id:
        try:
            service_pk = int(service_id)
        except (TypeError, ValueError):
            service_pk = None
        if service_pk:
            selected_service = next(
                (service for service in active_services if service.pk == service_pk),
                None,
            )
    if selected_service is None and active_services:
        selected_service = active_services[0]

    available = []
    if selected_service:
        available = available_slots(
            business,
            selected_date,
            selected_service.duration_minutes,
        )

    return {
        "business": business,
        "selected_date": selected_date,
        "schedule_blocks": schedule_blocks,
        "time_off": time_off,
        "day_off": bool(time_off),
        "appointments": appointments,
        "active_services": active_services,
        "selected_service": selected_service,
        "available_slots": available,
    }


@business_required
def week(request):
    business = request.business
    today = timezone.localdate()
    selected_date = _parse_date(request.GET.get("semana"))
    if selected_date:
        week_start = selected_date - timedelta(days=selected_date.weekday())
    else:
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    start_at, _ = day_bounds(week_start)
    end_at, _ = day_bounds(week_end + timedelta(days=1))
    appointments = list(
        business.appointments.filter(
            start_at__gte=start_at,
            start_at__lt=end_at,
        )
        .exclude(status=Appointment.STATUS_CANCELLED)
        .select_related("client", "service")
        .order_by("start_at")
    )

    appointments_by_day = {week_start + timedelta(days=index): [] for index in range(7)}
    for appointment in appointments:
        local_day = timezone.localtime(appointment.start_at).date()
        appointments_by_day.setdefault(local_day, []).append(appointment)

    time_off_by_day = {}
    for time_off in business.time_off.filter(
        start_date__lte=week_end,
        end_date__gte=week_start,
    ):
        current = max(time_off.start_date, week_start)
        last = min(time_off.end_date, week_end)
        while current <= last:
            time_off_by_day[current] = time_off
            current += timedelta(days=1)

    blocks_by_weekday = {}
    for block in business.schedule_blocks.all():
        blocks_by_weekday.setdefault(block.weekday, []).append(block)

    days = []
    for index in range(7):
        day = week_start + timedelta(days=index)
        blocks = blocks_by_weekday.get(day.weekday(), [])
        time_off = time_off_by_day.get(day)
        days.append(
            {
                "date": day,
                "weekday_label": dict(WEEKDAY_CHOICES)[day.weekday()],
                "is_today": day == today,
                "schedule_blocks": blocks,
                "time_off": time_off,
                "appointments": appointments_by_day.get(day, []),
            }
        )

    return render(
        request,
        "agenda/week.html",
        {
            "business": business,
            "days": days,
            "week_start": week_start,
            "week_end": week_end,
            "prev_week": (week_start - timedelta(days=7)).isoformat(),
            "next_week": (week_start + timedelta(days=7)).isoformat(),
            "today": today,
            "appointment_count": len(appointments),
        },
    )


@business_required
def day(request):
    business = request.business
    selected_date = _parse_date(request.GET.get("fecha")) or timezone.localdate()
    context = _day_context(
        business,
        selected_date,
        service_id=request.GET.get("servicio"),
    )
    today = timezone.localdate()
    context.update(
        {
            "prev_date": (selected_date - timedelta(days=1)).isoformat(),
            "next_date": (selected_date + timedelta(days=1)).isoformat(),
            "is_today": selected_date == today,
            "appointment_count": len(
                [
                    appointment
                    for appointment in context["appointments"]
                    if appointment.status != Appointment.STATUS_CANCELLED
                ]
            ),
        }
    )
    return render(request, "agenda/day.html", context)


@business_required
def reminders(request):
    business = request.business
    today = timezone.localdate()
    selected_date = _parse_date(request.GET.get("fecha")) or today + timedelta(days=1)
    start_at, end_at = day_bounds(selected_date)
    appointments = list(
        business.appointments.filter(
            status=Appointment.STATUS_SCHEDULED,
            start_at__gte=start_at,
            start_at__lt=end_at,
        )
        .select_related("client", "service")
        .order_by("start_at")
    )
    pending = [appointment for appointment in appointments if not appointment.is_reminded]
    all_messages = "\n\n".join(
        f"{timezone.localtime(appointment.start_at):%H:%M} · {appointment.reminder_text}"
        for appointment in pending
    )

    return render(
        request,
        "agenda/reminders.html",
        {
            "business": business,
            "selected_date": selected_date,
            "selected_date_label": selected_date.strftime("%A %d/%m").capitalize(),
            "previous_date": (selected_date - timedelta(days=1)).isoformat(),
            "next_date": (selected_date + timedelta(days=1)).isoformat(),
            "tomorrow_date": (today + timedelta(days=1)).isoformat(),
            "is_tomorrow": selected_date == today + timedelta(days=1),
            "appointments": appointments,
            "pending_count": len(pending),
            "reminded_count": len(appointments) - len(pending),
            "all_messages": all_messages,
        },
    )


@business_required
def availability(request):
    business = request.business
    selected_date = _parse_date(request.GET.get("fecha")) or timezone.localdate()
    service_id = request.GET.get("servicio")
    selected_service = None
    if service_id:
        try:
            service_pk = int(service_id)
        except (TypeError, ValueError):
            service_pk = None
        if service_pk:
            selected_service = business.services.filter(
                pk=service_pk,
                is_active=True,
            ).first()

    schedule_blocks = get_day_blocks(business, selected_date)
    time_off = get_time_off(business, selected_date)
    slots = []
    if selected_service:
        slots = available_slots(
            business,
            selected_date,
            selected_service.duration_minutes,
        )

    return render(
        request,
        "agenda/partials/availability.html",
        {
            "business": business,
            "selected_date": selected_date,
            "selected_service": selected_service,
            "schedule_blocks": schedule_blocks,
            "time_off": time_off,
            "day_off": bool(time_off),
            "available_slots": slots,
        },
    )


@business_required
def appointment_create(request):
    business = request.business
    initial = {}
    initial_day = _parse_date(request.GET.get("fecha"))

    client_id = _parse_pk(request.GET.get("cliente"))
    if client_id:
        client = business.clients.filter(pk=client_id, is_active=True).first()
        if client:
            initial["client"] = client

    selected_service = None
    service_id = _parse_pk(request.GET.get("servicio"))
    if service_id:
        selected_service = business.services.filter(
            pk=service_id,
            is_active=True,
        ).first()
        if selected_service:
            initial["service"] = selected_service

    if initial_day:
        selected_time = _parse_time(request.GET.get("inicio"))
        if selected_time:
            initial["start_at"] = timezone.make_aware(
                datetime.combine(initial_day, selected_time),
                timezone.get_current_timezone(),
            )
        elif selected_service:
            slots = available_slots(
                business,
                initial_day,
                selected_service.duration_minutes,
            )
            if slots:
                initial["start_at"] = timezone.make_aware(
                    datetime.combine(initial_day, slots[0]),
                    timezone.get_current_timezone(),
                )

    if request.method == "POST":
        form = AppointmentForm(request.POST, business=business)
        if form.is_valid():
            try:
                with transaction.atomic():
                    appointment = form.save()
            except IntegrityError:
                form.add_error(
                    "start_at",
                    "Ese horario acaba de ocuparse. Probá con otro.",
                )
            else:
                messages.success(request, "Turno agendado.")
                return redirect("agenda:appointment_detail", pk=appointment.pk)
    else:
        form = AppointmentForm(business=business, initial=initial)

    return render(
        request,
        "agenda/appointment_form.html",
        {
            "business": business,
            "form": form,
            "appointment": None,
            "is_edit": False,
            "back_url": _day_url(initial_day) if initial_day else reverse("agenda:week"),
            "active_clients_count": business.clients.filter(is_active=True).count(),
            "active_services_count": business.services.filter(is_active=True).count(),
        },
    )


@business_required
def appointment_edit(request, pk):
    business = request.business
    appointment = get_object_or_404(
        business.appointments.select_related("client", "service"),
        pk=pk,
    )

    if request.method == "POST":
        form = AppointmentForm(request.POST, instance=appointment, business=business)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error(
                    "start_at",
                    "Ese horario acaba de ocuparse. Probá con otro.",
                )
            else:
                messages.success(request, "Turno actualizado.")
                return redirect("agenda:appointment_detail", pk=appointment.pk)
    else:
        form = AppointmentForm(instance=appointment, business=business)

    return render(
        request,
        "agenda/appointment_form.html",
        {
            "business": business,
            "form": form,
            "appointment": appointment,
            "is_edit": True,
            "back_url": reverse("agenda:appointment_detail", args=[appointment.pk]),
            "active_clients_count": business.clients.filter(is_active=True).count(),
            "active_services_count": business.services.filter(is_active=True).count(),
        },
    )


@business_required
def appointment_detail(request, pk):
    business = request.business
    appointment = get_object_or_404(
        business.appointments.select_related("client", "service"),
        pk=pk,
    )
    local_day = timezone.localtime(appointment.start_at).date()
    return render(
        request,
        "agenda/appointment_detail.html",
        {
            "business": business,
            "appointment": appointment,
            "back_url": _day_url(local_day),
            "reminder_text": appointment.reminder_text,
            "payment_form": PaymentForm(appointment=appointment),
        },
    )


def _redirect_after_appointment(request, appointment, next_url=None):
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("agenda:appointment_detail", pk=appointment.pk)


def _change_status(request, pk, new_status):
    next_url = request.POST.get("next")
    try:
        with transaction.atomic():
            appointment = get_object_or_404(
                Appointment.objects.select_for_update(),
                pk=pk,
                business=request.business,
            )
            allowed = {
                Appointment.STATUS_COMPLETED: {Appointment.STATUS_SCHEDULED},
                Appointment.STATUS_CANCELLED: {Appointment.STATUS_SCHEDULED},
                Appointment.STATUS_NO_SHOW: {Appointment.STATUS_SCHEDULED},
                Appointment.STATUS_SCHEDULED: {
                    Appointment.STATUS_CANCELLED,
                    Appointment.STATUS_NO_SHOW,
                },
            }
            if appointment.status not in allowed.get(new_status, set()):
                messages.error(
                    request,
                    "Ese cambio de estado no está disponible para este turno.",
                )
                return _redirect_after_appointment(request, appointment, next_url)

            if new_status == Appointment.STATUS_SCHEDULED:
                try:
                    validate_appointment_slot(
                        request.business,
                        appointment.start_at,
                        appointment.duration_minutes,
                        exclude_pk=appointment.pk,
                    )
                except ValidationError as error:
                    messages.error(request, error.messages[0])
                    return _redirect_after_appointment(request, appointment, next_url)

            appointment.status = new_status
            appointment.save(update_fields=("status", "updated_at"))
    except IntegrityError:
        messages.error(
            request,
            "Ese horario ya no está disponible. Probá de nuevo o elegí otro turno.",
        )
        return redirect("agenda:appointment_detail", pk=pk)

    if new_status == Appointment.STATUS_COMPLETED and appointment.price is None:
        messages.warning(
            request,
            "El turno quedó completado, pero no tiene precio. "
            "Completalo para que cuente en tus ingresos.",
        )
    else:
        messages.success(request, "Estado del turno actualizado.")
    return _redirect_after_appointment(request, appointment, next_url)


@business_required
@require_POST
def appointment_complete(request, pk):
    return _change_status(request, pk, Appointment.STATUS_COMPLETED)


@business_required
@require_POST
def appointment_cancel(request, pk):
    return _change_status(request, pk, Appointment.STATUS_CANCELLED)


@business_required
@require_POST
def appointment_no_show(request, pk):
    return _change_status(request, pk, Appointment.STATUS_NO_SHOW)


@business_required
@require_POST
def appointment_reopen(request, pk):
    return _change_status(request, pk, Appointment.STATUS_SCHEDULED)


@business_required
def appointment_repeat(request, pk):
    business = request.business
    appointment = get_object_or_404(
        business.appointments.select_related("client", "service"),
        pk=pk,
    )
    params = {"cliente": appointment.client_id}
    service = appointment.service
    if (
        service.is_active
        and business.specialties.filter(pk=service.specialty_id).exists()
    ):
        params["servicio"] = service.pk
    else:
        messages.info(
            request,
            "El servicio de ese turno ya no está activo. Elegí otro servicio para repetirlo.",
        )

    local_day = timezone.localtime(appointment.start_at).date()
    target_day = max(local_day, timezone.localdate())
    params["fecha"] = target_day.isoformat()
    return redirect(f"{reverse('agenda:appointment_create')}?{urlencode(params)}")


@business_required
@require_POST
def appointment_reminded(request, pk):
    appointment = get_object_or_404(
        Appointment,
        pk=pk,
        business=request.business,
    )
    if appointment.reminded_at:
        appointment.reminded_at = None
        messages.success(request, "Recordatorio desmarcado.")
    else:
        appointment.reminded_at = timezone.now()
        messages.success(request, "Recordatorio marcado como enviado.")
    appointment.save(update_fields=("reminded_at", "updated_at"))
    return _redirect_after_appointment(
        request,
        appointment,
        request.POST.get("next"),
    )


@business_required
@require_POST
def appointment_payment(request, pk):
    appointment = get_object_or_404(
        Appointment,
        pk=pk,
        business=request.business,
    )
    form = PaymentForm(request.POST, appointment=appointment)
    if form.is_valid():
        appointment.amount_paid = form.cleaned_data["amount_paid"]
        appointment.payment_method = form.cleaned_data["payment_method"] or ""
        appointment.save(
            update_fields=("amount_paid", "payment_method", "updated_at")
        )
        if appointment.amount_paid is None:
            messages.success(request, "Cobro sin registrar.")
        else:
            messages.success(request, "Cobro registrado.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return _redirect_after_appointment(
        request,
        appointment,
        request.POST.get("next"),
    )


def _schedule_context(business, formset=None, time_off_form=None):
    if formset is None:
        formset = ScheduleBlockFormSet(
            queryset=business.schedule_blocks.all(),
            business=business,
            prefix="blocks",
        )
    if time_off_form is None:
        time_off_form = TimeOffForm()

    blocks = list(business.schedule_blocks.all())
    grouped_blocks = []
    for weekday, label in WEEKDAY_CHOICES:
        day_blocks = [block for block in blocks if block.weekday == weekday]
        if day_blocks:
            grouped_blocks.append(
                {
                    "weekday": weekday,
                    "label": label,
                    "blocks": day_blocks,
                }
            )

    time_off = business.time_off.order_by("-start_date", "-id")

    return {
        "business": business,
        "formset": formset,
        "time_off_form": time_off_form,
        "grouped_blocks": grouped_blocks,
        "has_blocks": bool(blocks),
        "time_off": time_off,
    }


@business_required
def schedule(request):
    business = request.business

    if request.method == "POST":
        formset = ScheduleBlockFormSet(
            request.POST,
            queryset=business.schedule_blocks.all(),
            business=business,
            prefix="blocks",
        )
        if formset.is_valid():
            with transaction.atomic():
                instances = formset.save(commit=False)
                for block in instances:
                    block.business = business
                    block.save()
                for block in formset.deleted_objects:
                    block.delete()
            messages.success(request, "Horarios actualizados.")
            return redirect("agenda:schedule")
        context = _schedule_context(business, formset=formset)
    else:
        context = _schedule_context(business)

    return render(request, "agenda/schedule.html", context)


@business_required
@require_POST
def schedule_suggested(request):
    business = request.business
    if business.schedule_blocks.exists():
        messages.info(request, "Ya tenés horarios cargados.")
        return redirect("agenda:schedule")

    with transaction.atomic():
        for weekday in range(5):
            ScheduleBlock.objects.create(
                business=business,
                weekday=weekday,
                start_time=time(9, 0),
                end_time=time(13, 0),
            )
            ScheduleBlock.objects.create(
                business=business,
                weekday=weekday,
                start_time=time(15, 0),
                end_time=time(19, 0),
            )
        ScheduleBlock.objects.create(
            business=business,
            weekday=5,
            start_time=time(9, 0),
            end_time=time(13, 0),
        )

    messages.success(
        request,
        "Cargamos un horario sugerido. Ajustalo a tu realidad cuando quieras.",
    )
    return redirect("agenda:schedule")


@business_required
@require_POST
def time_off_create(request):
    business = request.business
    form = TimeOffForm(request.POST)
    if form.is_valid():
        time_off = form.save(commit=False)
        time_off.business = business
        time_off.save()
        messages.success(request, "Día libre agregado.")
        return redirect("agenda:schedule")

    context = _schedule_context(business, time_off_form=form)
    return render(request, "agenda/schedule.html", context)


@business_required
@require_POST
def time_off_delete(request, pk):
    business = request.business
    time_off = get_object_or_404(TimeOff, pk=pk, business=business)
    time_off.delete()
    messages.success(request, "Día libre eliminado.")
    return redirect("agenda:schedule")


@business_required
def income(request):
    business = request.business
    month_start = _parse_month(request.GET.get("mes"))
    month_start, next_month = _month_bounds(month_start)
    month_start_at, _ = day_bounds(month_start)
    next_month_at, _ = day_bounds(next_month)

    completed = business.appointments.filter(
        status=Appointment.STATUS_COMPLETED,
        start_at__gte=month_start_at,
        start_at__lt=next_month_at,
    ).select_related("client", "service")
    completed_count = completed.count()
    income_total = completed.aggregate(total=Sum("price"))["total"] or Decimal("0.00")
    average_ticket = completed.aggregate(average=Avg("price"))["average"] or Decimal("0.00")
    missing_price_count = completed.filter(price__isnull=True).count()
    collected_total = completed.aggregate(total=Sum("amount_paid"))["total"] or Decimal(
        "0.00"
    )
    pending_collection_total = Decimal("0.00")
    for appointment in completed:
        if appointment.price is not None:
            paid = appointment.amount_paid or Decimal("0.00")
            if paid < appointment.price:
                pending_collection_total += appointment.price - paid
    cancelled_count = business.appointments.filter(
        status=Appointment.STATUS_CANCELLED,
        start_at__gte=month_start_at,
        start_at__lt=next_month_at,
    ).count()
    no_show_count = business.appointments.filter(
        status=Appointment.STATUS_NO_SHOW,
        start_at__gte=month_start_at,
        start_at__lt=next_month_at,
    ).count()

    available_minutes = 0
    current_day = month_start
    while current_day < next_month:
        if not get_time_off(business, current_day):
            for block in get_day_blocks(business, current_day):
                block_start = datetime.combine(current_day, block.start_time)
                block_end = datetime.combine(current_day, block.end_time)
                available_minutes += int((block_end - block_start).total_seconds() // 60)
        current_day += timedelta(days=1)

    booked_minutes = sum(
        appointment.duration_minutes
        for appointment in business.appointments.filter(
            start_at__gte=month_start_at,
            start_at__lt=next_month_at,
        ).exclude(status=Appointment.STATUS_CANCELLED)
    )
    occupancy_percent = (
        round((booked_minutes / available_minutes) * 100, 1)
        if available_minutes
        else None
    )
    no_show_rate = (
        round((no_show_count / (completed_count + no_show_count)) * 100, 1)
        if completed_count + no_show_count
        else 0.0
    )

    by_service = (
        completed.values("service_name")
        .annotate(total=Sum("price"), count=Count("id"))
        .order_by("-total", "service_name")
    )
    by_specialty = (
        completed.values("service__specialty__name")
        .annotate(total=Sum("price"), count=Count("id"))
        .order_by("-total", "service__specialty__name")
    )
    for row in by_specialty:
        row["specialty_name"] = row.pop("service__specialty__name")

    prev_month = (month_start - timedelta(days=1)).replace(day=1)
    next_month_start = next_month

    return render(
        request,
        "agenda/income.html",
        {
            "business": business,
            "month_start": month_start,
            "next_month": next_month_start,
            "prev_month_param": prev_month.strftime("%Y-%m"),
            "next_month_param": next_month_start.strftime("%Y-%m"),
            "completed_count": completed_count,
            "income_total": income_total,
            "average_ticket": average_ticket,
            "missing_price_count": missing_price_count,
            "collected_total": collected_total,
            "pending_collection_total": pending_collection_total,
            "cancelled_count": cancelled_count,
            "no_show_count": no_show_count,
            "occupancy_percent": occupancy_percent,
            "booked_minutes": booked_minutes,
            "available_minutes": available_minutes,
            "no_show_rate": no_show_rate,
            "by_service": by_service,
            "by_specialty": by_specialty,
            "completed_list": completed.order_by("-start_at"),
        },
    )
