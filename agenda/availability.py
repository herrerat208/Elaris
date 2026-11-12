from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Appointment


def _local(value):
    if timezone.is_naive(value):
        return timezone.make_aware(value)
    return timezone.localtime(value)


def day_bounds(day):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    return start, start + timedelta(days=1)


def get_time_off(business, day):
    return business.time_off.filter(start_date__lte=day, end_date__gte=day).first()


def get_day_blocks(business, day):
    return list(business.schedule_blocks.filter(weekday=day.weekday()).order_by("start_time"))


def get_day_appointments(business, day, include_cancelled=True):
    start, end = day_bounds(day)
    queryset = business.appointments.filter(
        start_at__gte=start,
        start_at__lt=end,
    ).select_related("client", "service")
    if not include_cancelled:
        queryset = queryset.exclude(status=Appointment.STATUS_CANCELLED)
    return queryset.order_by("start_at")


def validate_appointment_slot(business, start_at, duration_minutes, exclude_pk=None):
    if not start_at:
        return

    start_at = _local(start_at)
    end_at = start_at + timedelta(minutes=duration_minutes)
    local_start = timezone.localtime(start_at)
    local_end = timezone.localtime(end_at)

    if local_end.date() != local_start.date():
        raise ValidationError("El turno no puede terminar al día siguiente.")

    day = local_start.date()
    if get_time_off(business, day):
        raise ValidationError("Ese día está marcado como libre.")

    blocks = get_day_blocks(business, day)
    if not blocks:
        raise ValidationError("Ese día no tenés horario de atención.")

    start_time = local_start.time()
    end_time = local_end.time()
    if not any(block.start_time <= start_time and end_time <= block.end_time for block in blocks):
        raise ValidationError(
            "El turno tiene que entrar completo dentro de un bloque de tu horario."
        )

    overlapping = business.appointments.filter(
        start_at__lt=end_at,
        end_at__gt=start_at,
    ).exclude(status=Appointment.STATUS_CANCELLED)
    if exclude_pk is not None:
        overlapping = overlapping.exclude(pk=exclude_pk)
    if overlapping.exists():
        raise ValidationError("Ya tenés un turno en ese horario.")


def available_slots(business, day, duration_minutes, step_minutes=15, now=None):
    if duration_minutes <= 0 or get_time_off(business, day):
        return []

    blocks = get_day_blocks(business, day)
    if not blocks:
        return []

    if now is None:
        now = timezone.now()

    start, end = day_bounds(day)
    existing = list(
        business.appointments.filter(
            start_at__gte=start,
            start_at__lt=end,
        )
        .exclude(status=Appointment.STATUS_CANCELLED)
        .values_list("start_at", "end_at")
    )

    tz = timezone.get_current_timezone()
    slots = []
    for block in blocks:
        current = timezone.make_aware(datetime.combine(day, block.start_time), tz)
        block_end = timezone.make_aware(datetime.combine(day, block.end_time), tz)
        while current + timedelta(minutes=duration_minutes) <= block_end:
            slot_end = current + timedelta(minutes=duration_minutes)
            has_overlap = any(
                current < existing_end and slot_end > existing_start
                for existing_start, existing_end in existing
            )
            if current >= now and not has_overlap:
                slots.append(timezone.localtime(current).time())
            current += timedelta(minutes=step_minutes)
    return slots
