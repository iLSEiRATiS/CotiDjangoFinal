import os
from pathlib import Path

from django.conf import settings

from .api_order_utils import order_item_attrs_label, order_item_name


def _invoice_logo_path():
    explicit_logo = getattr(settings, "INVOICE_LOGO_PATH", "") or os.getenv("INVOICE_LOGO_PATH", "")
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    candidates = []
    if explicit_logo:
        candidates.append(Path(explicit_logo))
    candidates.extend([
        base_dir / "media" / "avatars" / "logo-coti.png",
        base_dir / "media" / "avatars" / "logo-coti.webp",
        base_dir / "static" / "logo-coti.png",
        base_dir / "static" / "logo-coti.webp",
        base_dir / "static" / "logo-coti.png",
        base_dir / "static" / "logo.png",
        base_dir.parent / "DjangoFrontCoti" / "src" / "assets" / "logo-coti-optimized.webp",
        base_dir.parent / "DjangoFrontCoti" / "src" / "assets" / "logo-coti.png",
        base_dir.parent / "DjangoFrontCoti" / "public" / "logo-coti.png",
        base_dir.parent / "frontend" / "src" / "assets" / "logo-coti.png",
    ])
    return next((path for path in candidates if path.exists()), None)


def build_invoice_pdf(order) -> bytes:
    from io import BytesIO
    from decimal import Decimal

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    def _money(value):
        try:
            val = Decimal(str(value or 0))
        except Exception:
            val = Decimal("0")
        s = f"{val:,.2f}"
        return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")

    def _attrs_label(attrs):
        return order_item_attrs_label(attrs, prefix=" - ", separator=" | ", suffix="")

    def _safe(txt, fallback="-"):
        s = str(txt or "").strip()
        return s if s else fallback

    def _wrap_text(text, max_width, font_name, font_size):
        content = str(text or "").strip()
        if not content:
            return [""]
        words = content.split()
        if not words:
            return [content]

        lines = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    buffer = BytesIO()
    width, height = A4
    canvas_obj = canvas.Canvas(buffer, pagesize=A4)

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    font_notice = "Times-BoldItalic"
    try:
        arial = r"C:\Windows\Fonts\arial.ttf"
        arial_bold = r"C:\Windows\Fonts\arialbd.ttf"
        georgia_bold_italic = r"C:\Windows\Fonts\georgiaz.ttf"
        if Path(arial).exists():
            pdfmetrics.registerFont(TTFont("Arial", arial))
            font_regular = "Arial"
        if Path(arial_bold).exists():
            pdfmetrics.registerFont(TTFont("Arial-Bold", arial_bold))
            font_bold = "Arial-Bold"
        if Path(georgia_bold_italic).exists():
            pdfmetrics.registerFont(TTFont("Georgia-BoldItalic", georgia_bold_italic))
            font_notice = "Georgia-BoldItalic"
    except Exception:
        pass

    def stroke_light():
        canvas_obj.setLineWidth(0.6)
        canvas_obj.setStrokeColorRGB(0.7, 0.7, 0.7)

    def text_dark():
        canvas_obj.setFillColorRGB(0.1, 0.1, 0.1)

    margin_l = 36
    margin_r = 36
    x_left = margin_l
    x_right = width - margin_r
    footer_y = 34
    footer_reserved_space = 78
    logo_width = 180
    logo_height = 58
    logo_top_margin = 8

    date_label = order.creado_en.strftime("%d/%m/%y %H:%M") if order.creado_en else ""
    status_to_pago = {
        "created": "Acordar (Pendiente)",
        "approved": "Acordar (Pendiente)",
        "pending_payment": "Acordar (Pendiente)",
        "paid": "Pagado",
        "shipped": "Enviado",
        "delivered": "Entregado",
        "cancelled": "Cancelado",
        "draft": "Borrador",
    }
    pago_label = status_to_pago.get(order.status, order.status)
    address = ", ".join(filter(None, [order.direccion, order.ciudad, order.cp]))
    logo_path = _invoice_logo_path()

    def draw_logo():
        if not logo_path:
            return
        try:
            img = ImageReader(str(logo_path))
            canvas_obj.drawImage(
                img,
                x_right - logo_width,
                height - logo_top_margin - logo_height,
                width=logo_width,
                height=logo_height,
                mask="auto",
                preserveAspectRatio=True,
            )
        except Exception:
            pass

    def draw_footer():
        text_dark()
        canvas_obj.setFont(font_regular, 8)
        canvas_obj.drawCentredString(
            width / 2,
            footer_y,
            "Los reclamos deberán hacerse dentro de las 48 horas recibido el pedido",
        )

    def header(y):
        text_dark()
        draw_logo()

        canvas_obj.setFont(font_bold, 14)
        canvas_obj.drawString(x_left, y, f"Orden: #{order.id}")

        y -= 16
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left, y, f"Fecha: {date_label}")

        y -= 12
        canvas_obj.drawString(x_left, y, f"Pago: {pago_label}")

        y -= 14
        canvas_obj.drawString(x_left, y, "Método de envío: Acordar envío")

        divider_y = y - 10
        if logo_path:
            divider_y = min(divider_y, height - logo_top_margin - logo_height - 12)
        stroke_light()
        canvas_obj.line(x_left, divider_y, x_right, divider_y)
        return divider_y - 16

    def customer(y):
        canvas_obj.setFont(font_bold, 9.5)
        canvas_obj.drawString(x_left, y, "Recibe:")
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left + 45, y, _safe(order.nombre))

        y -= 12
        canvas_obj.setFont(font_bold, 9.5)
        canvas_obj.drawString(x_left, y, "Teléfono:")
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left + 55, y, _safe(order.telefono))

        y -= 12
        canvas_obj.setFont(font_bold, 9.5)
        canvas_obj.drawString(x_left, y, "Email:")
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left + 38, y, _safe(order.email))

        y -= 12
        canvas_obj.setFont(font_bold, 9.5)
        canvas_obj.drawString(x_left, y, "Dirección:")
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left + 55, y, _safe(address))

        return y - 10

    col_code = x_left
    col_qty = x_left + 55
    col_desc = x_left + 110
    v1 = x_left + 48
    v2 = x_left + 102
    v3 = x_right - 140
    v4 = x_right - 70

    def table_header(y):
        row_h = 22
        stroke_light()
        canvas_obj.rect(x_left, y - row_h, x_right - x_left, row_h)
        for v in (v1, v2, v3, v4):
            canvas_obj.line(v, y - row_h, v, y)

        canvas_obj.setFont(font_bold, 9.2)
        text_dark()
        canvas_obj.drawString(col_code + 2, y - 15, "Código")
        canvas_obj.drawString(col_qty + 2, y - 15, "Cantidad")
        canvas_obj.drawString(col_desc + 2, y - 15, "Descripción")
        canvas_obj.drawRightString(v4 - 6, y - 15, "P. unitario")
        canvas_obj.drawRightString(x_right - 6, y - 15, "Total")
        return y - row_h

    def table_row(y, code, qty, desc, unit, total):
        font_size = 9
        line_height = 10
        desc_max_width = v3 - col_desc - 6
        desc_lines = _wrap_text(desc, desc_max_width, font_regular, font_size)
        row_h = max(18, 8 + len(desc_lines) * line_height)
        stroke_light()
        canvas_obj.rect(x_left, y - row_h, x_right - x_left, row_h)
        for v in (v1, v2, v3, v4):
            canvas_obj.line(v, y - row_h, v, y)

        canvas_obj.setFont(font_regular, font_size)
        text_dark()
        canvas_obj.drawString(col_code + 2, y - 13, str(code))
        canvas_obj.drawString(col_qty + 2, y - 13, str(qty))
        for idx, line in enumerate(desc_lines):
            canvas_obj.drawString(col_desc + 2, y - 13 - (idx * line_height), line)

        canvas_obj.drawRightString(v4 - 6, y - 13, _money(unit))
        canvas_obj.drawRightString(x_right - 6, y - 13, _money(total))
        return y - row_h

    y = height - 40
    y = header(y)
    y = customer(y)
    y = table_header(y)

    for item in order.items.all():
        desc = f"{order_item_name(item)}{_attrs_label(item.atributos)}"
        desc_lines = _wrap_text(desc, v3 - col_desc - 6, font_regular, 9)
        row_h = max(18, 8 + len(desc_lines) * 10)
        if y < footer_reserved_space + row_h:
            canvas_obj.showPage()
            y = height - 40
            y = header(y)
            y = customer(y)
            y = table_header(y)

        y = table_row(y, item.product_id or "-", item.cantidad, desc, item.precio_unitario, item.subtotal)

    y -= 14
    canvas_obj.setFont(font_bold, 11)
    if getattr(order, "envio", None):
        canvas_obj.drawRightString(x_right, y, f"ENVIO: {_money(order.envio)}")
        y -= 14
    canvas_obj.drawRightString(x_right, y, f"TOTAL: {_money(order.total)}")
    note = str(getattr(order, "nota", "") or "").strip()
    if note:
        note_lines = _wrap_text(note, x_right - x_left, font_regular, 9)
        note_block_height = 18 + (len(note_lines) * 10)
        if y - 20 - note_block_height < footer_reserved_space:
            canvas_obj.showPage()
            y = height - 40
            y = header(y)
        y -= 24
        canvas_obj.setFont(font_bold, 9.5)
        canvas_obj.drawString(x_left, y, "Nota:")
        y -= 12
        canvas_obj.setFont(font_regular, 9)
        for line in note_lines:
            canvas_obj.drawString(x_left, y, line)
            y -= 10

    if y < footer_reserved_space:
        canvas_obj.showPage()
        y = height - 40
        y = header(y)
    draw_footer()

    canvas_obj.save()
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Shipping labels (rótulos de envío) – Via Cargo style
# ---------------------------------------------------------------------------

# Label sizes in mm  (width, height)
LABEL_SIZES = {
    "thermal": (100, 150),   # Térmica estándar 100×150mm
    "courier":  (100, 190),   # Correo Argentino / Andreani 100×190mm
    "a4":       (105, 148.5), # Cuarto de A4 (A6) — 4 por hoja
}


def _get_sender_defaults():
    return {
        "name":     os.getenv("LABEL_SENDER_NAME", "CotiStore"),
        "email":    os.getenv("LABEL_SENDER_EMAIL", ""),
        "address":  os.getenv("LABEL_SENDER_ADDRESS", "Avenida Rivadavia 13770"),
        "city":     os.getenv("LABEL_SENDER_CITY", "Ramos Mejía"),
        "province": os.getenv("LABEL_SENDER_PROVINCE", "Buenos Aires, Argentina"),
        "zip":      os.getenv("LABEL_SENDER_ZIP", "B1704ERV"),
        "phone":    os.getenv("LABEL_SENDER_PHONE", "(011) 4654-0085"),
        "cuil":     os.getenv("LABEL_SENDER_CUIL", ""),
    }


def build_shipping_label_pdf(order, label_size="thermal", num_bultos=1) -> bytes:
    """Generate a PDF with *num_bultos* shipping labels for *order*.

    label_size: 'thermal' | 'courier' | 'a4'
    num_bultos: number of packages (each gets its own label page).
    """
    from io import BytesIO
    from datetime import datetime

    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    sender = _get_sender_defaults()
    size_key = label_size if label_size in LABEL_SIZES else "thermal"
    lw_mm, lh_mm = LABEL_SIZES[size_key]

    # For A4 mode we tile 4 labels on a single A4 page (2 cols × 2 rows)
    is_a4 = size_key == "a4"
    if is_a4:
        page_w, page_h = A4  # 595 × 842 pt
    else:
        page_w = lw_mm * mm
        page_h = lh_mm * mm

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))

    # ── Fonts ──────────────────────────────────────────────────────────────
    font_r = "Helvetica"
    font_b = "Helvetica-Bold"
    try:
        arial = r"C:\Windows\Fonts\arial.ttf"
        arial_bold = r"C:\Windows\Fonts\arialbd.ttf"
        if Path(arial).exists():
            pdfmetrics.registerFont(TTFont("Arial", arial))
            font_r = "Arial"
        if Path(arial_bold).exists():
            pdfmetrics.registerFont(TTFont("Arial-Bold", arial_bold))
            font_b = "Arial-Bold"
    except Exception:
        pass

    # ── Helpers ────────────────────────────────────────────────────────────
    def _safe(val, fb="-"):
        s = str(val or "").strip()
        return s if s else fb

    date_str = datetime.now().strftime("%d/%m/%Y")
    order_id_str = str(order.id)
    dest_name = _safe(order.nombre)
    dest_email = _safe(order.email)
    dest_address = _safe(order.direccion)
    dest_city = _safe(order.ciudad)
    dest_cp = _safe(order.cp)
    dest_province = _safe(order.estado, "")
    dest_phone = _safe(order.telefono)
    dest_document = _safe(getattr(order, "destinatario_documento", ""))
    sender_name = _safe(getattr(order, "remitente_nombre", "") or sender["name"])
    sender_email = _safe(getattr(order, "remitente_email", "") or sender.get("email", ""))
    sender_phone = _safe(getattr(order, "remitente_telefono", "") or sender["phone"])
    sender_document = _safe(getattr(order, "remitente_documento", "") or sender.get("cuil", ""))

    # ── Draw one label at offset (ox, oy) ─────────────────────────────────
    def draw_label(ox, oy, lw, lh, bulto_num, total_bultos):
        """Draw a single label. (ox, oy) is bottom-left corner in points."""
        pad = 4 * mm
        inner_w = lw - 2 * pad
        x = ox + pad
        top = oy + lh - pad
        y = top

        # — Outer border —
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(1.2)
        c.rect(ox + 1.5 * mm, oy + 1.5 * mm, lw - 3 * mm, lh - 3 * mm)

        # — Title bar —
        bar_h = 7 * mm
        c.setFillColorRGB(0.12, 0.12, 0.12)
        c.rect(ox + 1.5 * mm, top - bar_h, lw - 3 * mm, bar_h, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(font_b, 11)
        c.drawCentredString(ox + lw / 2, top - bar_h + 2.2 * mm, "RÓTULO DE ENVÍO — VIA CARGO")
        y = top - bar_h - 3 * mm

        c.setFillColorRGB(0, 0, 0)

        # — DESTINATARIO section —
        section_font = 9
        label_font = 8
        value_font = 9.5

        c.setFont(font_b, 10)
        c.drawString(x, y, "DESTINATARIO:")
        y -= 4.2 * mm

        def field(label_text, value, y_pos, indent=0):
            c.setFont(font_b, label_font)
            c.drawString(x + indent, y_pos, label_text)
            label_w = c.stringWidth(label_text, font_b, label_font) + 2
            c.setFont(font_r, value_font)
            c.drawString(x + indent + label_w, y_pos, _safe(value))
            return y_pos - 3.8 * mm

        y = field("Nombre: ", dest_name, y)
        y = field("DNI/CUIL: ", dest_document, y)
        y = field("Dirección: ", dest_address, y)

        # Localidad + CP on same line
        c.setFont(font_b, label_font)
        c.drawString(x, y, "Localidad: ")
        lw1 = c.stringWidth("Localidad: ", font_b, label_font) + 2
        c.setFont(font_r, value_font)
        c.drawString(x + lw1, y, dest_city)
        city_end = x + lw1 + c.stringWidth(dest_city, font_r, value_font) + 6 * mm
        c.setFont(font_b, label_font)
        c.drawString(city_end, y, "CP: ")
        cp_lw = c.stringWidth("CP: ", font_b, label_font) + 2
        c.setFont(font_r, value_font)
        c.drawString(city_end + cp_lw, y, dest_cp)
        y -= 3.8 * mm

        if dest_province:
            y = field("Provincia: ", dest_province, y)
        y = field("Teléfono: ", dest_phone, y)
        y = field("E-mail: ", dest_email, y)

        # — Divider —
        y -= 1.5 * mm
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.setLineWidth(0.6)
        c.line(ox + 3 * mm, y, ox + lw - 3 * mm, y)
        y -= 4 * mm

        # — REMITENTE section —
        c.setFont(font_b, 10)
        c.drawString(x, y, "REMITENTE:")
        y -= 4.2 * mm

        y = field("", sender_name, y)
        if sender.get("address"):
            y = field("", sender["address"], y)
        city_prov = ", ".join(filter(None, [sender["city"], sender["province"]]))
        if city_prov:
            y = field("", city_prov, y)
        if sender.get("zip"):
            y = field("CP: ", sender["zip"], y)
        if sender_phone and sender_phone != "-":
            y = field("Tel: ", sender_phone, y)
        if sender_email and sender_email != "-":
            y = field("E-mail: ", sender_email, y)
        if sender_document and sender_document != "-":
            y = field("DNI/CUIL: ", sender_document, y)

        # — Divider —
        y -= 1.5 * mm
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.line(ox + 3 * mm, y, ox + lw - 3 * mm, y)
        y -= 4 * mm

        # — Pedido + Fecha —
        c.setFont(font_b, 10)
        c.drawString(x, y, f"Pedido: #{order_id_str}")
        c.setFont(font_r, 9)
        c.drawRightString(ox + lw - pad, y, f"Fecha: {date_str}")
        y -= 5 * mm

        # — Pedido visible, sin código de barras —
        c.setFont(font_b, 12)
        c.drawCentredString(ox + lw / 2, y - 4 * mm, f"Pedido #{order_id_str}")
        y -= 10 * mm

        # — BULTOS section —
        y -= 2 * mm
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.line(ox + 3 * mm, y, ox + lw - 3 * mm, y)
        y -= 6 * mm

        bulto_text = f"BULTO  {bulto_num}  de  {total_bultos}"
        c.setFont(font_b, 16)
        c.drawCentredString(ox + lw / 2, y, bulto_text)

    # ── Generate pages ────────────────────────────────────────────────────
    if is_a4:
        # Tile 4 labels per A4 page
        label_w = lw_mm * mm
        label_h = lh_mm * mm
        # margins to center the 2×2 grid
        margin_x = (page_w - 2 * label_w) / 2
        margin_y = (page_h - 2 * label_h) / 2
        positions = [
            (margin_x,             margin_y + label_h),   # top-left
            (margin_x + label_w,   margin_y + label_h),   # top-right
            (margin_x,             margin_y),              # bottom-left
            (margin_x + label_w,   margin_y),              # bottom-right
        ]
        slot = 0
        for bulto in range(1, num_bultos + 1):
            if slot >= 4:
                c.showPage()
                slot = 0
            ox, oy = positions[slot]
            draw_label(ox, oy, label_w, label_h, bulto, num_bultos)
            slot += 1
    else:
        label_w = page_w
        label_h = page_h
        for bulto in range(1, num_bultos + 1):
            draw_label(0, 0, label_w, label_h, bulto, num_bultos)
            if bulto < num_bultos:
                c.showPage()

    c.save()
    return buffer.getvalue()


def build_shipping_label_pdf(order, label_size="thermal", num_bultos=1) -> bytes:
    """Rótulo 2.1: compacto, sin barcode y orientado a despacho interno."""
    from io import BytesIO
    from datetime import datetime

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    sender = _get_sender_defaults()
    size_key = label_size if label_size in LABEL_SIZES else "thermal"
    lw_mm, lh_mm = LABEL_SIZES[size_key]
    is_a4 = size_key == "a4"

    if is_a4:
        page_w, page_h = A4
    else:
        page_w = lw_mm * mm
        page_h = lh_mm * mm

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))

    font_r = "Helvetica"
    font_b = "Helvetica-Bold"
    try:
        arial = r"C:\Windows\Fonts\arial.ttf"
        arial_bold = r"C:\Windows\Fonts\arialbd.ttf"
        if Path(arial).exists():
            pdfmetrics.registerFont(TTFont("Arial", arial))
            font_r = "Arial"
        if Path(arial_bold).exists():
            pdfmetrics.registerFont(TTFont("Arial-Bold", arial_bold))
            font_b = "Arial-Bold"
    except Exception:
        pass

    def _safe(val, fb="-"):
        s = str(val or "").strip()
        return s if s else fb

    def _join(parts):
        return " - ".join([part for part in parts if part and part != "-"])

    date_str = datetime.now().strftime("%d/%m/%Y")
    order_id_str = str(order.id or "")

    dest_name = _safe(order.nombre)
    dest_document = _safe(getattr(order, "destinatario_documento", ""))
    dest_address = _safe(order.direccion)
    dest_city_line = _join([
        _safe(order.ciudad, ""),
        _safe(order.estado, ""),
        f"CP {order.cp}" if str(getattr(order, "cp", "") or "").strip() else "",
    ])
    dest_phone = _safe(order.telefono)
    dest_email = _safe(order.email)

    sender_name = _safe(getattr(order, "remitente_nombre", "") or sender.get("name", ""))
    sender_document = _safe(getattr(order, "remitente_documento", "") or sender.get("cuil", ""))
    sender_address = _safe(sender.get("address", ""), "")
    sender_city_line = _join([
        _safe(sender.get("city", ""), ""),
        _safe(sender.get("province", ""), ""),
        f"CP {sender.get('zip', '').strip()}" if str(sender.get("zip", "") or "").strip() else "",
    ])
    sender_phone = _safe(getattr(order, "remitente_telefono", "") or sender.get("phone", ""))
    sender_email = _safe(getattr(order, "remitente_email", "") or sender.get("email", ""))

    def draw_label(ox, oy, lw, lh, bulto_num, total_bultos):
        pad = 5 * mm
        x = ox + pad
        top = oy + lh - pad
        y = top

        c.setStrokeColorRGB(0, 0, 0)
        c.setFillColorRGB(0, 0, 0)
        c.setLineWidth(1.0)
        c.rect(ox + 2 * mm, oy + 2 * mm, lw - 4 * mm, lh - 4 * mm)

        compact = lh <= (160 * mm)
        meta_font = 8 if compact else 9
        section_font = 13 if compact else 15
        label_font = 6.8 if compact else 7.2
        value_font = 8.8 if compact else 9.8
        step = 4.6 * mm if compact else 5.3 * mm
        band_h = 16 * mm if compact else 18 * mm
        band_y = oy + 5 * mm

        def divider(y_pos):
            c.setStrokeColorRGB(0.35, 0.35, 0.35)
            c.setLineWidth(0.65)
            c.line(ox + 3 * mm, y_pos, ox + lw - 3 * mm, y_pos)

        def fit_text(text, font_name, font_size, max_width):
            text = _safe(text)
            if c.stringWidth(text, font_name, font_size) <= max_width:
                return text
            trimmed = text
            while trimmed and c.stringWidth(trimmed + "…", font_name, font_size) > max_width:
                trimmed = trimmed[:-1]
            return (trimmed.rstrip() + "…") if trimmed else text

        def line_field(label, value, y_pos):
            c.setFont(font_b, label_font)
            label_text = f"{label}:"
            c.drawString(x, y_pos, label_text)
            label_w = c.stringWidth(label_text, font_b, label_font) + 3
            c.setFont(font_r, value_font)
            max_w = (ox + lw - pad) - (x + label_w)
            c.drawString(x + label_w, y_pos, fit_text(value, font_r, value_font, max_w))
            return y_pos - step

        c.setFont(font_b, meta_font)
        c.drawString(x, y, f"PEDIDO #{order_id_str}")
        c.setFont(font_r, meta_font)
        c.drawRightString(ox + lw - pad, y, date_str)
        y -= 5.3 * mm
        divider(y)
        y -= 4.8 * mm

        c.setFont(font_b, section_font)
        c.drawString(x, y, "DESTINATARIO:")
        y -= 5.2 * mm
        y = line_field("APELLIDO Y NOMBRE", dest_name, y)
        y = line_field("DNI/CUIL", dest_document, y)
        y = line_field("DIRECCIÓN", dest_address, y)
        if dest_city_line:
            y = line_field("LOCALIDAD", dest_city_line, y)
        if dest_phone and dest_phone != "-":
            y = line_field("TELÉFONO", dest_phone, y)
        if dest_email and dest_email != "-":
            y = line_field("E-MAIL", dest_email, y)

        y -= 1 * mm
        divider(y)
        y -= 4.8 * mm

        c.setFont(font_b, section_font)
        c.drawString(x, y, "REMITENTE:")
        y -= 5.2 * mm
        y = line_field("APELLIDO Y NOMBRE", sender_name, y)
        if sender_document and sender_document != "-":
            y = line_field("DNI/CUIL", sender_document, y)
        if sender_address:
            y = line_field("DIRECCIÓN", sender_address, y)
        if sender_city_line:
            y = line_field("LOCALIDAD", sender_city_line, y)
        if sender_phone and sender_phone != "-":
            y = line_field("TELÉFONO", sender_phone, y)
        if sender_email and sender_email != "-":
            y = line_field("E-MAIL", sender_email, y)

        # Fondo y reserva del cierre operacional
        c.setFillColorRGB(0.95, 0.95, 0.95)
        c.rect(ox + 3 * mm, band_y, lw - 6 * mm, band_h, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.8)
        c.rect(ox + 3 * mm, band_y, lw - 6 * mm, band_h, fill=0, stroke=1)

        c.setFont(font_b, 10 if compact else 11)
        c.drawString(x, band_y + (9.8 * mm if compact else 10.8 * mm), f"PEDIDO: #{order_id_str}")
        c.setFont(font_b, 13 if compact else 15)
        c.drawRightString(ox + lw - pad, band_y + (9.2 * mm if compact else 10.1 * mm), f"BULTO {bulto_num} DE {total_bultos}")

    if is_a4:
        label_w = lw_mm * mm
        label_h = lh_mm * mm
        margin_x = (page_w - 2 * label_w) / 2
        margin_y = (page_h - 2 * label_h) / 2
        positions = [
            (margin_x, margin_y + label_h),
            (margin_x + label_w, margin_y + label_h),
            (margin_x, margin_y),
            (margin_x + label_w, margin_y),
        ]
        slot = 0
        for bulto in range(1, num_bultos + 1):
            if slot >= 4:
                c.showPage()
                slot = 0
            ox, oy = positions[slot]
            draw_label(ox, oy, label_w, label_h, bulto, num_bultos)
            slot += 1
    else:
        label_w = page_w
        label_h = page_h
        for bulto in range(1, num_bultos + 1):
            draw_label(0, 0, label_w, label_h, bulto, num_bultos)
            if bulto < num_bultos:
                c.showPage()

    c.save()
    return buffer.getvalue()


def build_shipping_label_pdf(order, label_size="thermal", num_bultos=1) -> bytes:
    """Rótulo 2.1: compacto, sin barcode y orientado a despacho interno."""
    from io import BytesIO
    from datetime import datetime

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    sender = _get_sender_defaults()
    size_key = label_size if label_size in LABEL_SIZES else "thermal"
    lw_mm, lh_mm = LABEL_SIZES[size_key]
    is_a4 = size_key == "a4"

    if is_a4:
        page_w, page_h = A4
    else:
        page_w = lw_mm * mm
        page_h = lh_mm * mm

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))

    font_r = "Helvetica"
    font_b = "Helvetica-Bold"
    try:
        arial = r"C:\Windows\Fonts\arial.ttf"
        arial_bold = r"C:\Windows\Fonts\arialbd.ttf"
        if Path(arial).exists():
            pdfmetrics.registerFont(TTFont("Arial", arial))
            font_r = "Arial"
        if Path(arial_bold).exists():
            pdfmetrics.registerFont(TTFont("Arial-Bold", arial_bold))
            font_b = "Arial-Bold"
    except Exception:
        pass

    def _safe(val, fb="-"):
        s = str(val or "").strip()
        return s if s else fb

    def _join(parts):
        return " - ".join([part for part in parts if part and part != "-"])

    date_str = datetime.now().strftime("%d/%m/%Y")
    order_id_str = str(order.id or "")

    dest_name = _safe(order.nombre)
    dest_document = _safe(getattr(order, "destinatario_documento", ""))
    dest_address = _safe(order.direccion)
    dest_city_line = _join([
        _safe(order.ciudad, ""),
        _safe(order.estado, ""),
        f"CP {order.cp}" if str(getattr(order, 'cp', '') or '').strip() else "",
    ])
    dest_phone = _safe(order.telefono)
    dest_email = _safe(order.email)

    sender_name = _safe(getattr(order, "remitente_nombre", "") or sender.get("name", ""))
    sender_document = _safe(getattr(order, "remitente_documento", "") or sender.get("cuil", ""))
    sender_address = _safe(sender.get("address", ""), "")
    sender_city_line = _join([
        _safe(sender.get("city", ""), ""),
        _safe(sender.get("province", ""), ""),
        f"CP {str(sender.get('zip', '') or '').strip()}" if str(sender.get("zip", "") or "").strip() else "",
    ])
    sender_phone = _safe(getattr(order, "remitente_telefono", "") or sender.get("phone", ""))
    sender_email = _safe(getattr(order, "remitente_email", "") or sender.get("email", ""))

    def draw_label(ox, oy, lw, lh, bulto_num, total_bultos):
        pad = 5 * mm
        x = ox + pad
        top = oy + lh - pad
        y = top

        c.setStrokeColorRGB(0, 0, 0)
        c.setFillColorRGB(0, 0, 0)
        c.setLineWidth(1.0)
        c.rect(ox + 2 * mm, oy + 2 * mm, lw - 4 * mm, lh - 4 * mm)

        compact = lh <= (160 * mm)
        meta_font = 8 if compact else 9
        section_font = 13 if compact else 15
        label_font = 6.8 if compact else 7.2
        value_font = 8.8 if compact else 9.8
        step = 4.6 * mm if compact else 5.3 * mm
        band_h = 16 * mm if compact else 18 * mm
        band_y = oy + 5 * mm

        def divider(y_pos):
            c.setStrokeColorRGB(0.35, 0.35, 0.35)
            c.setLineWidth(0.65)
            c.line(ox + 3 * mm, y_pos, ox + lw - 3 * mm, y_pos)

        def fit_text(text, font_name, font_size, max_width):
            text = _safe(text)
            if c.stringWidth(text, font_name, font_size) <= max_width:
                return text
            trimmed = text
            while trimmed and c.stringWidth(trimmed + "…", font_name, font_size) > max_width:
                trimmed = trimmed[:-1]
            return (trimmed.rstrip() + "…") if trimmed else text

        def line_field(label, value, y_pos):
            c.setFont(font_b, label_font)
            label_text = f"{label}:"
            c.drawString(x, y_pos, label_text)
            label_w = c.stringWidth(label_text, font_b, label_font) + 3
            c.setFont(font_r, value_font)
            max_w = (ox + lw - pad) - (x + label_w)
            c.drawString(x + label_w, y_pos, fit_text(value, font_r, value_font, max_w))
            return y_pos - step

        c.setFont(font_b, meta_font)
        c.drawString(x, y, f"PEDIDO #{order_id_str}")
        c.setFont(font_r, meta_font)
        c.drawRightString(ox + lw - pad, y, date_str)
        y -= 5.3 * mm
        divider(y)
        y -= 4.8 * mm

        c.setFont(font_b, section_font)
        c.drawString(x, y, "DESTINATARIO:")
        y -= 5.2 * mm
        y = line_field("APELLIDO Y NOMBRE", dest_name, y)
        y = line_field("DNI/CUIL", dest_document, y)
        y = line_field("DIRECCIÓN", dest_address, y)
        if dest_city_line:
            y = line_field("LOCALIDAD", dest_city_line, y)
        if dest_phone and dest_phone != "-":
            y = line_field("TELÉFONO", dest_phone, y)
        if dest_email and dest_email != "-":
            y = line_field("E-MAIL", dest_email, y)

        y -= 1 * mm
        divider(y)
        y -= 4.8 * mm

        c.setFont(font_b, section_font)
        c.drawString(x, y, "REMITENTE:")
        y -= 5.2 * mm
        y = line_field("APELLIDO Y NOMBRE", sender_name, y)
        if sender_document and sender_document != "-":
            y = line_field("DNI/CUIL", sender_document, y)
        if sender_address:
            y = line_field("DIRECCIÓN", sender_address, y)
        if sender_city_line:
            y = line_field("LOCALIDAD", sender_city_line, y)
        if sender_phone and sender_phone != "-":
            y = line_field("TELÉFONO", sender_phone, y)
        if sender_email and sender_email != "-":
            y = line_field("E-MAIL", sender_email, y)

        c.setFillColorRGB(0.95, 0.95, 0.95)
        c.rect(ox + 3 * mm, band_y, lw - 6 * mm, band_h, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.8)
        c.rect(ox + 3 * mm, band_y, lw - 6 * mm, band_h, fill=0, stroke=1)

        c.setFont(font_b, 10 if compact else 11)
        c.drawString(x, band_y + (9.8 * mm if compact else 10.8 * mm), f"PEDIDO: #{order_id_str}")
        c.setFont(font_b, 13 if compact else 15)
        c.drawRightString(ox + lw - pad, band_y + (9.2 * mm if compact else 10.1 * mm), f"BULTO {bulto_num} DE {total_bultos}")

    if is_a4:
        label_w = lw_mm * mm
        label_h = lh_mm * mm
        margin_x = (page_w - 2 * label_w) / 2
        margin_y = (page_h - 2 * label_h) / 2
        positions = [
            (margin_x, margin_y + label_h),
            (margin_x + label_w, margin_y + label_h),
            (margin_x, margin_y),
            (margin_x + label_w, margin_y),
        ]
        slot = 0
        for bulto in range(1, num_bultos + 1):
            if slot >= 4:
                c.showPage()
                slot = 0
            ox, oy = positions[slot]
            draw_label(ox, oy, label_w, label_h, bulto, num_bultos)
            slot += 1
    else:
        label_w = page_w
        label_h = page_h
        for bulto in range(1, num_bultos + 1):
            draw_label(0, 0, label_w, label_h, bulto, num_bultos)
            if bulto < num_bultos:
                c.showPage()

    c.save()
    return buffer.getvalue()
