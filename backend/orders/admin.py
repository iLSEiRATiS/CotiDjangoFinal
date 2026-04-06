from django import forms
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from products.models import Product

from .models import Order, OrderItem


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
    fields = ("product", "cantidad", "precio_unitario", "subtotal")
    readonly_fields = ("subtotal",)
    autocomplete_fields = ("product",)
    show_change_link = False
    verbose_name = "Producto del pedido"
    verbose_name_plural = "Productos del pedido"

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
    list_display = ("id", "nombre", "email", "status", "total", "creado_en")
    list_filter = ("status", "creado_en")
    search_fields = ("nombre", "email", "telefono", "status")
    autocomplete_fields = ("user",)
    inlines = [OrderItemInline]
    readonly_fields = ("total",)
    actions = ["aprobar", "marcar_pagado", "cancelar"]
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
        product = Product.objects.select_related("categoria").filter(pk=product_id).first()
        if not product:
            return JsonResponse({"error": "Producto no encontrado"}, status=404)
        return JsonResponse(
            {
                "id": product.id,
                "name": product.nombre,
                "category": product.categoria.nombre if product.categoria_id else "",
                "price": str(product.precio),
            }
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalc_total()

    @admin.action(description="Aprobar pedidos seleccionados")
    def aprobar(self, request, queryset):
        queryset.update(status="approved")

    @admin.action(description="Marcar como pagado")
    def marcar_pagado(self, request, queryset):
        queryset.update(status="paid")

    @admin.action(description="Cancelar pedidos")
    def cancelar(self, request, queryset):
        queryset.update(status="cancelled")
