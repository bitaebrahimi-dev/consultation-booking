from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
import uuid

def generate_tracking_code():
    return uuid.uuid4().hex[:8].upper()


class WeeklySchedule(models.Model):
    WEEKDAYS = [
        (0, "شنبه"),
        (1, "یکشنبه"),
        (2, "دوشنبه"),
        (3, "سه‌شنبه"),
        (4, "چهارشنبه"),
        (5, "پنجشنبه"),
        (6, "جمعه"),
    ]

    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    session_duration = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError(
                {"end_time": "ساعت پایان باید بعد از ساعت شروع باشد."}
            )

    def __str__(self):
        return f"{self.get_weekday_display()} - {self.start_time} تا {self.end_time}"


class Holiday(models.Model):
    date = models.DateField(unique=True)
    reason = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.date} - {self.reason or 'تعطیل'}"


class Reservation(models.Model):
    STATUS_CHOICES = [
        ("confirmed", "تأییدشده"),
        ("cancelled", "لغوشده"),
    ]

    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=11)
    topic = models.CharField(max_length=200)
    scheduled_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="confirmed",
    )
    tracking_code = models.CharField(
        max_length=20,
        unique=True,
        default=generate_tracking_code,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scheduled_at"],
                condition=~models.Q(status="cancelled"),
                name="unique_active_reservation_slot",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.scheduled_at}"