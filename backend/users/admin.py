from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("username", "email", "approval_status", "is_staff", "is_active", "date_joined")
    list_filter = ("approval_status", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)
    actions = ("approve_users", "reject_users")
    fieldsets = UserAdmin.fieldsets + (
        ("Estado de aprobacion", {"fields": ("approval_status",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Estado de aprobacion", {"fields": ("approval_status",)}),
    )

    @admin.action(description="Aprobar usuarios seleccionados")
    def approve_users(self, request, queryset):
        for user in queryset:
            user.approval_status = "approved"
            user.is_active = True
            user.save(update_fields=["approval_status", "is_active"])

    @admin.action(description="Rechazar usuarios seleccionados")
    def reject_users(self, request, queryset):
        for user in queryset:
            user.approval_status = "rejected"
            user.is_active = False
            user.save(update_fields=["approval_status", "is_active"])
