from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "phone", "email", "is_active")
    list_filter = ("is_active", "business")
    search_fields = ("name", "phone", "email")
    list_select_related = ("business",)
    readonly_fields = ("created_at", "updated_at")
