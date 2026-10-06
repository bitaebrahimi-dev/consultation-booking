from datetime import date, datetime, time

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

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
            datetime(2026, 10, 12, 10, 0),
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
            datetime(2026, 10, 12, 10, 0),
            slots,
        )

    def test_day_without_schedule_returns_no_slots(self):
        slots = generate_slots_for_date(
            date(2026, 10, 13)
        )

        self.assertEqual(slots, [])


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