from django.contrib import admin

from .models import Appointment, ScheduleBlock, TimeOff


@admin.register(ScheduleBlock)
class ScheduleBlockAdmin(admin.ModelAdmin):
    list_display = ("business", "weekday", "start_time", "end_time")
    list_filter = ("weekday", "business")
    list_select_related = ("business",)


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = ("business", "start_date", "end_date", "reason")
    list_filter = ("business",)
    search_fields = ("reason",)
    list_select_related = ("business",)
    date_hierarchy = "start_date"


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "start_at",
        "client",
        "service_name",
        "business",
        "status",
        "price",
    )
    list_filter = ("status", "business")
    search_fields = ("client__name", "service_name", "notes")
    list_select_related = ("business", "client", "service")
    date_hierarchy = "start_at"
    readonly_fields = ("service_name", "duration_minutes", "end_at", "created_at", "updated_at")
