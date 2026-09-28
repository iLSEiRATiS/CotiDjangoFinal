from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from products.models import Product

from .models import Order, OrderItem, PaidOrder
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
    actualizar_precio_producto = forms.BooleanField(
        label="¿Actualizar en tienda?",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            "title": "Tildá esta casilla para que el nuevo precio impacte en el producto de la página web al guardar",
        }),
    )

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
        if "actualizar_precio_producto" in self.fields:
            self.fields["actualizar_precio_producto"].label = "¿Actualizar en tienda?"
            self.fields["actualizar_precio_producto"].help_text = ""

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
    fields = ("product", "cantidad", "precio_unitario", "actualizar_precio_producto", "attr_name_1", "attr_value_1", "subtotal")
    readonly_fields = ("subtotal", "attr_name_1", "attr_value_1")
    autocomplete_fields = ("product",)
    show_change_link = False
    verbose_name = "Producto del pedido"
    verbose_name_plural = "Productos del pedido"

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if hasattr(request.user, "role") and request.user.role == "operator":
            return tuple(f for f in fields if f not in ("precio_unitario", "actualizar_precio_producto", "subtotal"))
        return fields

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
    change_list_template = "admin/orders/order/change_list.html"
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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self.model == PaidOrder:
            return qs.filter(status="paid")
        return qs.exclude(status="paid")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["pending_orders_count"] = Order.objects.exclude(status="paid").count()
        extra_context["paid_orders_count"] = Order.objects.filter(status="paid").count()
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/rotulos/",
                self.admin_site.admin_view(self.labels_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_labels",
            ),
            path(
                "<path:object_id>/descargar-pdf/",
                self.admin_site.admin_view(self.download_pdf_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_download_pdf",
            ),
            path(
                "<path:object_id>/descargar-stock-pdf/",
                self.admin_site.admin_view(self.stock_pdf_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_stock_pdf",
            ),
            path(
                "product-price/<int:product_id>/",
                self.admin_site.admin_view(self.product_price_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_product_price",
            ),
            path(
                "user-shipping/<int:user_id>/",
                self.admin_site.admin_view(self.user_shipping_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_user_shipping",
            ),
        ]
        return custom + urls

    def has_module_permission(self, request):
        if hasattr(request.user, "role") and request.user.role == "operator":
            return True
        return super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        if hasattr(request.user, "role") and request.user.role == "operator":
            return True
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if hasattr(request.user, "role") and request.user.role == "operator":
            return True
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if hasattr(request.user, "role") and request.user.role == "operator":
            return False
        return super().has_delete_permission(request, obj)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["labels_url"] = self._labels_url(object_id)
        if hasattr(request.user, "role") and request.user.role == "operator":
            extra_context["download_pdf_url"] = ""
        else:
            extra_context["download_pdf_url"] = self._download_pdf_url(object_id)
        extra_context["stock_pdf_url"] = self._stock_pdf_url(object_id)
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

    def get_list_display(self, request):
        if hasattr(request.user, "role") and request.user.role == "operator":
            return ("id", "nombre", "email", "status", "creado_en", "acciones_operator")
        return super().get_list_display(request)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if hasattr(request.user, "role") and request.user.role == "operator":
            new_fieldsets = []
            for name, opts in fieldsets:
                if name == "Pedido":
                    fields = tuple(f for f in opts.get("fields", []) if f not in ("total", "envio"))
                    new_opts = dict(opts)
                    new_opts["fields"] = fields
                    new_fieldsets.append((name, new_opts))
                else:
                    new_fieldsets.append((name, opts))
            return new_fieldsets
        return fieldsets

    def _labels_url(self, object_id):
        if not object_id:
            return ""
        return reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_labels", args=[object_id])

    def _download_pdf_url(self, object_id):
        if not object_id:
            return ""
        return reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_download_pdf", args=[object_id])

    def _stock_pdf_url(self, object_id):
        if not object_id:
            return ""
        return reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_stock_pdf", args=[object_id])

    @admin.display(description="Acciones")
    def acciones(self, obj):
        change_url = reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
        labels_url = self._labels_url(obj.pk)
        pdf_url = self._download_pdf_url(obj.pk)
        stock_url = self._stock_pdf_url(obj.pk)
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

    @admin.display(description="Acciones")
    def acciones_operator(self, obj):
        change_url = reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
        labels_url = self._labels_url(obj.pk)
        stock_url = self._stock_pdf_url(obj.pk)
        return format_html(
            '<div style="display: flex; gap: 4px; flex-wrap: wrap; min-width: max-content;">'
            '<a class="button" href="{}">Ver</a>'
            '<a class="button default" href="{}">Rótulo</a>'
            '<a class="button default" href="{}">Pedir Stock</a>'
            '</div>',
            change_url,
            labels_url,
            stock_url,
        )

    def download_pdf_view(self, request, object_id):
        if hasattr(request.user, "role") and request.user.role == "operator":
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("No tienes permiso para descargar presupuestos.")
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

    def save_formset(self, request, form, formset, change):
        if formset.model == OrderItem:
            updated_products = {}
            is_operator = hasattr(request.user, "role") and request.user.role == "operator"

            if not is_operator:
                for form_item in formset.forms:
                    if not form_item.is_valid() or form_item.cleaned_data.get("DELETE"):
                        continue

                    should_update = form_item.cleaned_data.get("actualizar_precio_producto")
                    product = form_item.cleaned_data.get("product") or getattr(form_item.instance, "product", None)
                    new_price = form_item.cleaned_data.get("precio_unitario")

                    if should_update and product and new_price is not None:
                        prod_obj = Product.objects.filter(pk=product.pk).first()
                        if prod_obj:
                            prod_obj.precio = new_price

                            attrs = getattr(form_item.instance, "atributos", None) or form_item.cleaned_data.get("atributos")
                            if prod_obj.atributos_precio and isinstance(prod_obj.atributos_precio, dict) and attrs and isinstance(attrs, dict):
                                new_attrs_price = dict(prod_obj.atributos_precio)
                                attrs_updated = False
                                for attr_name, val in attrs.items():
                                    for p_attr, p_map in new_attrs_price.items():
                                        if str(p_attr).strip().lower() == str(attr_name).strip().lower() and isinstance(p_map, dict):
                                            p_map_copy = dict(p_map)
                                            for p_val in p_map:
                                                if str(p_val).strip().lower() == str(val).strip().lower():
                                                    p_map_copy[p_val] = float(new_price)
                                                    attrs_updated = True
                                            new_attrs_price[p_attr] = p_map_copy
                                if attrs_updated:
                                    prod_obj.atributos_precio = new_attrs_price

                            prod_obj.save()
                            updated_products[prod_obj.id] = f"{prod_obj.nombre} (${new_price})"

            super().save_formset(request, form, formset, change)

            if updated_products:
                messages.success(
                    request,
                    f"¡Precios impactados en la página web con éxito! {', '.join(updated_products.values())}"
                )
        else:
            super().save_formset(request, form, formset, change)

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

    @admin.action(description="Marcar como pagado (transferir a Pedidos pagados)")
    def marcar_pagado(self, request, queryset):
        count = queryset.update(status="paid")
        self.message_user(
            request,
            f"Se marcaron {count} pedido(s) como pagados y se transfirieron a 'Pedidos pagados'.",
            messages.SUCCESS,
        )

    @admin.action(description="Cancelar pedidos seleccionados")
    def cancelar(self, request, queryset):
        queryset.update(status="cancelled")


@admin.register(PaidOrder)
class PaidOrderAdmin(OrderAdmin):
    list_display = ("id", "nombre", "email", "status", "total", "creado_en", "acciones")
    list_filter = ("creado_en",)
    actions = ["desmarcar_pagado", "cancelar"]

    @admin.action(description="Revertir pago (devolver a Pedidos a procesar)")
    def desmarcar_pagado(self, request, queryset):
        count = queryset.update(status="approved")
        self.message_user(
            request,
            f"Se revirtieron {count} pedido(s) y volvieron a 'Pedidos a procesar'.",
            messages.INFO,
        )


