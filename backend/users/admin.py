from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token, TokenProxy

from .models import CustomUser


for model in (Token, TokenProxy, Group):
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("username", "email", "approval_status", "is_staff", "is_active", "date_joined")
    list_filter = ("approval_status", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)
    actions = ("approve_users", "reject_users", "add_staff", "remove_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Estado de aprobacion", {"fields": ("approval_status",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Estado de aprobacion", {"fields": ("approval_status",)}),
    )

    @admin.action(description="Aprobar usuarios seleccionados")
    def approve_users(self, request, queryset):
        for user in queryset:
            user.set_approval_status("approved")
            user.save(update_fields=["approval_status", "is_active", "role"])

    @admin.action(description="Rechazar usuarios seleccionados")
    def reject_users(self, request, queryset):
        for user in queryset:
            user.set_approval_status("rejected")
            user.save(update_fields=["approval_status", "is_active", "role"])

    @admin.action(description="Añadir staff")
    def add_staff(self, request, queryset):
        for user in queryset:
            user.is_staff = True
            user.save(update_fields=["is_staff", "approval_status", "is_active", "role"])

    @admin.action(description="Quitar staff")
    def remove_staff(self, request, queryset):
        for user in queryset:
            user.is_staff = False
            user.role = "user"
            user.approval_status = "approved"
            user.is_active = True
            user.save(update_fields=["is_staff", "approval_status", "is_active", "role"])
