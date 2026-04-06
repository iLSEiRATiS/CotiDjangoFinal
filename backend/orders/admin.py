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
            self.fields["product"].help_text = "Busca por nombre o categoria. El resultado muestra categoria y precio."
        if "precio_unitario" in self.fields:
            self.fields["precio_unitario"].required = False
            self.fields["precio_unitario"].help_text = (
                "Podes modificar este valor. Si lo dejas vacio, se usa el precio actual del producto."
            )

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
    extra = 1
    fields = ("product", "cantidad", "precio_unitario", "subtotal")
    readonly_fields = ("subtotal",)
    autocomplete_fields = ("product",)
    show_change_link = True
    verbose_name = "Producto del pedido"
    verbose_name_plural = "Productos del pedido"


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
                "fields": ("status", "nota", "total"),
            },
        ),
    )

    class Media:
        js = ("admin/orders/order_item_price_v2.js",)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "product-price/<int:product_id>/",
                self.admin_site.admin_view(self.product_price_view),
                name="orders_order_product_price",
            ),
        ]
        return custom + urls

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

    @admin.action(description="Aprobar pedidos seleccionados")
    def aprobar(self, request, queryset):
        queryset.update(status="approved")

    @admin.action(description="Marcar como pagado")
    def marcar_pagado(self, request, queryset):
        queryset.update(status="paid")

    @admin.action(description="Cancelar pedidos")
    def cancelar(self, request, queryset):
        queryset.update(status="cancelled")
