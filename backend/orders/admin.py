from django import forms
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from products.models import Product

from .models import Order, OrderItem
from cotidjango.api_pdf import (
    LABEL_SIZES,
    build_shipping_label_pdf,
    build_invoice_pdf,
    build_stock_request_pdf,
)


LABEL_SIZE_CHOICES = (
    ("thermal", "Estándar térmica 100x150 mm"),
    ("courier", "Via Cargo / Andreani 100x190 mm"),
    ("a4", "Casera A4 (1/4 de hoja)"),
)


class OrderLabelsForm(forms.Form):
    label_size = forms.ChoiceField(label="Tamaño del rótulo", choices=LABEL_SIZE_CHOICES, initial="a4")
    num_bultos = forms.IntegerField(label="Cantidad de bultos", min_value=1, initial=1)

    def clean_label_size(self):
        value = (self.cleaned_data.get("label_size") or "").strip()
        if value not in LABEL_SIZES:
            raise forms.ValidationError("Elegí un tamaño de rótulo válido.")
        return value


class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        for field_name in (
            "destinatario_documento",
            "remitente_nombre",
            "remitente_email",
            "remitente_telefono",
            "remitente_documento",
        ):
            cleaned[field_name] = (cleaned.get(field_name) or "").strip()
        return cleaned


class OrderItemAdminForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "product" in self.fields:
            self.fields["product"].label = "Producto"
            self.fields["product"].help_text = ""
        if "cantidad" in self.fields:
            self.fields["cantidad"].label = "Cantidad"
        if "precio_unitario" in self.fields:
            self.fields["precio_unitario"].label = "Precio unitario"
            self.fields["precio_unitario"].required = False
            self.fields["precio_unitario"].help_text = ""

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        price = cleaned.get("precio_unitario")
        if product and price in (None, ""):
            cleaned["precio_unitario"] = product.precio
        return cleaned


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    form = OrderItemAdminForm
    extra = 0
    fields = ("product", "cantidad", "precio_unitario", "attr_name_1", "attr_value_1", "subtotal")
    readonly_fields = ("subtotal", "attr_name_1", "attr_value_1")
    autocomplete_fields = ("product",)
    show_change_link = False
    verbose_name = "Producto del pedido"
    verbose_name_plural = "Productos del pedido"

    def attr_name_1(self, obj):
        if not obj or not obj.atributos:
            return "-"
        keys = list(obj.atributos.keys())
        return keys[0] if keys else "-"
    attr_name_1.short_description = "Nombre atributo 1"

    def attr_value_1(self, obj):
        if not obj or not obj.atributos:
            return "-"
        values = list(obj.atributos.values())
        return values[0] if values else "-"
    attr_value_1.short_description = "Valor atributo 1"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "product" and formfield is not None:
            widget = formfield.widget
            for attr in ("can_add_related", "can_change_related", "can_delete_related", "can_view_related"):
                if hasattr(widget, attr):
                    setattr(widget, attr, False)
        return formfield


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = ("id", "nombre", "email", "status", "total", "creado_en", "acciones")
    list_filter = ("status", "creado_en")
    search_fields = ("nombre", "email", "telefono", "status")
    autocomplete_fields = ("user",)
    inlines = [OrderItemInline]
    readonly_fields = ("total",)
    actions = ["aprobar", "marcar_pagado", "cancelar"]
    change_form_template = "admin/orders/order/change_form.html"
    fieldsets = (
        (
            "Cliente",
            {
                "fields": ("user", "nombre", "email", "telefono"),
                "description": "Datos principales para identificar y contactar al cliente.",
            },
        ),
        (
            "Entrega",
            {
                "fields": ("direccion", "ciudad", "estado", "cp"),
            },
        ),
        (
            "Datos para rótulo",
            {
                "fields": (
                    "destinatario_documento",
                    ("remitente_nombre", "remitente_documento"),
                    ("remitente_email", "remitente_telefono"),
                ),
                "description": mark_safe(
                    "Estos datos se usan para imprimir rótulos de transporte. "
                    "Si el remitente queda vacío, se usan los datos generales configurados en el sistema."
                ),
            },
        ),
        (
            "Pedido",
            {
                "fields": ("status", "nota", "envio", "total"),
            },
        ),
    )

    class Media:
        css = {"all": ("admin/orders/order_admin.css",)}
        js = ("admin/orders/order_item_price_v2.js",)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/rotulos/",
                self.admin_site.admin_view(self.labels_view),
                name="orders_order_labels",
            ),
            path(
                "<path:object_id>/descargar-pdf/",
                self.admin_site.admin_view(self.download_pdf_view),
                name="orders_order_download_pdf",
            ),
            path(
                "<path:object_id>/descargar-stock-pdf/",
                self.admin_site.admin_view(self.stock_pdf_view),
                name="orders_order_stock_pdf",
            ),
            path(
                "product-price/<int:product_id>/",
                self.admin_site.admin_view(self.product_price_view),
                name="orders_order_product_price",
            ),
            path(
                "user-shipping/<int:user_id>/",
                self.admin_site.admin_view(self.user_shipping_view),
                name="orders_order_user_shipping",
            ),
        ]
        return custom + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["labels_url"] = self._labels_url(object_id)
        extra_context["download_pdf_url"] = self._download_pdf_url(object_id)
        extra_context["stock_pdf_url"] = self._stock_pdf_url(object_id)
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

    def _labels_url(self, object_id):
        if not object_id:
            return ""
        return reverse("admin:orders_order_labels", args=[object_id])

    def _download_pdf_url(self, object_id):
        if not object_id:
            return ""
        return reverse("admin:orders_order_download_pdf", args=[object_id])

    def _stock_pdf_url(self, object_id):
        if not object_id:
            return ""
        return reverse("admin:orders_order_stock_pdf", args=[object_id])

    @admin.display(description="Acciones")
    def acciones(self, obj):
        change_url = reverse("admin:orders_order_change", args=[obj.pk])
        labels_url = reverse("admin:orders_order_labels", args=[obj.pk])
        pdf_url = reverse("admin:orders_order_download_pdf", args=[obj.pk])
        stock_url = reverse("admin:orders_order_stock_pdf", args=[obj.pk])
        return format_html(
            '<div style="display: flex; gap: 4px; flex-wrap: wrap; min-width: max-content;">'
            '<a class="button" href="{}">Ver</a>'
            '<a class="button default" href="{}">Rótulo</a>'
            '<a class="button default" href="{}">Descargar</a>'
            '<a class="button default" href="{}">Pedir Stock</a>'
            '</div>',
            change_url,
            labels_url,
            pdf_url,
            stock_url,
        )

    def download_pdf_view(self, request, object_id):
        order = get_object_or_404(Order, pk=object_id)
        pdf = build_invoice_pdf(order)
        response = HttpResponse(pdf, content_type="application/pdf")
        filename = f"pedido-{order.id}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def stock_pdf_view(self, request, object_id):
        order = get_object_or_404(Order, pk=object_id)
        pdf = build_stock_request_pdf(order)
        response = HttpResponse(pdf, content_type="application/pdf")
        filename = f"pedido-stock-{order.id}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def labels_view(self, request, object_id):
        order = get_object_or_404(Order, pk=object_id)
        if request.method == "POST":
            form = OrderLabelsForm(request.POST)
            if form.is_valid():
                label_size = form.cleaned_data["label_size"]
                num_bultos = form.cleaned_data["num_bultos"]
                pdf = build_shipping_label_pdf(order, label_size=label_size, num_bultos=num_bultos)
                response = HttpResponse(pdf, content_type="application/pdf")
                response["Content-Disposition"] = f'attachment; filename="rotulos-pedido-{order.id}.pdf"'
                return response
        else:
            form = OrderLabelsForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": order,
            "order": order,
            "title": f"Imprimir rótulos del pedido #{order.id}",
            "form": form,
            "label_sizes": LABEL_SIZE_CHOICES,
        }
        return TemplateResponse(request, "admin/orders/order/labels_form.html", context)

    def user_shipping_view(self, request, user_id):
        user_model = Order._meta.get_field("user").remote_field.model
        user = user_model.objects.filter(pk=user_id).first()
        if not user:
            return JsonResponse({"error": "Usuario no encontrado"}, status=404)
        amount = getattr(user, "shipping_quote_amount", None)
        note = str(getattr(user, "shipping_quote_note", "") or "").strip()
        return JsonResponse(
            {
                "id": user.id,
                "amount": str(amount) if amount is not None else "",
                "note": note,
                "available": amount is not None or bool(note),
            }
        )

    def product_price_view(self, request, product_id):
        from cotidjango.api_common import resolve_discount_for_product
        product = Product.objects.select_related("categoria").filter(pk=product_id).first()
        if not product:
            return JsonResponse({"error": "Producto no encontrado"}, status=404)
        
        # Resolve active discount if any
        discount = resolve_discount_for_product(product)
        final_price = discount["final_price"] if discount else product.precio
        
        return JsonResponse(
            {
                "id": product.id,
                "name": product.nombre,
                "category": product.categoria.nombre if product.categoria_id else "",
                "price": str(final_price),
            }
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalc_total()

    def save_model(self, request, obj, form, change):
        for field_name in (
            "destinatario_documento",
            "remitente_nombre",
            "remitente_email",
            "remitente_telefono",
            "remitente_documento",
        ):
            setattr(obj, field_name, (getattr(obj, field_name, "") or "").strip())
        super().save_model(request, obj, form, change)

    @admin.action(description="Aprobar pedidos seleccionados")
    def aprobar(self, request, queryset):
        queryset.update(status="approved")

    @admin.action(description="Marcar como pagado")
    def marcar_pagado(self, request, queryset):
        queryset.update(status="paid")

    @admin.action(description="Cancelar pedidos")
    def cancelar(self, request, queryset):
        queryset.update(status="cancelled")
