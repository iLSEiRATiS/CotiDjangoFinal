from datetime import timedelta
from decimal import Decimal
from math import ceil

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction, models
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from django.core.mail import EmailMessage

from orders.models import Order, OrderItem
from products.models import Category, Product, Offer

User = get_user_model()


def build_token(user):
    token = AccessToken.for_user(user)
    token.set_exp(from_time=timezone.now(), lifetime=timedelta(days=7))
    return str(token)


def _abs_media(request, path):
    if not path:
        return None
    if str(path).startswith("http"):
        return path
    base = request.build_absolute_uri("/")
    return f"{base.rstrip('/')}/{str(path).lstrip('/')}"


def serialize_user(user, request=None):
    return {
        "_id": str(user.id),
        "id": user.id,
        "name": user.name or user.username,
        "email": user.email,
        "role": user.role,
        "profile": {
            "phone": user.phone or "",
            "avatar": _abs_media(request, user.avatar.url) if (request and user.avatar) else None,
        },
        "shipping": {
            "name": user.name or "",
            "address": user.address or "",
            "city": user.city or "",
            "zip": user.zip_code or "",
            "phone": user.phone or "",
        },
        "createdAt": user.date_joined.isoformat() if user.date_joined else None,
        "updatedAt": user.last_login.isoformat() if user.last_login else None,
    }


def serialize_category(cat):
    if not cat:
        return None
    return {"_id": cat.id, "id": cat.id, "name": cat.nombre, "slug": cat.slug}


def serialize_product(prod, request=None):
    images = []
    if prod.imagen:
        images.append(_abs_media(request, prod.imagen.url))
    discount = resolve_discount_for_product(prod)
    final_price = discount["final_price"] if discount else prod.precio
    return {
        "_id": prod.id,
        "id": prod.id,
        "slug": prod.slug,
        "name": prod.nombre,
        "price": float(final_price),
        "priceOriginal": float(prod.precio),
        "discount": discount["meta"] if discount else None,
        "description": prod.descripcion or "",
        "images": images,
        "category": serialize_category(prod.categoria),
        "stock": prod.stock,
        "active": prod.activo,
        "createdAt": prod.creado_en.isoformat() if prod.creado_en else None,
        "updatedAt": None,
    }


def serialize_order(order, request=None):
    status_labels = {
        "created": "Creado",
        "approved": "Aprobado",
        "paid": "Pagado",
        "shipped": "Enviado",
        "delivered": "Entregado",
        "cancelled": "Cancelado",
        "draft": "Borrador",
    }
    items = []
    for item in order.items.all():
        items.append({
            "productId": item.product_id,
            "name": item.product.nombre if item.product else "",
            "price": float(item.precio_unitario),
            "qty": item.cantidad,
            "subtotal": float(item.subtotal),
        })
    totals = {
        "items": sum(it["qty"] for it in items),
        "amount": float(order.total or 0),
    }
    return {
        "_id": order.id,
        "id": order.id,
        "user": serialize_user(order.user, request) if order.user else None,
        "items": items,
        "totals": totals,
        "status": order.status,
        "status_label": status_labels.get(order.status, order.status),
        "shipping": {
            "name": order.nombre,
            "address": order.direccion,
            "city": order.ciudad,
            "zip": order.cp,
            "phone": order.telefono,
        },
        "createdAt": order.creado_en.isoformat() if order.creado_en else None,
    }


def resolve_category(value):
    if not value:
        return None
    slug = slugify(str(value))
    cat, _ = Category.objects.get_or_create(slug=slug, defaults={"nombre": value})
    return cat


def resolve_product(value):
    if not value:
        return None
    try:
        return Product.objects.get(pk=value)
    except Exception:
        return Product.objects.filter(slug=value).first()


def resolve_discount_for_product(product: Product):
    now = timezone.now()
    offers = Offer.objects.filter(activo=True).filter(
        models.Q(producto=product) | models.Q(categoria=product.categoria)
    )
    offers = offers.filter(
        models.Q(empieza__isnull=True) | models.Q(empieza__lte=now),
        models.Q(termina__isnull=True) | models.Q(termina__gte=now),
    ).order_by("-porcentaje")
    offer = offers.first()
    if not offer:
        return None
    pct = offer.porcentaje or Decimal("0")
    final_price = product.precio * (Decimal("1.00") - (pct / Decimal("100")))
    if final_price < 0:
        final_price = Decimal("0.00")
    return {
        "final_price": final_price,
        "meta": {
            "percent": float(pct),
            "label": f"-{pct}%",
            "offerId": offer.id,
            "offerSlug": offer.slug,
        },
    }


def _escape_pdf_text(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_invoice_pdf(order) -> bytes:
    # PDF simple (texto) sin dependencias externas
    lines = []
    lines.append(f"Factura / Pedido #{order.id}")
    lines.append(f"Fecha: {order.creado_en.strftime('%Y-%m-%d %H:%M') if order.creado_en else ''}")
    lines.append(f"Cliente: {order.nombre} - {order.email}")
    addr = ", ".join(filter(None, [order.direccion, order.ciudad, order.cp]))
    lines.append(f"Envio: {addr}")
    lines.append("")
    lines.append("Items:")
    for item in order.items.all():
        lines.append(f"- {item.product.nombre} x{item.cantidad} @ ${item.precio_unitario} = ${item.subtotal}")
    lines.append("")
    lines.append(f"Total: ${order.total}")
    lines.append(f"Estado: {order.status}")

    # Construccion minimalista del PDF
    content_parts = []
    content_parts.append("BT /F1 12 Tf 50 760 Td")
    first = True
    for ln in lines:
        if first:
            content_parts.append(f"({_escape_pdf_text(ln)}) Tj")
            first = False
        else:
            content_parts.append("0 -16 Td")
            content_parts.append(f"({_escape_pdf_text(ln)}) Tj")
    content_parts.append("ET")
    content = "\n".join(content_parts)
    content_bytes = content.encode("latin-1", errors="replace")

    objects = []
    # 1: catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # 2: pages
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # 3: page
    objects.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n")
    # 4: font
    objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    # 5: contents
    objects.append(b"5 0 obj\n<< /Length %d >>\nstream\n" % len(content_bytes))
    objects.append(content_bytes + b"\nendstream\nendobj\n")

    pdf_parts = [b"%PDF-1.4\n"]
    offsets = []
    pos = len(pdf_parts[0])
    for obj in objects:
        offsets.append(pos)
        pdf_parts.append(obj)
        pos += len(obj)
    xref_pos = pos
    pdf_parts.append(b"xref\n0 %d\n" % (len(objects) + 1))
    pdf_parts.append(b"0000000000 65535 f \n")
    for off in offsets:
        pdf_parts.append(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf_parts.append(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%EOF" % (len(objects) + 1, xref_pos))
    return b"".join(pdf_parts)


def send_invoice_email(order, request=None):
    if not order.email:
        return
    pdf_bytes = build_invoice_pdf(order)
    subject = f"Presupuesto de tu pedido #{order.id}"
    body = (
        f"Hola {order.nombre},\n\n"
        f"Adjuntamos el presupuesto de tu pedido #{order.id}.\n"
        f"Total: ${order.total}\n"
        f"Estado: {order.status}\n\n"
        "Gracias por tu compra."
    )
    email = EmailMessage(subject, body, to=[order.email])
    email.attach(f"pedido-{order.id}.pdf", pdf_bytes, "application/pdf")
    try:
        email.send(fail_silently=True)
    except Exception:
        pass


class AuthRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        email = (request.data.get("email") or "").strip().lower()
        password = (request.data.get("password") or "").strip()
        if not name or not email or not password:
            return Response({"error": "Faltan campos"}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
            return Response({"error": "Email ya registrado"}, status=status.HTTP_409_CONFLICT)
        username = email or slugify(name) or f"user-{timezone.now().timestamp()}"
        user = User.objects.create_user(username=username, email=email, password=password, name=name)
        token = build_token(user)
        return Response({"token": token, "user": serialize_user(user, request)}, status=status.HTTP_201_CREATED)


class AuthLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get("email") or request.data.get("username") or "").strip()
        password = (request.data.get("password") or "").strip()
        if not email or not password:
            return Response({"error": "Email y contrasena son requeridos"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=email, password=password)
        if not user and "@" in email:
            candidate = User.objects.filter(email__iexact=email).first()
            if candidate:
                user = authenticate(request, username=candidate.username, password=password)
        if not user:
            return Response({"error": "Credenciales invalidas"}, status=status.HTTP_401_UNAUTHORIZED)

        token = build_token(user)
        return Response({"token": token, "user": serialize_user(user, request)})


class AuthMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"user": serialize_user(request.user, request)})


class AccountProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        return Response({"user": serialize_user(request.user, request)})

    def patch(self, request):
        user = request.user
        name = request.data.get("name")
        email = request.data.get("email")
        profile = request.data.get("profile") if isinstance(request.data.get("profile"), dict) else {}
        shipping = request.data.get("shipping") if isinstance(request.data.get("shipping"), dict) else {}
        profile_phone = request.data.get("profilePhone")
        remove_avatar = str(request.data.get("removeAvatar") or "").lower() in {"1", "true", "yes"}
        avatar_file = request.FILES.get("avatar")

        if email:
            normalized_email = str(email).strip().lower()
            exists = User.objects.filter(Q(email__iexact=normalized_email) | Q(username__iexact=normalized_email)).exclude(pk=user.pk).exists()
            if exists:
                return Response({"error": "Email ya registrado"}, status=status.HTTP_409_CONFLICT)
            user.email = normalized_email
            user.username = user.username or normalized_email

        if name is not None:
            user.name = name

        phone_val = profile.get("phone") if profile else None
        if profile_phone is not None:
            phone_val = profile_phone
        if phone_val is not None:
            user.phone = phone_val

        if shipping:
            if "name" in shipping:
                user.name = shipping.get("name") or user.name
            if "address" in shipping:
                user.address = shipping.get("address") or ""
            if "city" in shipping:
                user.city = shipping.get("city") or ""
            if "zip" in shipping:
                user.zip_code = shipping.get("zip") or ""
            if "phone" in shipping:
                user.phone = shipping.get("phone") or user.phone

        if remove_avatar and user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None
        if avatar_file:
            user.avatar = avatar_file

        user.save()
        return Response({"user": serialize_user(user, request)})


class AccountPasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        current = request.data.get("currentPassword") or request.data.get("old_password")
        new = request.data.get("newPassword") or request.data.get("new_password")
        if not current or not new:
            return Response({"error": "Faltan campos"}, status=status.HTTP_400_BAD_REQUEST)
        if not request.user.check_password(current):
            return Response({"error": "Contrasena actual incorrecta"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new, user=request.user)
        except ValidationError as exc:
            return Response({"error": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(new)
        request.user.save()
        return Response({"detail": "Contrasena actualizada"})


class ProductListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = (request.query_params.get("q") or request.query_params.get("search") or "").strip()
        category = request.query_params.get("category") or request.query_params.get("cat")
        page = max(1, int(request.query_params.get("page") or 1))
        limit = max(1, min(100, int(request.query_params.get("limit") or 20)))

        qs = Product.objects.filter(activo=True).select_related("categoria")
        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
        if category:
            qs = qs.filter(categoria__slug=category)

        total = qs.count()
        start = (page - 1) * limit
        items = qs.order_by("-creado_en")[start:start + limit]
        data = [serialize_product(p, request) for p in items]
        return Response({"items": data, "total": total, "page": page, "pages": ceil(total / limit) if total else 1})


class ProductDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        prod = resolve_product(pk)
        if not prod:
            return Response({"error": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_product(prod, request))


class OrderCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        raw_items = request.data.get("items") or []
        shipping = request.data.get("shipping") or {}
        if not isinstance(shipping, dict):
            shipping = {}
        if not isinstance(raw_items, list) or not raw_items:
            return Response({"error": "Carrito vacio"}, status=status.HTTP_400_BAD_REQUEST)

        built_items = []
        for raw in raw_items:
            pid = raw.get("productId") or raw.get("product_id") or raw.get("id") or raw.get("slug")
            product = resolve_product(pid)
            qty = max(1, int(raw.get("qty") or raw.get("cantidad") or 1))
            price = raw.get("price")
            if price is None and product:
                price = product.precio
            price = Decimal(str(price or 0))
            name = raw.get("name") or (product.nombre if product else "")
            if not name:
                continue
            built_items.append({"product": product, "qty": qty, "price": price, "name": name})

        if not built_items:
            return Response({"error": "Carrito vacio"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                nombre=shipping.get("name") or request.user.name or request.user.username,
                email=request.user.email or "",
                direccion=shipping.get("address") or "",
                ciudad=shipping.get("city") or "",
                estado="",
                cp=shipping.get("zip") or "",
                telefono=shipping.get("phone") or request.user.phone,
                nota="",
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
                    cantidad=item["qty"],
                    precio_unitario=item["price"],
                )
            order.recalc_total()

        order = Order.objects.prefetch_related("items__product").select_related("user").get(pk=order.pk)
        send_invoice_email(order, request)
        return Response({"order": serialize_order(order, request)}, status=status.HTTP_201_CREATED)


class MyOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Order.objects.filter(user=request.user).prefetch_related("items__product").order_by("-creado_en")
        return Response({"orders": [serialize_order(o, request) for o in qs]})


class OrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        order = Order.objects.prefetch_related("items__product").select_related("user").filter(pk=pk).first()
        if not order:
            return Response({"error": "Pedido no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        is_owner = order.user_id == request.user.id
        if not is_owner and not request.user.is_staff:
            return Response({"error": "Sin permiso"}, status=status.HTTP_403_FORBIDDEN)
        return Response({"order": serialize_order(order, request)})


class OrderMarkPaidView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        order = Order.objects.prefetch_related("items__product").select_related("user").filter(pk=pk).first()
        if not order:
            return Response({"error": "Pedido no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        is_owner = order.user_id == request.user.id
        if not is_owner and not request.user.is_staff:
            return Response({"error": "Sin permiso"}, status=status.HTTP_403_FORBIDDEN)
        if order.status != "approved":
            return Response({"error": "Tu pedido aun no fue aprobado por el administrador"}, status=status.HTTP_400_BAD_REQUEST)
        order.status = "paid"
        order.save(update_fields=["status"])
        send_invoice_email(order, request)
        return Response({"order": serialize_order(order, request)})


class AdminOverviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        counts = {
            "users": User.objects.count(),
            "products": Product.objects.count(),
            "orders": Order.objects.count(),
        }
        since = timezone.now() - timedelta(days=30)
        paid_states = ["paid", "shipped", "delivered"]
        recent = Order.objects.filter(creado_en__gte=since, status__in=paid_states)
        revenue = recent.aggregate(total=Sum("total")).get("total") or Decimal("0.00")
        last_orders = Order.objects.prefetch_related("items__product").select_related("user").order_by("-creado_en")[:5]
        return Response({
            "counts": counts,
            "last30d": {
                "revenue": float(revenue or 0),
                "orders": recent.count(),
                "items": sum(o.items.count() for o in recent),
            },
            "lastOrders": [serialize_order(o, request) for o in last_orders],
        })


class AdminUsersView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        page = max(1, int(request.query_params.get("page") or 1))
        limit = max(1, min(100, int(request.query_params.get("limit") or 20)))
        qs = User.objects.all().order_by("-date_joined")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q))
        total = qs.count()
        start = (page - 1) * limit
        items = qs[start:start + limit]
        data = [serialize_user(u, request) for u in items]
        return Response({"items": data, "total": total, "page": page, "pages": ceil(total / limit) if total else 1})

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        email = (request.data.get("email") or "").strip().lower()
        password = (request.data.get("password") or "").strip()
        if not name or not email or not password:
            return Response({"error": "Nombre, email y password requeridos"}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email__iexact=email).exists():
            return Response({"error": "Email ya registrado"}, status=status.HTTP_409_CONFLICT)
        try:
            validate_password(password)
        except ValidationError as exc:
            return Response({"error": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.create_user(username=email, email=email, password=password, name=name)
        return Response(serialize_user(user, request), status=status.HTTP_201_CREATED)


class AdminUserDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        if "name" in request.data:
            user.name = request.data.get("name") or user.name
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
        user.save()
        return Response(serialize_user(user, request))

    def delete(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
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
        start = (page - 1) * limit
        items = qs[start:start + limit]
        data = [serialize_order(o, request) for o in items]
        return Response({"items": data, "total": total, "page": page, "pages": ceil(total / limit) if total else 1})


class AdminOrderDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, pk):
        order = Order.objects.filter(pk=pk).first()
        if not order:
            return Response({"error": "Pedido no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        status_val = request.data.get("status")
        allowed = {"created", "approved", "paid", "shipped", "delivered", "cancelled", "draft"}
        if status_val not in allowed:
            return Response({"error": "Estado invalido"}, status=status.HTTP_400_BAD_REQUEST)
        order.status = status_val
        # Opcionalmente actualizar items si vienen en el payload
        raw_items = request.data.get("items")
        if isinstance(raw_items, list) and raw_items:
            with transaction.atomic():
                order.items.all().delete()
                built_items = []
                for raw in raw_items:
                    pid = raw.get("productId") or raw.get("product") or raw.get("id") or raw.get("slug")
                    product = resolve_product(pid)
                    qty = max(1, int(raw.get("qty") or raw.get("cantidad") or 1))
                    price = raw.get("price")
                    if price is None and product:
                        price = product.precio
                    price = Decimal(str(price or 0))
                    name = raw.get("name") or (product.nombre if product else "")
                    if not name or not product:
                        continue
                    built_items.append({"product": product, "qty": qty, "price": price})
                if built_items:
                    for it in built_items:
                        OrderItem.objects.create(
                            order=order,
                            product=it["product"],
                            cantidad=it["qty"],
                            precio_unitario=it["price"],
                        )
                    order.recalc_total()
        order.save()
        order.refresh_from_db()
        return Response(serialize_order(order, request))


class AdminProductsView(APIView):
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        page = max(1, int(request.query_params.get("page") or 1))
        limit = max(1, min(100, int(request.query_params.get("limit") or 20)))
        qs = Product.objects.select_related("categoria").order_by("-creado_en")
        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
        total = qs.count()
        start = (page - 1) * limit
        items = qs[start:start + limit]
        data = [serialize_product(p, request) for p in items]
        return Response({"items": data, "total": total, "page": page, "pages": ceil(total / limit) if total else 1})

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        price = request.data.get("price")
        if not name or price is None:
            return Response({"error": "Nombre y precio requeridos"}, status=status.HTTP_400_BAD_REQUEST)
        cat_val = request.data.get("category")
        category = resolve_category(cat_val) if cat_val else None
        product = Product(
            user=request.user,
            nombre=name,
            precio=Decimal(str(price)),
            descripcion=request.data.get("description") or "",
            categoria=category,
            stock=int(request.data.get("stock") or 0),
            activo=str(request.data.get("active") or "true").lower() in {"1", "true", "yes"},
        )
        if request.FILES.get("image"):
            product.imagen = request.FILES["image"]
        product.save()
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
        if "stock" in request.data:
            product.stock = int(request.data.get("stock") or 0)
        if "active" in request.data:
            product.activo = str(request.data.get("active")).lower() in {"1", "true", "yes"}
        if "category" in request.data:
            cat = resolve_category(request.data.get("category"))
            product.categoria = cat
        if request.FILES.get("image"):
            product.imagen = request.FILES["image"]
        product.save()
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


class OffersListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        now = timezone.now()
        offers = Offer.objects.filter(activo=True).filter(
            models.Q(empieza__isnull=True) | models.Q(empieza__lte=now),
            models.Q(termina__isnull=True) | models.Q(termina__gte=now),
        ).order_by("-porcentaje")
        data = []
        for off in offers:
            data.append({
                "id": off.id,
                "slug": off.slug,
                "name": off.nombre,
                "description": off.descripcion,
                "percent": float(off.porcentaje),
                "product": serialize_product(off.producto, request) if off.producto else None,
                "category": serialize_category(off.categoria),
                "starts": off.empieza.isoformat() if off.empieza else None,
                "ends": off.termina.isoformat() if off.termina else None,
            })
        return Response({"items": data})


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
        prod_val = request.data.get("product")
        cat_val = request.data.get("category")
        product = resolve_product(prod_val) if prod_val else None
        category = Category.objects.filter(pk=cat_val).first() if cat_val else None
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
            cat_val = request.data.get("category")
            offer.categoria = Category.objects.filter(pk=cat_val).first() if cat_val else None
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
