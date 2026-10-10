from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from .forms import ReservationForm
from .services import (
    get_next_7_days_with_jalali,
    format_selected_slot,
    format_reservation_datetime,
)

def create_reservation(request):
    if request.method == "POST":
        form = ReservationForm(request.POST)

        selected_slot = request.POST.get("scheduled_at")
        selected_slot_display = format_selected_slot(selected_slot)

        if form.is_valid():
            try:
                with transaction.atomic():
                    reservation = form.save()

            except IntegrityError:
                form.add_error(
                    "scheduled_at",
                    "این زمان لحظاتی قبل رزرو شده است. لطفاً زمان دیگری انتخاب کنید.",
                )

            else:
                reservation_datetime_display = format_reservation_datetime(
                    reservation.scheduled_at
                )

                return render(
                    request,
                    "booking/reservation_success.html",
                    {
                        "reservation": reservation,
                        "reservation_datetime_display": reservation_datetime_display,
                    },
                )

    else:
        selected_slot = request.GET.get("slot")
        if not selected_slot:
            return redirect("availability")
        selected_slot_display = format_selected_slot(selected_slot)
        if selected_slot_display is None:
            return redirect("availability")


        form = ReservationForm(
            initial={
                "scheduled_at": selected_slot,
            }
        )

    return render(
        request,
        "booking/reservation_form.html",
        {
            "form": form,
            "selected_slot": selected_slot,
            "selected_slot_display": selected_slot_display,
        },
    )


def availability(request):
    days = get_next_7_days_with_jalali()

    return render(
        request,
        "booking/availability.html",
        {
            "days": days,
        },
    )