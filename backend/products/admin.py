from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .forms import HomeMarqueeAdminForm, ProductAdminForm
from .models import Category, HomeImage, HomeMarquee, Offer, Product, ProductImage
from .product_importer import PRODUCT_HEADERS, SAMPLE_ROWS, ProductXlsxImporter

admin.site.site_header = "Admin Coti"
admin.site.site_title = "Admin Coti"
admin.site.index_title = "Panel de administracion"


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
    list_display = ("nombre", "slug", "precio", "user", "categoria", "stock", "activo", "creado_en")
    search_fields = ("nombre", "descripcion", "slug")
    list_filter = ("creado_en", "activo", "categoria")
    list_editable = ("precio", "stock", "activo")
    search_help_text = "Buscar producto por nombre, slug o descripcion"
    change_list_template = "admin/products/product/change_list.html"
    inlines = [ProductImageInline]

    template_xlsx_path = r"C:\Users\facun\OneDrive\Escritorio\CotiWeb\Exportacion-productos-03-02-26.fixed.xlsx"
    product_headers = PRODUCT_HEADERS
    sample_rows = SAMPLE_ROWS

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

        created = 0
        updated = 0
        errors = []

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
                        f"Importaci?n completada. Nuevos: {created} | Actualizados: {updated}",
                    )
                for err in errors:
                    messages.error(request, err)
            except Exception as exc:  # pragma: no cover
                messages.error(request, f"No se pudo procesar el XLSX: {exc}")
                return redirect(reverse("admin:products_product_import_xlsx"))

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar productos via XLSX",
            "headers": self.product_headers,
            "example_url": f"{reverse('admin:products_product_import_xlsx')}?sample=1",
            "template_url": f"{reverse('admin:products_product_import_xlsx')}?template=1",
            "created": created,
            "updated": updated,
            "errors": errors,
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


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "order", "image_url", "activo", "creado_en")
    list_filter = ("activo", "product", "creado_en")
    search_fields = ("product__nombre", "image_url")
    search_help_text = "Buscar por nombre del producto o URL de imagen"
    list_editable = ("order", "activo")
