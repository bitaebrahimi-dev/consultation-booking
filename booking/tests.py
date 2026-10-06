from datetime import date, datetime, time
from .forms import ReservationForm
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from .models import Holiday, Reservation, WeeklySchedule
from .services import generate_raw_slots, generate_slots_for_date


class SlotGenerationTests(TestCase):
    def test_generate_raw_slots(self):
        slots = generate_raw_slots(
            date(2026, 10, 12),
            time(9, 0),
            time(11, 0),
            30,
        )

        self.assertEqual(len(slots), 4)

    def test_incomplete_slot_is_not_generated(self):
        slots = generate_raw_slots(
            date(2026, 10, 12),
            time(10, 0),
            time(11, 20),
            30,
        )

        self.assertEqual(len(slots), 2)


class SlotFilterTests(TestCase):
    def test_holiday_returns_no_slots(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        Holiday.objects.create(
            date=date(2026, 10, 12),
            reason="تعطیلی آزمایشی",
        )

        slots = generate_slots_for_date(date(2026, 10, 12))

        self.assertEqual(slots, [])

    def test_past_slots_are_removed(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        slots = generate_slots_for_date(date(2020, 1, 6))

        self.assertEqual(slots, [])

    def test_booked_slot_is_removed(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        booked_time = timezone.make_aware(
            datetime(2026, 10, 12, 10, 0)
        )

        Reservation.objects.create(
            name="Test User",
            mobile="09121234567",
            topic="Test consultation",
            scheduled_at=booked_time,
            status="confirmed",
        )

        slots = generate_slots_for_date(date(2026, 10, 12))

        self.assertNotIn(
            booked_time,
            slots,
        )

    def test_cancelled_reservation_does_not_block_slot(self):
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        cancelled_time = timezone.make_aware(
            datetime(2026, 10, 12, 10, 0)
        )

        Reservation.objects.create(
            name="Test User",
            mobile="09121234567",
            topic="Test consultation",
            scheduled_at=cancelled_time,
            status="cancelled",
        )

        slots = generate_slots_for_date(date(2026, 10, 12))

        self.assertIn(
            cancelled_time,
            slots,
        )

    def test_day_without_schedule_returns_no_slots(self):
        slots = generate_slots_for_date(
            date(2026, 10, 13)
        )

        self.assertEqual(slots, [])


class ReservationFormMobileTests(TestCase):
    def test_valid_english_mobile_is_accepted(self):
        form = ReservationForm(data={
            "name": "Mobin",
            "mobile": "09121234567",
            "topic": "Test consultation",
            "scheduled_at": "2026-10-12 10:00",
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
            "scheduled_at": "2026-10-12 10:00",
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
            "scheduled_at": "2026-10-12 10:00",
        })

        form.is_valid()

        self.assertIn(
            "mobile",
            form.errors,
        )


class ReservationConstraintTests(TestCase):
    def test_duplicate_active_reservation_is_rejected(self):
        slot_time = timezone.make_aware(
            datetime(2026, 10, 12, 10, 0)
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
        slot_time = timezone.make_aware(
            datetime(2026, 10, 12, 10, 0)
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
        slot_time = timezone.make_aware(
            datetime(2026, 10, 12, 11, 0)
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
            "scheduled_at": "2026-10-12 10:00",
        })

        self.assertTrue(form.is_valid())


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
            "scheduled_at": "2026-10-12 10:00",
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
            "scheduled_at": "2026-10-12 10:15",
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
        WeeklySchedule.objects.create(
            weekday=2,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_duration=30,
        )

        Holiday.objects.create(
            date=date(2026, 10, 12),
            reason="تعطیلی آزمایشی",
        )

        form = ReservationForm(data={
            "name": "Mobin",
            "mobile": "09121234567",
            "topic": "Test consultation",
            "scheduled_at": "2026-10-12 10:00",
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

        booked_time = timezone.make_aware(
            datetime(2026, 10, 12, 10, 0)
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
            "scheduled_at": "2026-10-12 10:00",
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

        cancelled_time = timezone.make_aware(
            datetime(2026, 10, 12, 10, 0)
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
            "scheduled_at": "2026-10-12 10:00",
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
                "scheduled_at": "2026-10-12 10:00",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            Reservation.objects.filter(
                mobile="09121234567",
                scheduled_at=timezone.make_aware(
                    datetime(2026, 10, 12, 10, 0)
                ),
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
                "scheduled_at": "2026-10-12 10:00",
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
                "scheduled_at": "2026-10-12 10:00",
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

        slot_time = timezone.make_aware(
            datetime(2026, 10, 12, 10, 0)
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
                "scheduled_at": "2026-10-12 10:00",
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
                "scheduled_at": "2026-10-12 10:00",
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