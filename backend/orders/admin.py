from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("subtotal",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "email", "status", "total", "creado_en")
    list_filter = ("status", "creado_en")
    search_fields = ("nombre", "email", "status")
    inlines = [OrderItemInline]
    readonly_fields = ("total",)
    actions = ["aprobar", "marcar_pagado", "cancelar"]

    @admin.action(description="Aprobar pedidos seleccionados")
    def aprobar(self, request, queryset):
        queryset.update(status="approved")

    @admin.action(description="Marcar como pagado")
    def marcar_pagado(self, request, queryset):
        queryset.update(status="paid")

    @admin.action(description="Cancelar pedidos")
    def cancelar(self, request, queryset):
        queryset.update(status="cancelled")
