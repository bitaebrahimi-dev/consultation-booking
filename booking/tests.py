from datetime import date, datetime, time, timedelta
from .forms import ReservationForm
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from .models import Holiday, Reservation, WeeklySchedule
from .services import generate_raw_slots, generate_slots_for_date


def get_future_monday():
    today = timezone.localdate()

    days_ahead = (0 - today.weekday()) % 7

    if days_ahead == 0:
        days_ahead = 7

    return today + timedelta(days=days_ahead)


def get_future_monday_datetime(hour, minute=0):
    future_monday = get_future_monday()

    return timezone.make_aware(
        datetime.combine(
            future_monday,
            time(hour, minute),
        )
    )


def get_future_monday_string(hour, minute=0):
    future_datetime = get_future_monday_datetime(
        hour,
        minute,
    )

    return future_datetime.strftime("%Y-%m-%d %H:%M")


class SlotGenerationTests(TestCase):
    def test_generate_raw_slots(self):
        future_monday = get_future_monday()

        slots = generate_raw_slots(
            future_monday,
            time(9, 0),
            time(11, 0),
            30,
        )

        self.assertEqual(len(slots), 4)

    def test_incomplete_slot_is_not_generated(self):
        future_monday = get_future_monday()

        slots = generate_raw_slots(
            future_monday,
            time(10, 0),
            time(11, 20),
            30,
        )

        self.assertEqual(len(slots), 2)


class SlotFilterTests(TestCase):
    def test_holiday_returns_no_slots(self):
        future_monday = get_future_monday()

        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        Holiday.objects.create(
            date=future_monday,
            reason="تعطیلی آزمایشی",
        )

        slots = generate_slots_for_date(future_monday)

        self.assertEqual(slots, [])

    def test_past_slots_are_removed(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        slots = generate_slots_for_date(
            date(2020, 1, 6)
        )

        self.assertEqual(slots, [])

    def test_booked_slot_is_removed(self):
        future_monday = get_future_monday()

        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        booked_time = get_future_monday_datetime(
            10,
            0,
        )

        Reservation.objects.create(
            name="Test User",
            mobile="09121234567",
            topic="Test consultation",
            scheduled_at=booked_time,
            status="confirmed",
        )

        slots = generate_slots_for_date(
            future_monday
        )

        self.assertNotIn(
            booked_time,
            slots,
        )

    def test_cancelled_reservation_does_not_block_slot(self):
        future_monday = get_future_monday()

        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        cancelled_time = get_future_monday_datetime(
            10,
            0,
        )

        Reservation.objects.create(
            name="Test User",
            mobile="09121234567",
            topic="Test consultation",
            scheduled_at=cancelled_time,
            status="cancelled",
        )

        slots = generate_slots_for_date(
            future_monday
        )

        self.assertIn(
            cancelled_time,
            slots,
        )

    def test_day_without_schedule_returns_no_slots(self):
        future_tuesday = (
            get_future_monday()
            + timedelta(days=1)
        )

        slots = generate_slots_for_date(
            future_tuesday
        )

        self.assertEqual(slots, [])


class ReservationFormMobileTests(TestCase):
    def test_valid_english_mobile_is_accepted(self):
        form = ReservationForm(data={
            "name": "Mobin",
            "mobile": "09121234567",
            "topic": "Test consultation",
            "scheduled_at": get_future_monday_string(10),
        })

        form.is_valid()

        self.assertNotIn(
            "mobile",
            form.errors,
        )

    def test_persian_mobile_is_normalized(self):
        form = ReservationForm(data={
            "name": "Mobin",
            "mobile": "۰۹۱۲۱۲۳۴۵۶۷",
            "topic": "Test consultation",
            "scheduled_at": get_future_monday_string(10),
        })

        form.is_valid()

        self.assertEqual(
            form.cleaned_data["mobile"],
            "09121234567",
        )

    def test_invalid_mobile_is_rejected(self):
        form = ReservationForm(data={
            "name": "Mobin",
            "mobile": "08121234567",
            "topic": "Test consultation",
            "scheduled_at": get_future_monday_string(10),
        })

        form.is_valid()

        self.assertIn(
            "mobile",
            form.errors,
        )


class ReservationConstraintTests(TestCase):
    def test_duplicate_active_reservation_is_rejected(self):
        slot_time = get_future_monday_datetime(
            10,
            0,
        )

        Reservation.objects.create(
            name="User One",
            mobile="09121234567",
            topic="First consultation",
            scheduled_at=slot_time,
            status="confirmed",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Reservation.objects.create(
                    name="User Two",
                    mobile="09129876543",
                    topic="Second consultation",
                    scheduled_at=slot_time,
                    status="confirmed",
                )

    def test_cancelled_reservation_allows_new_active_reservation(self):
        slot_time = get_future_monday_datetime(
            10,
            0,
        )

        Reservation.objects.create(
            name="User One",
            mobile="09121234567",
            topic="Cancelled consultation",
            scheduled_at=slot_time,
            status="cancelled",
        )

        new_reservation = Reservation.objects.create(
            name="User Two",
            mobile="09129876543",
            topic="New consultation",
            scheduled_at=slot_time,
            status="confirmed",
        )

        self.assertEqual(
            new_reservation.status,
            "confirmed",
        )

    def test_duplicate_active_reservation_raises_integrity_error(self):
        slot_time = get_future_monday_datetime(
            11,
            0,
        )

        Reservation.objects.create(
            name="User One",
            mobile="09121234567",
            topic="First consultation",
            scheduled_at=slot_time,
            status="confirmed",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Reservation.objects.create(
                    name="User Two",
                    mobile="09129876543",
                    topic="Second consultation",
                    scheduled_at=slot_time,
                    status="confirmed",
                )


class ReservationFormTimeTests(TestCase):
    def test_valid_available_time_is_accepted(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        form = ReservationForm(data={
            "name": "Mobin",
            "mobile": "09121234567",
            "topic": "Test consultation",
            "scheduled_at": get_future_monday_string(10),
        })

        self.assertTrue(form.is_valid())

    def test_time_outside_generated_slots_is_rejected(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        form = ReservationForm(data={
            "name": "Mobin",
            "mobile": "09121234567",
            "topic": "Test consultation",
            "scheduled_at": get_future_monday_string(10, 15),
        })

        self.assertFalse(form.is_valid())

        self.assertIn(
            "scheduled_at",
            form.errors,
        )

    def test_past_time_is_rejected(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        form = ReservationForm(data={
            "name": "Mobin",
            "mobile": "09121234567",
            "topic": "Test consultation",
            "scheduled_at": "2020-01-06 10:00",
        })

        self.assertFalse(form.is_valid())

        self.assertIn(
            "scheduled_at",
            form.errors,
        )

    def test_holiday_time_is_rejected(self):
        future_monday = get_future_monday()

        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        Holiday.objects.create(
            date=future_monday,
            reason="تعطیلی آزمایشی",
        )

        form = ReservationForm(data={
            "name": "Mobin",
            "mobile": "09121234567",
            "topic": "Test consultation",
            "scheduled_at": get_future_monday_string(10),
        })

        self.assertFalse(form.is_valid())

        self.assertIn(
            "scheduled_at",
            form.errors,
        )

    def test_booked_time_is_rejected(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        booked_time = get_future_monday_datetime(
            10,
            0,
        )

        Reservation.objects.create(
            name="User One",
            mobile="09121234567",
            topic="First consultation",
            scheduled_at=booked_time,
            status="confirmed",
        )

        form = ReservationForm(data={
            "name": "User Two",
            "mobile": "09129876543",
            "topic": "Second consultation",
            "scheduled_at": get_future_monday_string(10),
        })

        self.assertFalse(form.is_valid())

        self.assertIn(
            "scheduled_at",
            form.errors,
        )

    def test_cancelled_reservation_does_not_block_time(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        cancelled_time = get_future_monday_datetime(
            10,
            0,
        )

        Reservation.objects.create(
            name="User One",
            mobile="09121234567",
            topic="Cancelled consultation",
            scheduled_at=cancelled_time,
            status="cancelled",
        )

        form = ReservationForm(data={
            "name": "User Two",
            "mobile": "09129876543",
            "topic": "New consultation",
            "scheduled_at": get_future_monday_string(10),
        })

        self.assertTrue(form.is_valid())

class ReservationViewTests(TestCase):
    def test_valid_reservation_is_created(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        response = self.client.post(
            reverse("create_reservation"),
            data={
                "name": "Mobin",
                "mobile": "09121234567",
                "topic": "Test consultation",
                "scheduled_at": get_future_monday_string(10),
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            Reservation.objects.filter(
                mobile="09121234567",
                scheduled_at=get_future_monday_datetime(10),
            ).exists()
        )

    def test_success_page_is_returned_after_reservation(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        response = self.client.post(
            reverse("create_reservation"),
            data={
                "name": "Mobin",
                "mobile": "09121234567",
                "topic": "Test confirmation page",
                "scheduled_at": get_future_monday_string(10),
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "booking/reservation_success.html",
        )

    def test_tracking_code_is_shown_on_success_page(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        response = self.client.post(
            reverse("create_reservation"),
            data={
                "name": "Mobin",
                "mobile": "09121234567",
                "topic": "Tracking code test",
                "scheduled_at": get_future_monday_string(10),
            },
        )

        reservation = Reservation.objects.get(
            mobile="09121234567"
        )

        self.assertContains(
            response,
            reservation.tracking_code,
        )

    def test_duplicate_reservation_is_rejected_in_view(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        slot_time = get_future_monday_datetime(
            10,
            0,
        )

        Reservation.objects.create(
            name="User One",
            mobile="09121234567",
            topic="First consultation",
            scheduled_at=slot_time,
            status="confirmed",
        )

        response = self.client.post(
            reverse("create_reservation"),
            data={
                "name": "User Two",
                "mobile": "09129876543",
                "topic": "Second consultation",
                "scheduled_at": get_future_monday_string(10),
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            Reservation.objects.filter(
                scheduled_at=slot_time,
                status="confirmed",
            ).count(),
            1,
        )

        self.assertContains(
            response,
            "زمان انتخاب‌شده قابل رزرو نیست.",
        )

    def test_persian_mobile_is_normalized_in_view(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        response = self.client.post(
            reverse("create_reservation"),
            data={
                "name": "Mobin",
                "mobile": "۰۹۱۲۱۲۳۴۵۶۷",
                "topic": "Persian mobile test",
                "scheduled_at": get_future_monday_string(10),
            },
        )

        self.assertEqual(response.status_code, 200)

        reservation = Reservation.objects.get(
            name="Mobin"
        )

        self.assertEqual(
            reservation.mobile,
            "09121234567",
        )

    def test_reserve_without_slot_redirects_to_availability(self):
        response = self.client.get(
            reverse("create_reservation")
        )

        self.assertRedirects(
            response,
            reverse("availability"),
        )

    def test_invalid_slot_redirects_to_availability(self):
        response = self.client.get(
            reverse("create_reservation"),
            {
                "slot": "abc",
            },
        )

        self.assertRedirects(
            response,
            reverse("availability"),
        )
