from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import render

from .forms import ReservationForm


def create_reservation(request):
    if request.method == "POST":
        form = ReservationForm(request.POST)

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
                return render(
                    request,
                    "booking/reservation_success.html",
                    {
                        "reservation": reservation,
                    },
                )

    else:
        form = ReservationForm()

    return render(
        request,
        "booking/reservation_form.html",
        {
            "form": form,
        },
    )