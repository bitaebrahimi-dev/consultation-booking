from datetime import datetime, timedelta
from django.utils import timezone
from .models import Holiday, Reservation, WeeklySchedule
import jdatetime


def get_model_weekday(target_date):
    return (target_date.weekday() + 2) % 7


def get_schedules_for_date(target_date):
    weekday = get_model_weekday(target_date)

    return WeeklySchedule.objects.filter(
        weekday=weekday
    ).order_by("start_time")


def generate_raw_slots(target_date, start_time, end_time, session_duration):
    slots = []

    current = timezone.make_aware(
        datetime.combine(target_date, start_time)
    )

    end = timezone.make_aware(
        datetime.combine(target_date, end_time)
    )

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
        if slot > now:
            future_slots.append(slot)

    return future_slots


def remove_booked_slots(slots):
    available_slots = []

    for slot in slots:
        is_booked = Reservation.objects.filter(
            scheduled_at=slot,
            status="confirmed",
        ).exists()

        if not is_booked:
            available_slots.append(slot)

    return available_slots


def get_next_7_days():
    today = timezone.localdate()

    days = []

    for day_number in range(7):
        target_date = today + timedelta(days=day_number)
        days.append(target_date)

    return days


def to_jalali_date(gregorian_date):
    jalali_date = jdatetime.date.fromgregorian(
        date=gregorian_date
    )

    return jalali_date


def get_next_7_days_with_jalali():
    days = []

    for gregorian_date in get_next_7_days():
        jalali_date = to_jalali_date(gregorian_date)
        slots = generate_slots_for_date(gregorian_date)

        days.append({
            "gregorian": gregorian_date,
            "jalali": jalali_date,
            "jalali_display": format_jalali_date(jalali_date),
            "slots": slots,

        })

    return days


def format_jalali_date(jalali_date):
    weekday_names = {
        "Saturday": "شنبه",
        "Sunday": "یکشنبه",
        "Monday": "دوشنبه",
        "Tuesday": "سه‌شنبه",
        "Wednesday": "چهارشنبه",
        "Thursday": "پنجشنبه",
        "Friday": "جمعه",
    }

    months = [
        "",
        "فروردین",
        "اردیبهشت",
        "خرداد",
        "تیر",
        "مرداد",
        "شهریور",
        "مهر",
        "آبان",
        "آذر",
        "دی",
        "بهمن",
        "اسفند",
    ]

    english_weekday = jalali_date.strftime("%A")

    weekday_name = weekday_names[english_weekday]
    month_name = months[jalali_date.month]

    return f"{weekday_name} {jalali_date.day} {month_name}"


def format_selected_slot(selected_slot):
    if not selected_slot:
        return None

    try:
        selected_datetime = datetime.strptime(
            selected_slot,
            "%Y-%m-%d %H:%M",
        )
    except ValueError:
        return None

    jalali_date = to_jalali_date(selected_datetime.date())
    jalali_display = format_jalali_date(jalali_date)

    return (
        f"{jalali_display} — "
        f"ساعت {selected_datetime.strftime('%H:%M')}"
    )


def format_reservation_datetime(reservation_datetime):
    jalali_date = to_jalali_date(
        reservation_datetime.date()
    )

    jalali_display = format_jalali_date(jalali_date)

    return (
        f"{jalali_display} — "
        f"ساعت {reservation_datetime.strftime('%H:%M')}"
    )