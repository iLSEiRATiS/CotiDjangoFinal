from decimal import Decimal

from django.db import transaction
from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order, OrderItem
from products.models import StoreSettings
from .api_common import build_invoice_pdf, resolve_product, send_admin_order_email, send_invoice_email, serialize_order
from .api_order_utils import build_order_item_input


def _get_order_for_user(user, pk):
    order = Order.objects.prefetch_related("items__product").select_related("user").filter(pk=pk).first()
    if not order:
        return None, Response({"error": "Pedido no encontrado"}, status=status.HTTP_404_NOT_FOUND)
    if order.user_id != user.id and not user.is_staff:
        return None, Response({"error": "Sin permiso"}, status=status.HTTP_403_FORBIDDEN)
    return order, None


class OrderCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        raw_items = request.data.get("items") or []
        shipping = request.data.get("shipping") or {}
        note = (request.data.get("note") or request.data.get("nota") or "").strip()
        if len(note) > 1000:
            note = note[:1000]
        if not isinstance(shipping, dict):
            shipping = {}

        email = shipping.get("email") or request.user.email or ""
        phone = shipping.get("phone") or request.user.phone or ""
        missing = []
        if not (shipping.get("name") or request.user.name or request.user.username):
            missing.append("nombre")
        if not email:
            missing.append("email")
        if not phone:
            missing.append("telefono")
        if not shipping.get("address"):
            missing.append("direccion")
        if not shipping.get("city"):
            missing.append("ciudad")
        if not shipping.get("zip"):
            missing.append("cp")
        if missing:
            return Response({"error": f"Faltan datos obligatorios: {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(raw_items, list) or not raw_items:
            return Response({"error": "Carrito vacio"}, status=status.HTTP_400_BAD_REQUEST)

        built_items = [build_order_item_input(raw, resolve_product) for raw in raw_items]
        built_items = [item for item in built_items if item["name"]]

        if not built_items:
            return Response({"error": "Carrito vacio"}, status=status.HTTP_400_BAD_REQUEST)
        total_amount = sum((item["price"] * item["qty"] for item in built_items), Decimal("0.00"))
        min_order_amount = StoreSettings.get_solo().min_order_amount
        if total_amount < min_order_amount:
            return Response(
                {"error": f"¡Ya casi terminás tu compra! El mínimo es de ${min_order_amount:,.2f}. Podés agregar algunos productos más para alcanzarlo. ¡Gracias!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                nombre=shipping.get("name") or request.user.name or request.user.username,
                email=email,
                direccion=shipping.get("address") or "",
                ciudad=shipping.get("city") or "",
                estado="",
                cp=shipping.get("zip") or "",
                telefono=phone,
                nota=note,
                status="created",
                total=Decimal("0.00"),
            )
            for item in built_items:
                if item["product"] is None:
                    transaction.set_rollback(True)
                    return Response({"error": "Producto no encontrado"}, status=status.HTTP_400_BAD_REQUEST)
                OrderItem.objects.create(
                    order=order,
                    product=item["product"],
                    product_name=item["name"],
                    cantidad=item["qty"],
                    precio_unitario=item["price"],
                    atributos=item.get("attrs") or {},
                )
            order.recalc_total()

        order = Order.objects.prefetch_related("items__product").select_related("user").get(pk=order.pk)
        try:
            send_invoice_email(order, request)
        except Exception:
            pass
        try:
            send_admin_order_email(order, request)
        except Exception:
            pass
        return Response({"order": serialize_order(order, request)}, status=status.HTTP_201_CREATED)


class MyOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Order.objects.filter(user=request.user).prefetch_related("items__product").order_by("-creado_en")
        return Response({"orders": [serialize_order(o, request) for o in qs]})


class OrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        order, error_response = _get_order_for_user(request.user, pk)
        if error_response:
            return error_response
        return Response({"order": serialize_order(order, request)})


class OrderPdfView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        order, error_response = _get_order_for_user(request.user, pk)
        if error_response:
            return error_response
        pdf_bytes = build_invoice_pdf(order)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="pedido-{order.id}.pdf"'
        return resp


class OrderMarkPaidView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        order, error_response = _get_order_for_user(request.user, pk)
        if error_response:
            return error_response
        if order.status != "approved":
            return Response({"error": "Tu pedido aun no fue aprobado por el administrador"}, status=status.HTTP_400_BAD_REQUEST)
        order.status = "paid"
        order.save(update_fields=["status"])
        try:
            send_invoice_email(order, request)
        except Exception:
            pass
        return Response({"order": serialize_order(order, request)})
