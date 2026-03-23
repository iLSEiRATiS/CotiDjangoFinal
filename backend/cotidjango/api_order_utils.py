from decimal import Decimal


def order_item_name(item):
    if getattr(item, "product_name", ""):
        return item.product_name
    if getattr(item, "product", None):
        return item.product.nombre
    return "Producto"


def order_item_attrs_label(attrs, prefix=" (", separator="; ", suffix=")"):
    if not isinstance(attrs, dict) or not attrs:
        return ""
    parts = []
    for key, value in attrs.items():
        if isinstance(value, list):
            value = ", ".join(str(x) for x in value)
        if value not in (None, ""):
            parts.append(f"{key}: {value}")
    if not parts:
        return ""
    return f"{prefix}{separator.join(parts)}{suffix}"


def normalize_order_item_attrs(raw_attrs):
    return raw_attrs if isinstance(raw_attrs, dict) else {}


def build_order_item_display_name(base_name, attrs):
    return f"{base_name}{order_item_attrs_label(attrs)}" if base_name else ""


def build_order_item_input(raw, resolve_product):
    product_id = raw.get("productId") or raw.get("product_id") or raw.get("product") or raw.get("id") or raw.get("slug")
    product = resolve_product(product_id)
    qty = max(1, int(raw.get("qty") or raw.get("cantidad") or 1))
    price = raw.get("price")
    if price is None and product:
        price = product.precio
    attrs = normalize_order_item_attrs(raw.get("attributes") or raw.get("atributos") or {})
    name = raw.get("name") or (product.nombre if product else "")
    name = build_order_item_display_name(name, attrs)
    return {
        "product": product,
        "qty": qty,
        "price": Decimal(str(price or 0)),
        "name": name,
        "attrs": attrs,
    }
