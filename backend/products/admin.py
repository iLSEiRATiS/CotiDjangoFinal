from decimal import Decimal
import os
import openpyxl
from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.text import slugify
import unicodedata

from .models import Product, Category, Offer


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "parent")
    prepopulated_fields = {"slug": ("nombre",)}
    search_fields = ("nombre", "descripcion")
    list_filter = ("parent",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "precio", "user", "categoria", "stock", "activo", "creado_en")
    search_fields = ("nombre", "descripcion", "slug")
    list_filter = ("creado_en", "activo", "categoria")
    list_editable = ("precio", "stock", "activo")
    change_list_template = "admin/products/product/change_list.html"

    template_xlsx_path = r"C:\Users\facun\OneDrive\Escritorio\CotiWeb\Exportacion-productos-03-02-26.fixed.xlsx"

    product_headers = [
        "sku", "parent_sku", "nombre", "slug", "descripcion", "categoria", "subcategoria", "marca",
        "precio", "costo", "moneda", "stock", "activo", "opcion_1_nombre", "opcion_1_valor",
        "opcion_2_nombre", "opcion_2_valor", "imagen_1", "url imag", "imagen_2", "meta_title",
        "meta_description", "peso", "largo", "ancho", "alto", "es_destacado", "requiere_envio",
        "gestion_stock",
    ]

    sample_rows = [
        {
            "sku": "REM-BAS-001",
            "parent_sku": "",
            "nombre": "Remera basica",
            "slug": "remera-basica",
            "descripcion": "Remera algodon lisa",
            "categoria": "Ropa",
            "subcategoria": "Remeras",
            "marca": "Acme",
            "precio": 8999,
            "costo": 4500,
            "moneda": "ARS",
            "stock": 120,
            "activo": True,
            "opcion_1_nombre": "",
            "opcion_1_valor": "",
            "opcion_2_nombre": "",
            "opcion_2_valor": "",
            "imagen_1": "https://example.com/rem-bas-001.jpg",
            "url imag": "",
            "imagen_2": "",
            "meta_title": "Remera basica",
            "meta_description": "Remera de algodon basica",
            "peso": 0.3,
            "largo": 30,
            "ancho": 25,
            "alto": 2,
            "es_destacado": True,
            "requiere_envio": True,
            "gestion_stock": True,
        },
        {
            "sku": "REM-BAS-001-M-NEGRO",
            "parent_sku": "REM-BAS-001",
            "nombre": "Remera basica M Negro",
            "slug": "remera-basica-m-negro",
            "descripcion": "Remera algodon talla M color negro",
            "categoria": "Ropa",
            "subcategoria": "Remeras",
            "marca": "Acme",
            "precio": 8999,
            "costo": 4500,
            "moneda": "ARS",
            "stock": 40,
            "activo": True,
            "opcion_1_nombre": "Talle",
            "opcion_1_valor": "M",
            "opcion_2_nombre": "Color",
            "opcion_2_valor": "Negro",
            "imagen_1": "https://example.com/rem-bas-001-m-negro.jpg",
            "url imag": "",
            "imagen_2": "",
            "meta_title": "Remera basica M negro",
            "meta_description": "Remera negra basica talla M",
            "peso": 0.3,
            "largo": 30,
            "ancho": 25,
            "alto": 2,
            "es_destacado": False,
            "requiere_envio": True,
            "gestion_stock": True,
        },
    ]

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

    def _parse_bool(self, value, default=True):
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        return s in {"true", "1", "si", "sí", "yes", "y"}

    def _parse_decimal(self, value):
        if value is None or value == "":
            return None
        s = str(value).replace("$", "").replace(" ", "").replace(",", ".")
        try:
            return Decimal(s)
        except Exception:
            return None

    def _parse_int(self, value):
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except Exception:
            return None

    def _parse_attr_values(self, value):
        if value in (None, ""):
            return []
        text = str(value).strip()
        if not text:
            return []
        for sep in [",", ";", "|", "/"]:
            if sep in text:
                parts = [p.strip() for p in text.split(sep)]
                return [p for p in parts if p]
        return [text]

    def _strip_attr_from_name(self, name, values):
        if not name:
            return name
        base = str(name)
        for val in values or []:
            if not val:
                continue
            # remove value occurrences (case-insensitive)
            base = base.replace(str(val), "").replace(str(val).lower(), "").replace(str(val).upper(), "")
        # cleanup common separators
        base = base.replace("  ", " ").replace(" - ", " ").replace(" ,", ",").strip(" -_,")
        base = " ".join(base.split())
        return base or name

    def _build_slug(self, base):
        candidate = slugify(base or "")[:110] or "producto"
        original = candidate
        i = 1
        while Product.objects.filter(slug=candidate).exists():
            i += 1
            candidate = f"{original}-{i}"
        return candidate

    def _norm_header(self, value):
        if value is None:
            return ""
        text = str(value).strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        return text

    def _parse_category_path(self, raw):
        if not raw:
            return []
        text = str(raw).strip()
        if not text:
            return []
        for sep in (" > ", ">", " / ", "/", " | ", "|", " - ", "-"):
            if sep in text:
                parts = [p.strip() for p in text.split(sep)]
                return [p for p in parts if p]
        return [text]

    def _export_workbook(self, rows, filename):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Productos"
        ws.append(self.product_headers)
        for row in rows:
            ws.append([row.get(h, "") for h in self.product_headers])
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    def import_xlsx_view(self, request):
        if request.method == "GET" and request.GET.get("sample"):
            return self._export_workbook(self.sample_rows, "productos_ejemplo.xlsx")
        if request.method == "GET" and request.GET.get("template"):
            if os.path.isfile(self.template_xlsx_path):
                with open(self.template_xlsx_path, "rb") as fh:
                    response = HttpResponse(
                        fh.read(),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                    response["Content-Disposition"] = 'attachment; filename="plantilla_productos.xlsx"'
                    return response
            empty_row = {h: "" for h in self.product_headers}
            return self._export_workbook([empty_row], "plantilla_productos.xlsx")

        created = 0
        updated = 0
        errors = []

        if request.method == "POST":
            upload = request.FILES.get("file")
            if not upload:
                messages.error(request, "Selecciona un archivo XLSX.")
                return redirect(
                    reverse("admin:products_product_import_xlsx")
                )
            try:
                wb = openpyxl.load_workbook(upload, data_only=True)
                sheet = wb.active
                rows = list(sheet.iter_rows(values_only=True))
                if not rows:
                    raise ValueError("El archivo est? vac?o.")

                header_idx = None
                header_row = None
                for i, row in enumerate(rows):
                    if not row:
                        continue
                    normalized = [self._norm_header(h) for h in row]
                    if {"sku", "nombre", "precio"}.issubset(set(normalized)):
                        header_idx = i
                        header_row = row
                        break

                if header_row is None:
                    header_row = self.product_headers
                    header_idx = -1

                headers = [self._norm_header(h) for h in header_row]
                alias = {
                    "categorias": "categoria",
                    "categoria": "categoria",
                    "url imag": "url imag",
                    "url_imag": "url imag",
                    "mostrar en tienda": "activo",
                    "nombre atributo 1": "opcion_1_nombre",
                    "valor atributo 1": "opcion_1_valor",
                    "nombre atributo1": "opcion_1_nombre",
                    "valor atributo1": "opcion_1_valor",
                    "nombre atributo 2": "opcion_2_nombre",
                    "valor atributo 2": "opcion_2_valor",
                    "nombre atributo2": "opcion_2_nombre",
                    "valor atributo2": "opcion_2_valor",
                }
                header_map = {}
                for idx, h in enumerate(headers):
                    key = alias.get(h, h)
                    if key:
                        header_map[key] = idx

                missing = {"sku", "nombre", "precio"} - set(header_map.keys())
                if missing:
                    errors.append(f"Faltan columnas obligatorias: {', '.join(sorted(missing))}")

                with transaction.atomic():

                    for idx, raw in enumerate(rows, start=1):
                        if header_idx is not None and idx - 1 == header_idx:
                            continue
                        data = {h: raw[header_map[h]] if h in header_map and header_map[h] < len(raw) else "" for h in header_map}
                        # normaliza claves originales (con y sin mayúsculas)
                        row_data = {k: data.get(k) for k in header_map}
                        if all(v in ("", None) for v in row_data.values()):
                            continue
                        nombre = row_data.get("nombre") or ""
                        precio = self._parse_decimal(row_data.get("precio"))
                        if not nombre:
                            errors.append(f"Fila {idx}: nombre es obligatorio.")
                            continue
                        if precio is None:
                            precio = Decimal("0")
                        opt1_name = (row_data.get("opcion_1_nombre") or "").strip()
                        opt1_val = row_data.get("opcion_1_valor")
                        opt2_name = (row_data.get("opcion_2_nombre") or "").strip()
                        opt2_val = row_data.get("opcion_2_valor")
                        opt1_vals = self._parse_attr_values(opt1_val)
                        opt2_vals = self._parse_attr_values(opt2_val)
                        base_name = self._strip_attr_from_name(nombre, opt1_vals + opt2_vals)

                        parent_sku = (row_data.get("parent_sku") or "").strip()
                        if parent_sku:
                            slug_src = parent_sku
                        elif opt1_name or opt2_name:
                            slug_src = base_name
                        else:
                            slug_src = row_data.get("slug") or row_data.get("sku") or nombre
                        slug = slugify(slug_src)[:110] or self._build_slug(nombre)
                        categoria_raw = row_data.get("categoria") or ""
                        categoria_obj = None
                        if categoria_raw:
                            path_parts = self._parse_category_path(categoria_raw)
                            parent = None
                            for part in path_parts:
                                parent, _ = Category.objects.get_or_create(nombre=part, parent=parent)
                            categoria_obj = parent
                        existing = Product.objects.filter(slug=slug).first()
                        is_new = existing is None
                        product = existing or Product(slug=slug, user=request.user)
                        product.nombre = base_name if (opt1_name or opt2_name) else nombre
                        product.descripcion = row_data.get("descripcion") or ""
                        product.precio = precio
                        stock = self._parse_int(row_data.get("stock"))
                        product.stock = stock if stock is not None else 0
                        product.activo = self._parse_bool(row_data.get("activo"), default=True)
                        product.categoria = categoria_obj
                        attrs = {}
                        if opt1_name:
                            values = opt1_vals
                            if values:
                                attrs[opt1_name] = values
                        if opt2_name:
                            values = opt2_vals
                            if values:
                                attrs[opt2_name] = values
                        if attrs:
                            merged = {}
                            if isinstance(product.atributos, dict):
                                merged.update(product.atributos)
                            for key, values in attrs.items():
                                existing_vals = merged.get(key, [])
                                if not isinstance(existing_vals, list):
                                    existing_vals = [existing_vals] if existing_vals else []
                                combined = list(existing_vals)
                                for v in values:
                                    if v not in combined:
                                        combined.append(v)
                                merged[key] = combined
                            product.atributos = merged
                            # stock por variante (solo si tenemos stock y valor singular)
                            if stock is not None:
                                stock_map = product.atributos_stock if isinstance(product.atributos_stock, dict) else {}
                                for key, values in attrs.items():
                                    if not values:
                                        continue
                                    current = stock_map.get(key, {}) if isinstance(stock_map.get(key), dict) else {}
                                    for v in values:
                                        current[v] = max(int(current.get(v, 0)), int(stock))
                                    stock_map[key] = current
                                product.atributos_stock = stock_map
                        image_url = row_data.get("imagen_1") or row_data.get("url imag") or row_data.get("url_imag") or ""
                        if image_url and str(image_url).startswith(("http://", "https://")):
                            product.image_url = str(image_url).strip()
                        if is_new and not product.slug:
                            product.slug = self._build_slug(nombre)
                        product.save()
                        if is_new:
                            created += 1
                        else:
                            updated += 1
                if created or updated:
                    messages.success(
                        request,
                        f"Importación completada. Nuevos: {created} | Actualizados: {updated}",
                    )
                if errors:
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
