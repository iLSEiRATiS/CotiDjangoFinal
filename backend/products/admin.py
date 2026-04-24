from pathlib import Path
import re

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .forms import HomeMarqueeAdminForm, ProductAdminForm
from .models import Category, HomeImage, HomeMarquee, Offer, Product, ProductImage, StoreSettings
from .product_importer import EXPORT_HEADERS, PRODUCT_HEADERS, SAMPLE_ROWS, ProductXlsxImporter

admin.site.site_header = "Admin Coti"
admin.site.site_title = "Admin Coti"
admin.site.index_title = "Panel de administracion"


MISSING_IDPRODUCT_RE = re.compile(r"^Fila (?P<row>\d+): IDProduct (?P<id>\d+) no existe\.")


def summarize_import_errors(errors):
    missing_id_rows = []
    other_errors = []

    for error in errors:
        match = MISSING_IDPRODUCT_RE.match(str(error))
        if match:
            missing_id_rows.append((match.group("row"), match.group("id")))
        else:
            other_errors.append(str(error))

    summary = []
    if missing_id_rows:
        preview = ", ".join(f"fila {row} (ID {pk})" for row, pk in missing_id_rows[:12])
        extra = len(missing_id_rows) - 12
        if extra > 0:
            preview = f"{preview} y {extra} mas"
        summary.append({
            "kind": "missing_idproduct",
            "count": len(missing_id_rows),
            "message": (
                f"{len(missing_id_rows)} filas traian IDProduct que no existe en esta base. "
                "No se importaron para evitar duplicados."
            ),
            "preview": preview,
        })

    if other_errors:
        summary.append({
            "kind": "other",
            "count": len(other_errors),
            "message": f"{len(other_errors)} errores adicionales durante la importacion.",
            "preview": " | ".join(other_errors[:8]),
        })

    return summary


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "parent")
    prepopulated_fields = {"slug": ("nombre",)}
    search_fields = ("nombre", "descripcion")
    list_filter = ("parent",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("order", "image_url", "image", "activo")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("nombre", "slug", "precio", "user", "categoria", "has_video", "stock", "activo", "creado_en")
    search_fields = ("nombre", "descripcion", "slug", "categoria__nombre")
    list_filter = ("creado_en", "activo", "categoria")
    list_editable = ("precio", "stock", "activo")
    search_help_text = "Buscar producto por nombre, slug o descripcion"
    change_list_template = "admin/products/product/change_list.html"
    inlines = [ProductImageInline]

    template_xlsx_path = str(Path(__file__).resolve().parent / "resources" / "ProductosCoti_base.xlsx")
    product_headers = PRODUCT_HEADERS
    export_headers = EXPORT_HEADERS
    sample_rows = SAMPLE_ROWS

    @admin.display(description="Video")
    def has_video(self, obj):
        return bool(obj.video_url)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "categoria")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "importar-xlsx/",
                self.admin_site.admin_view(self.import_xlsx_view),
                name="products_product_import_xlsx",
            ),
        ]
        return custom + urls

    def import_xlsx_view(self, request):
        importer = ProductXlsxImporter(
            request_user=request.user,
            template_xlsx_path=self.template_xlsx_path,
        )

        if request.method == "GET" and request.GET.get("sample"):
            return importer.export_workbook(self.sample_rows, "productos_ejemplo.xlsx")

        if request.method == "GET" and request.GET.get("template"):
            return importer.export_template_response()

        if request.method == "GET" and request.GET.get("export"):
            return importer.export_products_response()

        created = 0
        updated = 0
        errors = []
        error_summary = []

        if request.method == "POST":
            upload = request.FILES.get("file")
            if not upload:
                messages.error(request, "Selecciona un archivo XLSX.")
                return redirect(reverse("admin:products_product_import_xlsx"))
            try:
                created, updated, errors = importer.import_upload(upload)
                if created or updated:
                    messages.success(
                        request,
                        f"Importacion completada. Nuevos: {created} | Actualizados: {updated}",
                    )
                error_summary = summarize_import_errors(errors)
                for item in error_summary:
                    messages.warning(request, item["message"])
                for err in errors[:8]:
                    messages.error(request, err)
                if len(errors) > 8:
                    messages.info(
                        request,
                        f"Se omitieron {len(errors) - 8} errores repetidos en las alertas. "
                        "Podes ver el detalle completo en el resumen de esta pantalla.",
                    )
            except Exception as exc:  # pragma: no cover
                messages.error(request, f"No se pudo procesar el XLSX: {exc}")
                return redirect(reverse("admin:products_product_import_xlsx"))

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar productos via XLSX",
            "headers": self.product_headers,
            "export_headers": self.export_headers,
            "export_url": f"{reverse('admin:products_product_import_xlsx')}?export=1",
            "created": created,
            "updated": updated,
            "errors": errors,
            "error_summary": error_summary,
            "visible_errors": errors[:20],
            "hidden_error_count": max(len(errors) - 20, 0),
        }
        return TemplateResponse(request, "admin/products/product/import_xlsx.html", context)


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("nombre", "porcentaje", "producto", "categoria", "activo", "empieza", "termina")
    list_filter = ("activo", "empieza", "termina", "categoria")
    search_fields = ("nombre", "descripcion", "producto__nombre", "categoria__nombre")
    prepopulated_fields = {"slug": ("nombre",)}
    list_editable = ("activo",)
    actions = ["activar_ofertas", "desactivar_ofertas"]

    @admin.action(description="Activar ofertas seleccionadas")
    def activar_ofertas(self, request, queryset):
        queryset.update(activo=True)

    @admin.action(description="Desactivar ofertas seleccionadas")
    def desactivar_ofertas(self, request, queryset):
        queryset.update(activo=False)


@admin.register(HomeImage)
class HomeImageAdmin(admin.ModelAdmin):
    list_display = ("key", "section", "title", "target_url", "order", "activo")
    list_filter = ("section", "activo")
    search_fields = ("key", "title", "image_url", "target_url")
    list_editable = ("order", "activo")


@admin.register(HomeMarquee)
class HomeMarqueeAdmin(admin.ModelAdmin):
    form = HomeMarqueeAdminForm
    list_display = ("text", "text_color", "background_color", "activo", "actualizado_en")
    list_editable = ("activo",)

    def has_add_permission(self, request):
        if HomeMarquee.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ("min_order_amount", "actualizado_en")

    def has_add_permission(self, request):
        if StoreSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "order", "image_url", "activo", "creado_en")
    list_filter = ("activo", "product", "creado_en")
    search_fields = ("product__nombre", "image_url")
    search_help_text = "Buscar por nombre del producto o URL de imagen"
    list_editable = ("order", "activo")
