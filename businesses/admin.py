from django.contrib import admin

from .models import Business, Service


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0
    fields = ("specialty", "name", "duration_minutes", "price", "is_active")
    autocomplete_fields = ("specialty",)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__email")
    list_filter = ("specialties",)
    filter_horizontal = ("specialties",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (ServiceInline,)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "business",
        "specialty",
        "duration_minutes",
        "price",
        "is_active",
    )
    list_filter = ("specialty", "is_active")
    search_fields = ("name", "business__name", "business__owner__email")
    autocomplete_fields = ("business", "specialty")
    readonly_fields = ("created_at", "updated_at")
