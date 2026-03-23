from datetime import timedelta
import json
import hashlib
import secrets
import unicodedata
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

from orders.models import Order, OrderItem
from products.models import Category, Product, ProductImage, Offer, HomeImage, HomeMarquee, SupplierContact
from users.models import PasswordResetToken
from .api_mail import send_admin_order_email, send_invoice_email, send_password_reset_email, send_resend_email
from .api_order_utils import order_item_attrs_label as _order_item_attrs_label
from .api_order_utils import order_item_name as _order_item_name
from .api_pdf import build_invoice_pdf

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


def _verify_turnstile(token, remote_ip=""):
    secret = getattr(settings, "TURNSTILE_SECRET_KEY", "").strip()
    if not secret:
        return True
    if not token:
        return False
    payload = json.dumps({
        "secret": secret,
        "response": token,
        "remoteip": remote_ip or "",
    }).encode("utf-8")
    req = urlrequest.Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return bool(data.get("success"))
    except Exception:
        return False


def _collect_product_images(prod, request=None):
    out = []
    seen = set()

    def append(url):
        value = str(url or "").strip()
        if not value or value in seen:
            return
        seen.add(value)
        out.append(value)

    append(getattr(prod, "image_url", ""))
    if getattr(prod, "imagen", None):
        try:
            append(_abs_media(request, prod.imagen.url))
        except Exception:
            pass

    extra_images = getattr(prod, "extra_images", None)
    if extra_images is not None:
        iterable = extra_images.all()
    else:
        iterable = ProductImage.objects.filter(product=prod)
    for img in iterable:
        if not getattr(img, "activo", True):
            continue
        append(getattr(img, "image_url", ""))
        if getattr(img, "image", None):
            try:
                append(_abs_media(request, img.image.url))
            except Exception:
                pass
    return out


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
    images = _collect_product_images(prod, request)
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
        "attributes_price": prod.atributos_precio or {},
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
        attrs_label = _order_item_attrs_label(attrs)
        items.append({
            "productId": item.product_id,
            "name": _order_item_name(item) + attrs_label,
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


def serialize_home_marquee(item):
    if not item:
        return {
            "enabled": False,
            "text": "",
            "textColor": "#ffffff",
            "backgroundColor": "#dc3545",
        }
    return {
        "enabled": bool(item.activo and item.text),
        "text": item.text or "",
        "textColor": item.text_color or "#ffffff",
        "backgroundColor": item.background_color or "#dc3545",
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


def parse_image_urls_payload(raw_value):
    if raw_value in (None, ""):
        return []
    items = raw_value if isinstance(raw_value, list) else [raw_value]
    out = []
    seen = set()
    for item in items:
        if isinstance(item, str):
            parts = [item]
            for sep in ["|", ";", ","]:
                if sep in item:
                    parts = [x.strip() for x in item.split(sep)]
                    break
            for part in parts:
                url = str(part or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                out.append(url)
    return out


def sync_product_images(product: Product, image_urls):
    urls = [str(u or "").strip() for u in (image_urls or []) if str(u or "").strip()]
    if urls:
        product.image_url = urls[0]
    extra_urls = urls[1:]
    existing = {x.image_url: x for x in ProductImage.objects.filter(product=product)}
    keep = set()
    for idx, url in enumerate(extra_urls, start=1):
        keep.add(url)
        row = existing.get(url)
        if row:
            changed = False
            if row.order != idx:
                row.order = idx
                changed = True
            if not row.activo:
                row.activo = True
                changed = True
            if changed:
                row.save(update_fields=["order", "activo"])
        else:
            ProductImage.objects.create(product=product, image_url=url, order=idx, activo=True)
    ProductImage.objects.filter(product=product).exclude(image_url__in=keep).delete()


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


def _reset_token_hash(raw_token: str) -> str:
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()
