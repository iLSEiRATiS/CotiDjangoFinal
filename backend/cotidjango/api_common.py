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
from .api_pdf import build_invoice_pdf, build_shipping_label_pdf

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
    display_name = user.get_display_name() if hasattr(user, "get_display_name") else (user.name or user.username)
    missing_profile_fields = user.get_missing_profile_fields() if hasattr(user, "get_missing_profile_fields") else []
    shipping_quote_amount = getattr(user, "shipping_quote_amount", None)
    shipping_quote_note = str(getattr(user, "shipping_quote_note", "") or "").strip()
    shipping_quote_updated_at = getattr(user, "shipping_quote_updated_at", None)
    return {
        "_id": str(user.id),
        "id": user.id,
        "name": display_name,
        "firstName": str(user.first_name or "").strip(),
        "lastName": str(user.last_name or "").strip(),
        "documentNumber": str(getattr(user, "document_number", "") or "").strip(),
        "email": user.email,
        "role": user.role,
        "missingProfileFields": missing_profile_fields,
        "profileCompletionRequired": bool(missing_profile_fields),
        "profile": {
            "phone": user.phone or "",
            "documentNumber": str(getattr(user, "document_number", "") or "").strip(),
            "avatar": _abs_media(request, user.avatar.url) if (request and user.avatar) else None,
        },
        "shipping": {
            "name": display_name,
            "address": user.address or "",
            "city": user.city or "",
            "zip": user.zip_code or "",
            "phone": user.phone or "",
        },
        "shippingQuote": {
            "amount": float(shipping_quote_amount) if shipping_quote_amount is not None else None,
            "note": shipping_quote_note,
            "updatedAt": shipping_quote_updated_at.isoformat() if shipping_quote_updated_at else None,
            "available": shipping_quote_amount is not None or bool(shipping_quote_note),
        },
        "createdAt": user.date_joined.isoformat() if user.date_joined else None,
        "updatedAt": user.last_login.isoformat() if user.last_login else None,
    }


def serialize_category(cat):
    if not cat:
        return None
    path = build_category_path(cat)
    return {
        "_id": cat.id,
        "id": cat.id,
        "name": cat.nombre,
        "slug": cat.slug,
        "path": [node.nombre for node in path],
        "pathName": build_category_path_name(cat),
        "pathSlug": build_category_path_slug(cat),
    }


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
        "videoUrl": prod.video_url or "",
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
        "shipping": float(getattr(order, "envio", 0) or 0),
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


def build_category_path(category):
    path = []
    current = category
    seen = set()
    while current and getattr(current, "id", None) and current.id not in seen:
        seen.add(current.id)
        path.append(current)
        current = getattr(current, "parent", None)
    return list(reversed(path))


def build_category_path_name(category):
    return " > ".join(cat.nombre for cat in build_category_path(category))


def build_category_path_slug(category):
    return "/".join((cat.slug or slugify(cat.nombre or "")).strip("/") for cat in build_category_path(category) if cat)


def _category_matches_segment(category, segment):
    wanted = _norm_text(segment)
    if not wanted:
        return False
    return (
        wanted == _norm_text(category.slug)
        or wanted == _norm_text(category.nombre)
        or wanted == _norm_text(slugify(category.nombre or ""))
    )


def resolve_category_reference(value):
    raw = str(value or "").strip().strip("/")
    if not raw:
        return None

    segments = [segment.strip() for segment in raw.split("/") if segment.strip()]
    if len(segments) > 1:
        current = None
        for segment in segments:
            queryset = Category.objects.filter(parent=current)
            matches = [cat for cat in queryset if _category_matches_segment(cat, segment)]
            if len(matches) != 1:
                current = None
                break
            current = matches[0]
        if current:
            return current

    exact_slug_matches = [cat for cat in Category.objects.all().only("id", "nombre", "slug", "parent_id") if _norm_text(cat.slug) == _norm_text(raw)]
    if len(exact_slug_matches) == 1:
        return exact_slug_matches[0]

    exact_name_matches = [cat for cat in Category.objects.all().only("id", "nombre", "slug", "parent_id") if _norm_text(cat.nombre) == _norm_text(raw)]
    if len(exact_name_matches) == 1:
        return exact_name_matches[0]

    exact_slugified_name_matches = [
        cat
        for cat in Category.objects.all().only("id", "nombre", "slug", "parent_id")
        if _norm_text(slugify(cat.nombre or "")) == _norm_text(raw)
    ]
    if len(exact_slugified_name_matches) == 1:
        return exact_slugified_name_matches[0]

    return None


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


def get_ancestor_ids(category):
    out = []
    current = category
    seen = set()
    while current and getattr(current, "id", None) and current.id not in seen:
        seen.add(current.id)
        out.append(current.id)
        current = getattr(current, "parent", None)
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
    xlsx_slug = f"xlsx-offer-product-{product.pk}"
    category_ids = get_ancestor_ids(getattr(product, "categoria", None))

    active_window = (
        models.Q(empieza__isnull=True) | models.Q(empieza__lte=now),
        models.Q(termina__isnull=True) | models.Q(termina__gte=now),
    )

    xlsx_offer = Offer.objects.filter(
        activo=True,
        producto=product,
        slug=xlsx_slug,
    ).filter(*active_window).first()

    if xlsx_offer:
        offer = xlsx_offer
    else:
        category_offer = None
        if category_ids:
            category_offer = Offer.objects.filter(
                activo=True,
                categoria_id__in=category_ids,
            ).filter(*active_window).order_by("-porcentaje").first()
        offer = category_offer

    if not offer:
        return None
    base_price = product.precio if isinstance(product.precio, Decimal) else Decimal(str(product.precio or "0"))
    pct = offer.porcentaje if isinstance(offer.porcentaje, Decimal) else Decimal(str(offer.porcentaje or "0"))
    exact_offer_price = getattr(offer, "precio_oferta", None)
    if exact_offer_price is not None:
        exact_offer_price = exact_offer_price if isinstance(exact_offer_price, Decimal) else Decimal(str(exact_offer_price))
    if exact_offer_price is not None and exact_offer_price > 0:
        final_price = exact_offer_price
        if base_price > 0:
            pct = ((base_price - final_price) / base_price) * Decimal("100")
            pct = pct.quantize(Decimal("0.01"))
    else:
        final_price = base_price * (Decimal("1.00") - (pct / Decimal("100")))
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
