from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from rest_framework.authtoken.models import Token, TokenProxy

from .forms import AdminCustomUserCreationForm
from .models import CustomUser
from .user_importer import USER_IMPORT_HEADERS, USER_SAMPLE_ROWS, UserXlsxImporter


for model in (Token, TokenProxy, Group):
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    add_form = AdminCustomUserCreationForm
    list_display = ("username", "email", "approval_status", "is_staff", "is_active", "date_joined")
    list_filter = ("approval_status", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    actions = ("approve_users", "reject_users", "add_staff", "remove_staff")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "email", "name", "phone", "address", "city", "zip_code", "avatar")}),
        ("Estado de aprobacion", {"fields": ("approval_status",)}),
        ("Presupuesto de envio", {"fields": ("shipping_quote_amount", "shipping_quote_note", "shipping_quote_updated_at")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Fechas importantes", {"fields": ("last_login", "date_joined", "welcome_email_sent_at", "last_password_changed_at")}),
    )
    readonly_fields = ("shipping_quote_updated_at", "welcome_email_sent_at", "last_password_changed_at", "last_login", "date_joined")
    filter_horizontal = ()
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("first_name", "last_name", "email", "password1", "password2", "approval_status"),
            },
        ),
    )
    change_list_template = "admin/users/customuser/change_list.html"
    template_xlsx_path = None

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "importar-xlsx/",
                self.admin_site.admin_view(self.import_xlsx_view),
                name="users_customuser_import_xlsx",
            ),
        ]
        return custom + urls

    def save_model(self, request, obj, form, change):
        if obj.first_name or obj.last_name:
            obj.name = " ".join(part for part in [str(obj.first_name or "").strip(), str(obj.last_name or "").strip()] if part).strip()
        if obj.email:
            obj.username = str(obj.email).strip().lower()
        super().save_model(request, obj, form, change)

    def import_xlsx_view(self, request):
        importer = UserXlsxImporter(template_xlsx_path=self.template_xlsx_path)

        if request.method == "GET" and request.GET.get("sample"):
            return importer.export_workbook(USER_SAMPLE_ROWS, "clientes_ejemplo.xlsx")

        if request.method == "GET" and request.GET.get("template"):
            return importer.export_template_response()

        created = 0
        updated = 0
        errors = []

        if request.method == "POST":
            upload = request.FILES.get("file")
            if not upload:
                messages.error(request, "Selecciona un archivo XLSX.")
                return redirect(reverse("admin:users_customuser_import_xlsx"))
            try:
                created, updated, errors = importer.import_upload(upload)
                if created or updated:
                    messages.success(
                        request,
                        f"Importacion completada. Nuevos: {created} | Actualizados: {updated}",
                    )
                for err in errors:
                    messages.error(request, err)
            except Exception as exc:  # pragma: no cover
                messages.error(request, f"No se pudo procesar el XLSX: {exc}")
                return redirect(reverse("admin:users_customuser_import_xlsx"))

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar clientes via XLSX",
            "headers": USER_IMPORT_HEADERS,
            "example_url": f"{reverse('admin:users_customuser_import_xlsx')}?sample=1",
            "template_url": f"{reverse('admin:users_customuser_import_xlsx')}?template=1",
            "created": created,
            "updated": updated,
            "errors": errors,
        }
        return TemplateResponse(request, "admin/users/customuser/import_xlsx.html", context)

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
