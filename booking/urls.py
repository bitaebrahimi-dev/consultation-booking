from django.urls import path

from .views import availability, create_reservation

urlpatterns = [
    path(
        "reserve/",
        create_reservation,
        name="create_reservation",
    ),
    path(
        "availability/",
        availability,
        name="availability",
    ),
]