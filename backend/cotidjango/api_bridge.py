from datetime import timedelta
import os
import json
import unicodedata
from pathlib import Path
from urllib import request as urlrequest

from django.conf import settings
from decimal import Decimal
from math import ceil

from django.contrib.auth import authenticate, get_user_model
from django.http import HttpResponse
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction, models
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from django.core.mail import EmailMessage

from orders.models import Order, OrderItem
from products.models import Category, Product, Offer, HomeImage

User = get_user_model()


def _norm_text(value):
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


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
    if getattr(prod, "image_url", ""):
        images.append(prod.image_url)
    elif prod.imagen:
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
        "imageUrl": images[0] if images else None,
        "discount": discount["meta"] if discount else None,
        "description": prod.descripcion or "",
        "images": images,
        "attributes": prod.atributos or {},
        "attributes_stock": prod.atributos_stock or {},
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
        "pending_payment": "Falta pago",
        "paid": "Pagado",
        "shipped": "Enviado",
        "delivered": "Entregado",
        "cancelled": "Cancelado",
        "draft": "Borrador",
    }
    items = []
    for item in order.items.all():
        attrs = item.atributos or {}
        attrs_label = ""
        if isinstance(attrs, dict) and attrs:
            parts = []
            for k, v in attrs.items():
                if isinstance(v, list):
                    v = ", ".join(str(x) for x in v)
                if v not in (None, ""):
                    parts.append(f"{k}: {v}")
            if parts:
                attrs_label = f" ({'; '.join(parts)})"
        items.append({
            "productId": item.product_id,
            "name": (item.product.nombre if item.product else "") + attrs_label,
            "price": float(item.precio_unitario),
            "qty": item.cantidad,
            "subtotal": float(item.subtotal),
            "attributes": attrs,
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
        "note": order.nota or "",
        "createdAt": order.creado_en.isoformat() if order.creado_en else None,
    }


def serialize_home_image(item):
    return {
        "id": item.id,
        "key": item.key,
        "section": item.section,
        "title": item.title or "",
        "imageUrl": item.image_url,
        "targetUrl": item.target_url or "",
        "order": item.order,
        "active": item.activo,
    }


def resolve_category(value):
    if not value:
        return None
    slug = slugify(str(value))
    cat, _ = Category.objects.get_or_create(slug=slug, defaults={"nombre": value})
    return cat


def get_descendant_ids(root_id):
    if not root_id:
        return []
    cats = Category.objects.all().values("id", "parent_id")
    children = {}
    for c in cats:
        pid = c["parent_id"]
        children.setdefault(pid, []).append(c["id"])
    out = []
    stack = [root_id]
    while stack:
        current = stack.pop()
        out.append(current)
        stack.extend(children.get(current, []))
    return out


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
    # PDF minimalista: normalizamos para evitar problemas de acentos en Helvetica
    try:
        import unicodedata
        text = unicodedata.normalize("NFKD", text or "")
        text = "".join(c for c in text if not unicodedata.combining(c))
    except Exception:
        text = text or ""
    return (text or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_invoice_pdf(order) -> bytes:
    from io import BytesIO
    from decimal import Decimal
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    def _money(value):
        try:
            val = Decimal(str(value or 0))
        except Exception:
            val = Decimal("0")
        s = f"{val:,.2f}"
        # 1,234.56 -> 1.234,56
        return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")

    def _attrs_label(attrs):
        if not isinstance(attrs, dict) or not attrs:
            return ""
        parts = []
        for k, v in attrs.items():
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v)
            if v not in (None, ""):
                parts.append(f"{k}: {v}")
        return f" - {' | '.join(parts)}" if parts else ""

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(612, 792))  # Letter

    font_name = "Helvetica"
    arial_path = r"C:\Windows\Fonts\arial.ttf"
    try:
        if Path(arial_path).exists():
            pdfmetrics.registerFont(TTFont("Arial", arial_path))
            font_name = "Arial"
    except Exception:
        pass

    y = 760
    line_height = 18
    x_left = 50
    x_right = 562

    status_labels = {
        "created": "Creado",
        "approved": "Aprobado",
        "pending_payment": "Falta pago",
        "paid": "Pagado",
        "shipped": "Enviado",
        "delivered": "Entregado",
        "cancelled": "Cancelado",
        "draft": "Borrador",
    }
    payment_label = status_labels.get(order.status, order.status)
    date_label = order.creado_en.strftime("%d/%m/%Y %H:%M") if order.creado_en else ""
    address = ", ".join(filter(None, [order.direccion, order.ciudad, order.cp]))

    def _draw_page_header(current_y):
        c.setFont(font_name, 22)
        c.drawString(x_left, current_y, f"Orden: #{order.id}")
        c.setFont(font_name, 11)
        c.drawRightString(x_right, current_y + 4, "CotiStore")

        current_y -= 28
        c.setFont(font_name, 12)
        c.drawString(x_left, current_y, f"Fecha: {date_label}")
        current_y -= 16
        c.drawString(x_left, current_y, f"Pago: {payment_label}")
        current_y -= 16
        c.drawString(x_left, current_y, "Metodo de envio: Acordar envio")
        current_y -= 10
        c.line(x_left, current_y, x_right, current_y)
        current_y -= 18
        return current_y

    def _draw_customer_block(current_y):
        c.setFont(font_name, 12)
        c.drawString(x_left, current_y, f"Recibe: {order.nombre or '-'}")
        current_y -= 16
        c.drawString(x_left, current_y, f"Telefono: {order.telefono or '-'}")
        current_y -= 16
        c.drawString(x_left, current_y, f"Email: {order.email or '-'}")
        current_y -= 16
        c.drawString(x_left, current_y, f"Direccion: {address or '-'}")
        current_y -= 16
        return current_y

    col_code = 50
    col_qty = 105
    col_desc = 170
    col_unit = 455
    col_total = 530

    def _draw_table_header(current_y):
        top = current_y
        bottom = current_y - 24
        c.rect(x_left, bottom, x_right - x_left, top - bottom, stroke=1, fill=0)
        for xx in (95, 155, 440, 520):
            c.line(xx, bottom, xx, top)
        c.setFont(font_name, 11)
        c.drawString(col_code, current_y - 16, "Codigo")
        c.drawString(col_qty, current_y - 16, "Cantidad")
        c.drawString(col_desc, current_y - 16, "Descripcion")
        c.drawRightString(col_unit, current_y - 16, "P. unitario")
        c.drawRightString(col_total + 20, current_y - 16, "Total")
        return bottom

    def _draw_row(current_y, code, qty, desc, unit_price, row_total):
        row_h = 20
        bottom = current_y - row_h
        c.rect(x_left, bottom, x_right - x_left, row_h, stroke=1, fill=0)
        for xx in (95, 155, 440, 520):
            c.line(xx, bottom, xx, current_y)
        c.setFont(font_name, 10)
        c.drawString(col_code, current_y - 14, str(code))
        c.drawString(col_qty, current_y - 14, str(qty))
        c.drawString(col_desc, current_y - 14, (desc or "")[:58])
        c.drawRightString(col_unit, current_y - 14, _money(unit_price))
        c.drawRightString(col_total + 20, current_y - 14, _money(row_total))
        return bottom

    y = _draw_page_header(y)
    y = _draw_customer_block(y)
    y -= 6
    y = _draw_table_header(y)

    for item in order.items.all():
        desc = f"{item.product.nombre}{_attrs_label(item.atributos)}"
        if y < 70:
            c.showPage()
            y = 760
            y = _draw_page_header(y)
            y = _draw_customer_block(y)
            y -= 6
            y = _draw_table_header(y)
        code = item.product_id or "-"
        y = _draw_row(y, code, item.cantidad, desc, item.precio_unitario, item.subtotal)

    y -= 14
    c.setFont(font_name, 13)
    c.drawRightString(x_right, y, f"TOTAL: {_money(order.total)}")
    y -= line_height
    c.setFont(font_name, 11)
    c.drawRightString(x_right, y, f"Estado: {payment_label}")

    c.showPage()
    c.save()
    return buffer.getvalue()

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
    reply_to = os.getenv("RESEND_REPLY_TO")
    html_body = body.replace("\n", "<br>")
    if send_resend_email([order.email], subject, body, html_body=html_body, reply_to=reply_to):
        return
    email = EmailMessage(subject, body, to=[order.email])
    email.attach(f"pedido-{order.id}.pdf", pdf_bytes, "application/pdf")
    try:
        email.send(fail_silently=True)
    except Exception:
        pass


def send_resend_email(to_emails, subject, text_body, html_body=None, reply_to=None):
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("RESEND_FROM_EMAIL", "").strip() or "onboarding@resend.dev"
    if not api_key:
        return False
    if not to_emails:
        return False
    payload = {
        "from": from_email,
        "to": to_emails,
        "subject": subject or "",
        "text": text_body or "",
    }
    if html_body:
        payload["html"] = html_body
    if reply_to:
        payload["reply_to"] = reply_to
    try:
        req = urlrequest.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=15) as resp:
            status_code = getattr(resp, "status", 0) or 0
            return 200 <= status_code < 300
    except Exception:
        return False


def send_admin_order_email(order, request=None):
    admin_email = (
        os.getenv("ADMIN_ORDER_EMAIL", "").strip()
        or os.getenv("GMAIL_USER", "").strip()
        or getattr(settings, "DEFAULT_FROM_EMAIL", "")
    )
    if not admin_email:
        return

    subject = f"Nuevo pedido #{order.id} para aprobar"
    lines = [
        f"Pedido #{order.id}",
        f"Cliente: {order.nombre} - {order.email}",
        f"Total: ${order.total}",
        f"Estado: {order.status}",
        "",
        "Items:",
    ]
    for item in order.items.all():
        attrs = item.atributos or {}
        attrs_label = ""
        if isinstance(attrs, dict) and attrs:
            parts = []
            for k, v in attrs.items():
                if isinstance(v, list):
                    v = ", ".join(str(x) for x in v)
                if v not in (None, ""):
                    parts.append(f"{k}: {v}")
            if parts:
                attrs_label = f" ({'; '.join(parts)})"
        lines.append(
            f"- {item.product.nombre}{attrs_label} x{item.cantidad} @ ${item.precio_unitario:.2f} = ${item.subtotal:.2f}"
        )
    body = "\n".join(lines)
    html_body = body.replace("\n", "<br>")
    reply_to = os.getenv("RESEND_REPLY_TO")

    if send_resend_email([admin_email], subject, body, html_body=html_body, reply_to=reply_to):
        return

    email = EmailMessage(subject, body, to=[admin_email])
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


class HomeImagesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = HomeImage.objects.filter(activo=True).order_by("section", "order", "id")
        items = [serialize_home_image(x) for x in qs]
        by_key_image = {x["key"]: x["imageUrl"] for x in items}
        by_key_target = {x["key"]: x["targetUrl"] for x in items if x.get("targetUrl")}
        return Response({"items": items, "byKey": by_key_image, "byKeyTarget": by_key_target})


class ProductListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = (request.query_params.get("q") or request.query_params.get("search") or "").strip()
        category = request.query_params.get("category") or request.query_params.get("cat")
        category_id = request.query_params.get("category_id")
        include_inactive = str(request.query_params.get("all") or "").lower() in {"1", "true", "yes", "si", "s"}
        sort = (request.query_params.get("sort") or "").strip().lower()
        page = max(1, int(request.query_params.get("page") or 1))
        limit = max(1, min(100, int(request.query_params.get("limit") or 20)))

        qs = Product.objects.select_related("categoria")
        if not include_inactive:
            qs = qs.filter(activo=True)
        if q:
            # Filtro tolerante a tildes/variantes unicode para que la busqueda
            # no pierda productos por diferencias de codificacion.
            q_norm = _norm_text(q)
            base_qs = qs
            qs = qs.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
            if q_norm:
                extra_ids = [
                    p.id
                    for p in base_qs
                    if (q_norm in _norm_text(p.nombre)) or (q_norm in _norm_text(p.descripcion))
                ]
                if extra_ids:
                    qs = base_qs.filter(Q(id__in=extra_ids) | Q(nombre__icontains=q) | Q(descripcion__icontains=q))
        if category_id:
            try:
                root_id = int(category_id)
            except Exception:
                root_id = None
            if root_id:
                ids = get_descendant_ids(root_id)
                qs = qs.filter(categoria_id__in=ids)
        elif category:
            root = Category.objects.filter(slug=category).first()
            if not root:
                wanted = _norm_text(category).replace("-", " ")
                for c in Category.objects.all().only("id", "nombre", "slug"):
                    name_norm = _norm_text(c.nombre)
                    slug_norm = _norm_text(c.slug).replace("-", " ")
                    if wanted in {name_norm, slug_norm}:
                        root = c
                        break
            if root:
                ids = get_descendant_ids(root.id)
                qs = qs.filter(categoria_id__in=ids)

        if sort in {"mas_vendidos", "relevancia"}:
            qs = qs.annotate(sold=Coalesce(Sum("order_items__cantidad"), 0)).order_by("-sold", "-creado_en")
        elif sort == "precio_asc":
            qs = qs.order_by("precio")
        elif sort == "precio_desc":
            qs = qs.order_by("-precio")
        elif sort == "nombre_asc":
            qs = qs.order_by("nombre")
        elif sort == "nombre_desc":
            qs = qs.order_by("-nombre")
        else:
            qs = qs.order_by("-creado_en")

        total = qs.count()
        start = (page - 1) * limit
        items = qs[start:start + limit]
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
        note = (request.data.get("note") or request.data.get("nota") or "").strip()
        if len(note) > 1000:
            note = note[:1000]
        if not isinstance(shipping, dict):
            shipping = {}

        # Validacion de datos del cliente
        email = shipping.get('email') or request.user.email or ''
        phone = shipping.get('phone') or request.user.phone or ''
        missing = []
        if not (shipping.get('name') or request.user.name or request.user.username):
            missing.append('nombre')
        if not email:
            missing.append('email')
        if not phone:
            missing.append('telefono')
        if not shipping.get('address'):
            missing.append('direccion')
        if not shipping.get('city'):
            missing.append('ciudad')
        if not shipping.get('zip'):
            missing.append('cp')
        if missing:
            return Response({"error": f"Faltan datos obligatorios: {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)
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
            raw_attrs = raw.get("attributes") or raw.get("atributos") or {}
            attrs = raw_attrs if isinstance(raw_attrs, dict) else {}
            name = raw.get("name") or (product.nombre if product else "")
            if attrs:
                parts = []
                for k, v in attrs.items():
                    if isinstance(v, list):
                        v = ", ".join(str(x) for x in v)
                    if v not in (None, ""):
                        parts.append(f"{k}: {v}")
                if parts:
                    name = f"{name} ({'; '.join(parts)})"
            if not name:
                continue
            built_items.append({"product": product, "qty": qty, "price": price, "name": name, "attrs": attrs})

        if not built_items:
            return Response({"error": "Carrito vacio"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                nombre=shipping.get("name") or request.user.name or request.user.username,
                email=shipping.get("email") or request.user.email or "",
                direccion=shipping.get("address") or "",
                ciudad=shipping.get("city") or "",
                estado="",
                cp=shipping.get("zip") or "",
                telefono=shipping.get("phone") or request.user.phone or "",
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
        try:
            send_invoice_email(order, request)
        except Exception:
            pass
        return Response({"order": serialize_order(order, request)})


class AdminOverviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        counts = {
            "users": User.objects.count(),
            "products": Product.objects.filter(activo=True).count(),
            "orders": Order.objects.count(),
        }
        since = timezone.now() - timedelta(days=30)
        paid_states = ["paid", "shipped", "delivered"]
        recent = Order.objects.filter(creado_en__gte=since, status__in=paid_states)
        revenue = recent.aggregate(total=Sum("total")).get("total") or Decimal("0.00")
        last_orders = Order.objects.prefetch_related("items__product").select_related("user").order_by("-creado_en")[:5]
        pending_orders = Order.objects.filter(status="created").prefetch_related("items__product").select_related("user").order_by("-creado_en")[:5]
        recent_users = User.objects.order_by("-date_joined")[:5]
        return Response({
            "counts": counts,
            "last30d": {
                "revenue": float(revenue or 0),
                "orders": recent.count(),
                "items": sum(o.items.count() for o in recent),
            },
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
        allowed = {"created", "approved", "pending_payment", "paid", "shipped", "delivered", "cancelled", "draft"}
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
                    raw_attrs = raw.get("attributes") or raw.get("atributos") or {}
                    attrs = raw_attrs if isinstance(raw_attrs, dict) else {}
                    name = raw.get("name") or (product.nombre if product else "")
                    if attrs:
                        parts = []
                        for k, v in attrs.items():
                            if isinstance(v, list):
                                v = ", ".join(str(x) for x in v)
                            if v not in (None, ""):
                                parts.append(f"{k}: {v}")
                        if parts:
                            name = f"{name} ({'; '.join(parts)})"
                    if not name or not product:
                        continue
                    built_items.append({"product": product, "qty": qty, "price": price, "attrs": attrs})
                if built_items:
                    for it in built_items:
                        OrderItem.objects.create(
                            order=order,
                            product=it["product"],
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
        order = Order.objects.prefetch_related("items__product").select_related("user").filter(pk=pk).first()
        if not order:
            return Response({"error": "Pedido no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        pdf_bytes = build_invoice_pdf(order)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="pedido-{order.id}.pdf"'
        return resp


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
        image_url = request.data.get("imageUrl") or request.data.get("image_url") or ""
        product = Product(
            user=request.user,
            nombre=name,
            precio=Decimal(str(price)),
            descripcion=request.data.get("description") or "",
            categoria=category,
            stock=int(request.data.get("stock") or 0),
            activo=str(request.data.get("active") or "true").lower() in {"1", "true", "yes"},
        )
        if image_url:
            product.image_url = str(image_url).strip()
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
        if "imageUrl" in request.data or "image_url" in request.data:
            product.image_url = str(request.data.get("imageUrl") or request.data.get("image_url") or "").strip()
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
