from django.contrib import admin

from .models import Holiday, Reservation, WeeklySchedule


admin.site.register(WeeklySchedule)
admin.site.register(Holiday)
admin.site.register(Reservation)