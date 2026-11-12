from django.contrib import admin

from .models import ServiceTemplate, Specialty


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ServiceTemplate)
class ServiceTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "specialty", "default_duration_minutes", "sort_order", "is_active")
    list_filter = ("specialty", "is_active")
    list_editable = ("default_duration_minutes", "sort_order", "is_active")
    search_fields = ("name", "specialty__name")
