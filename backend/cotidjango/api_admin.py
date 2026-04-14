from datetime import timedelta
from decimal import Decimal
from math import ceil

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order, OrderItem
from products.models import Category, Offer, Product
from .api_common import (
    User,
    _abs_media,
    build_invoice_pdf,
    build_shipping_label_pdf,
    parse_image_urls_payload,
    resolve_category,
    resolve_product,
    serialize_category,
    serialize_order,
    serialize_product,
    serialize_user,
    sync_product_images,
)
from .api_order_utils import build_order_item_input


def _normalize_person_name(value):
    return " ".join(str(value or "").strip().split())


def _build_full_name(first_name, last_name):
    return " ".join(part for part in [_normalize_person_name(first_name), _normalize_person_name(last_name)] if part).strip()


def _parse_shipping_quote_payload(data):
    if not isinstance(data, dict):
        return None
    amount_raw = data.get("amount")
    note = str(data.get("note") or "").strip()
    amount = None
    if amount_raw not in (None, ""):
        try:
            amount = Decimal(str(amount_raw))
        except Exception:
            raise ValidationError("Monto de envio invalido")
        if amount < 0:
            raise ValidationError("El monto de envio no puede ser negativo")
    return {"amount": amount, "note": note}


def _get_order_or_404(pk):
    return Order.objects.prefetch_related("items__product").select_related("user").filter(pk=pk).first()


class AdminOverviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        counts = {"users": User.objects.count(), "products": Product.objects.filter(activo=True).count(), "orders": Order.objects.count()}
        since = timezone.now() - timedelta(days=30)
        recent = Order.objects.filter(creado_en__gte=since, status__in=["paid", "shipped", "delivered"])
        revenue = recent.aggregate(total=Sum("total")).get("total") or Decimal("0.00")
        last_orders = Order.objects.prefetch_related("items__product").select_related("user").order_by("-creado_en")[:5]
        pending_orders = Order.objects.filter(status="created").prefetch_related("items__product").select_related("user").order_by("-creado_en")[:5]
        recent_users = User.objects.order_by("-date_joined")[:5]
        return Response({
            "counts": counts,
            "last30d": {"revenue": float(revenue or 0), "orders": recent.count(), "items": sum(o.items.count() for o in recent)},
            "lastOrders": [serialize_order(o, request) for o in last_orders],
            "pendingOrders": [serialize_order(o, request) for o in pending_orders],
            "recentUsers": [serialize_user(u, request) for u in recent_users],
        })


class AdminUsersView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        page = max(1, int(request.query_params.get("page") or 1))
        limit = max(1, min(100, int(request.query_params.get("limit") or 20)))
        qs = User.objects.all().order_by("-date_joined")
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
            )
        total = qs.count()
        items = qs[(page - 1) * limit:(page - 1) * limit + limit]
        return Response({"items": [serialize_user(u, request) for u in items], "total": total, "page": page, "pages": ceil(total / limit) if total else 1})

    def post(self, request):
        first_name = _normalize_person_name(request.data.get("firstName") or request.data.get("first_name"))
        last_name = _normalize_person_name(request.data.get("lastName") or request.data.get("last_name"))
        name = _build_full_name(first_name, last_name) or _normalize_person_name(request.data.get("name"))
        email = (request.data.get("email") or "").strip().lower()
        password = (request.data.get("password") or "").strip()
        if not first_name or not last_name or not email or not password:
            return Response({"error": "Nombre, apellido, email y password requeridos"}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email__iexact=email).exists():
            return Response({"error": "Email ya registrado"}, status=status.HTTP_409_CONFLICT)
        try:
            validate_password(password)
        except ValidationError as exc:
            return Response({"error": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            name=name,
            first_name=first_name,
            last_name=last_name,
        )
        return Response(serialize_user(user, request), status=status.HTTP_201_CREATED)


class AdminUserDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        if "name" in request.data:
            user.name = _normalize_person_name(request.data.get("name")) or user.name
        if "firstName" in request.data or "first_name" in request.data:
            user.first_name = _normalize_person_name(request.data.get("firstName") or request.data.get("first_name"))
        if "lastName" in request.data or "last_name" in request.data:
            user.last_name = _normalize_person_name(request.data.get("lastName") or request.data.get("last_name"))
        full_name = _build_full_name(user.first_name, user.last_name)
        if full_name:
            user.name = full_name
        if "email" in request.data:
            candidate = str(request.data.get("email") or "").strip().lower()
            if candidate and User.objects.filter(email__iexact=candidate).exclude(pk=user.pk).exists():
                return Response({"error": "Email ya registrado"}, status=status.HTTP_409_CONFLICT)
            if candidate:
                user.email = candidate
                user.username = user.username or candidate
        if "password" in request.data and request.data.get("password"):
            candidate_pwd = request.data.get("password")
            try:
                validate_password(candidate_pwd, user=user)
            except ValidationError as exc:
                return Response({"error": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(candidate_pwd)
        if "shippingQuote" in request.data:
            try:
                shipping_quote = _parse_shipping_quote_payload(request.data.get("shippingQuote"))
            except ValidationError as exc:
                return Response({"error": exc.messages if hasattr(exc, "messages") else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            if shipping_quote is not None:
                user.shipping_quote_amount = shipping_quote["amount"]
                user.shipping_quote_note = shipping_quote["note"]
                user.shipping_quote_updated_at = timezone.now() if (shipping_quote["amount"] is not None or shipping_quote["note"]) else None
        user.save()
        return Response(serialize_user(user, request))

    def delete(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        try:
            user.delete()
        except ProtectedError:
            return Response(
                {
                    "error": (
                        "No se puede borrar este usuario porque tiene productos vinculados "
                        "a pedidos existentes. Desactivalo o reasigna sus productos antes de eliminarlo."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response({"ok": True})


class AdminOrdersView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        status_filter = request.query_params.get("status")
        page = max(1, int(request.query_params.get("page") or 1))
        limit = max(1, min(100, int(request.query_params.get("limit") or 20)))
        qs = Order.objects.select_related("user").prefetch_related("items__product").order_by("-creado_en")
        if status_filter:
            qs = qs.filter(status=status_filter)
        total = qs.count()
        items = qs[(page - 1) * limit:(page - 1) * limit + limit]
        return Response({"items": [serialize_order(o, request) for o in items], "total": total, "page": page, "pages": ceil(total / limit) if total else 1})


class AdminOrderDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, pk):
        order = _get_order_or_404(pk)
        if not order:
            return Response({"error": "Pedido no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        status_val = request.data.get("status")
        if status_val not in {"created", "approved", "pending_payment", "paid", "shipped", "delivered", "cancelled", "draft"}:
            return Response({"error": "Estado invalido"}, status=status.HTTP_400_BAD_REQUEST)
        order.status = status_val
        raw_items = request.data.get("items")
        if isinstance(raw_items, list) and raw_items:
            with transaction.atomic():
                order.items.all().delete()
                built_items = [build_order_item_input(raw, resolve_product) for raw in raw_items]
                built_items = [item for item in built_items if item["name"] and item["product"]]
                if built_items:
                    for it in built_items:
                        OrderItem.objects.create(
                            order=order,
                            product=it["product"],
                            product_name=it["name"],
                            cantidad=it["qty"],
                            precio_unitario=it["price"],
                            atributos=it.get("attrs") or {},
                        )
                    order.recalc_total()
        order.save()
        order.refresh_from_db()
        return Response(serialize_order(order, request))


class AdminOrderPdfView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, pk):
        order = _get_order_or_404(pk)
        if not order:
            return Response({"error": "Pedido no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        pdf_bytes = build_invoice_pdf(order)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="pedido-{order.id}.pdf"'
        return resp


class AdminOrderLabelsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, pk):
        order = _get_order_or_404(pk)
        if not order:
            return Response({"error": "Pedido no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        label_size = request.query_params.get("size", "thermal")
        try:
            num_bultos = max(1, min(99, int(request.query_params.get("bultos", 1))))
        except (ValueError, TypeError):
            num_bultos = 1
        pdf_bytes = build_shipping_label_pdf(order, label_size=label_size, num_bultos=num_bultos)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="rotulo-pedido-{order.id}.pdf"'
        return resp

class AdminProductsView(APIView):
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        page = max(1, int(request.query_params.get("page") or 1))
        limit = max(1, min(100, int(request.query_params.get("limit") or 20)))
        qs = Product.objects.select_related("categoria").prefetch_related("extra_images").order_by("-creado_en")
        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
        total = qs.count()
        items = qs[(page - 1) * limit:(page - 1) * limit + limit]
        return Response({"items": [serialize_product(p, request) for p in items], "total": total, "page": page, "pages": ceil(total / limit) if total else 1})

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        price = request.data.get("price")
        if not name or price is None:
            return Response({"error": "Nombre y precio requeridos"}, status=status.HTTP_400_BAD_REQUEST)
        category = resolve_category(request.data.get("category")) if request.data.get("category") else None
        image_url = request.data.get("imageUrl") or request.data.get("image_url") or ""
        image_urls = parse_image_urls_payload(request.data.get("images"))
        if not image_urls and image_url:
            image_urls = parse_image_urls_payload(image_url)
        product = Product(
            user=request.user,
            nombre=name,
            precio=Decimal(str(price)),
            descripcion=request.data.get("description") or "",
            categoria=category,
            video_url=str(request.data.get("videoUrl") or request.data.get("video_url") or "").strip(),
            stock=int(request.data.get("stock") or 0),
            activo=str(request.data.get("active") or "true").lower() in {"1", "true", "yes"},
        )
        if image_urls:
            product.image_url = image_urls[0]
        elif image_url:
            product.image_url = str(image_url).strip()
        if request.FILES.get("image"):
            product.imagen = request.FILES["image"]
        product.save()
        if image_urls:
            sync_product_images(product, image_urls)
            product.refresh_from_db()
        return Response(serialize_product(product, request), status=status.HTTP_201_CREATED)


class AdminProductDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, pk):
        product = resolve_product(pk)
        if not product:
            return Response({"error": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        if "name" in request.data:
            product.nombre = request.data.get("name") or product.nombre
        if "price" in request.data and request.data.get("price") is not None:
            product.precio = Decimal(str(request.data.get("price")))
        if "description" in request.data:
            product.descripcion = request.data.get("description") or ""
        if "videoUrl" in request.data or "video_url" in request.data:
            product.video_url = str(request.data.get("videoUrl") or request.data.get("video_url") or "").strip()
        if "stock" in request.data:
            product.stock = int(request.data.get("stock") or 0)
        if "active" in request.data:
            product.activo = str(request.data.get("active")).lower() in {"1", "true", "yes"}
        if "category" in request.data:
            product.categoria = resolve_category(request.data.get("category"))
        incoming_images = None
        if "images" in request.data:
            incoming_images = parse_image_urls_payload(request.data.get("images"))
        if "imageUrl" in request.data or "image_url" in request.data:
            product.image_url = str(request.data.get("imageUrl") or request.data.get("image_url") or "").strip()
            if incoming_images is None:
                incoming_images = parse_image_urls_payload(product.image_url)
        if request.FILES.get("image"):
            product.imagen = request.FILES["image"]
        product.save()
        if incoming_images is not None:
            sync_product_images(product, incoming_images)
            product.refresh_from_db()
        return Response(serialize_product(product, request))

    def delete(self, request, pk):
        product = resolve_product(pk)
        if not product:
            return Response({"error": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        product.delete()
        return Response({"ok": True})


class AdminUploadImageView(APIView):
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        file_obj = request.FILES.get("file") or request.FILES.get("image") or request.FILES.get("avatar")
        if not file_obj:
            return Response({"error": "Archivo requerido"}, status=status.HTTP_400_BAD_REQUEST)
        path = default_storage.save(f"uploads/{file_obj.name}", file_obj)
        url = _abs_media(request, default_storage.url(path))
        return Response({"url": url, "path": default_storage.url(path)})


class AdminOffersView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = Offer.objects.select_related("producto", "categoria").order_by("-creado_en")
        data = [{
            "id": o.id,
            "slug": o.slug,
            "name": o.nombre,
            "percent": float(o.porcentaje),
            "active": o.activo,
            "product": serialize_product(o.producto, request) if o.producto else None,
            "category": serialize_category(o.categoria),
            "starts": o.empieza.isoformat() if o.empieza else None,
            "ends": o.termina.isoformat() if o.termina else None,
        } for o in qs]
        return Response({"items": data, "total": len(data)})

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        pct = request.data.get("percent")
        if not name or pct is None:
            return Response({"error": "Nombre y porcentaje requeridos"}, status=status.HTTP_400_BAD_REQUEST)
        product = resolve_product(request.data.get("product")) if request.data.get("product") else None
        category = Category.objects.filter(pk=request.data.get("category")).first() if request.data.get("category") else None
        offer = Offer.objects.create(
            nombre=name,
            descripcion=request.data.get("description") or "",
            porcentaje=Decimal(str(pct)),
            producto=product,
            categoria=category,
            activo=str(request.data.get("active") or "true").lower() in {"1", "true", "yes"},
            empieza=request.data.get("starts") or None,
            termina=request.data.get("ends") or None,
        )
        return Response({"id": offer.id, "name": offer.nombre}, status=status.HTTP_201_CREATED)


class AdminOfferDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, pk):
        offer = Offer.objects.filter(pk=pk).first()
        if not offer:
            return Response({"error": "Oferta no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        if "name" in request.data:
            offer.nombre = request.data.get("name") or offer.nombre
        if "description" in request.data:
            offer.descripcion = request.data.get("description") or ""
        if "percent" in request.data and request.data.get("percent") is not None:
            offer.porcentaje = Decimal(str(request.data.get("percent")))
        if "active" in request.data:
            offer.activo = str(request.data.get("active")).lower() in {"1", "true", "yes"}
        if "product" in request.data:
            offer.producto = resolve_product(request.data.get("product"))
        if "category" in request.data:
            offer.categoria = Category.objects.filter(pk=request.data.get("category")).first() if request.data.get("category") else None
        if "starts" in request.data:
            offer.empieza = request.data.get("starts") or None
        if "ends" in request.data:
            offer.termina = request.data.get("ends") or None
        offer.save()
        return Response({"ok": True})

    def delete(self, request, pk):
        offer = Offer.objects.filter(pk=pk).first()
        if not offer:
            return Response({"error": "Oferta no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        offer.delete()
        return Response({"ok": True})
