from django import forms
from .services import generate_slots_for_date
from .models import Reservation


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = [
            "name",
            "mobile",
            "topic",
            "scheduled_at",
        ]
        widgets = {
            "scheduled_at": forms.HiddenInput(),
        }

    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data["scheduled_at"]

        available_slots = generate_slots_for_date(
            scheduled_at.date()
        )

        if scheduled_at not in available_slots:
            raise forms.ValidationError(
                "زمان انتخاب‌شده قابل رزرو نیست."
            )

        return scheduled_at


    def clean_mobile(self):
        mobile = self.cleaned_data["mobile"]

        persian_digits = "۰۱۲۳۴۵۶۷۸۹"
        english_digits = "0123456789"

        translation_table = str.maketrans(
            persian_digits,
            english_digits,
        )

        mobile = mobile.translate(translation_table)

        if not mobile.isdigit():
            raise forms.ValidationError(
                "شماره موبایل باید فقط شامل عدد باشد."
            )

        if len(mobile) != 11 or not mobile.startswith("09"):
            raise forms.ValidationError(
                "شماره موبایل معتبر نیست."
            )

        return mobile