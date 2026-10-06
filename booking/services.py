from datetime import datetime, timedelta
from .models import Holiday, WeeklySchedule
from django.utils import timezone
from .models import Holiday, Reservation, WeeklySchedule


def get_model_weekday(target_date):
    return (target_date.weekday() + 2) % 7


def get_schedules_for_date(target_date):
    weekday = get_model_weekday(target_date)

    return WeeklySchedule.objects.filter(
        weekday=weekday
    ).order_by("start_time")


def generate_raw_slots(target_date, start_time, end_time, session_duration):
    slots = []

    current = datetime.combine(target_date, start_time)
    end = datetime.combine(target_date, end_time)

    duration = timedelta(minutes=session_duration)

    while current + duration <= end:
        slots.append(current)
        current += duration

    return slots


def generate_slots_for_date(target_date):
    if Holiday.objects.filter(date=target_date).exists():
        return []

    slots = []

    schedules = get_schedules_for_date(target_date)

    for schedule in schedules:
        raw_slots = generate_raw_slots(
            target_date,
            schedule.start_time,
            schedule.end_time,
            schedule.session_duration,
        )

        slots.extend(raw_slots)

    future_slots = remove_past_slots(slots)

    return remove_booked_slots(future_slots)


def remove_past_slots(slots):
    now = timezone.now()
    future_slots = []

    for slot in slots:
        aware_slot = timezone.make_aware(slot)

        if aware_slot > now:
            future_slots.append(slot)

    return future_slots


def remove_past_slots(slots):
    now = timezone.now()
    future_slots = []

    for slot in slots:
        aware_slot = timezone.make_aware(slot)

        if aware_slot > now:
            future_slots.append(slot)

    return future_slots


def remove_booked_slots(slots):
    available_slots = []

    for slot in slots:
        is_booked = Reservation.objects.filter(
            scheduled_at=timezone.make_aware(slot),
            status="confirmed",
        ).exists()

        if not is_booked:
            available_slots.append(slot)

    return available_slots
