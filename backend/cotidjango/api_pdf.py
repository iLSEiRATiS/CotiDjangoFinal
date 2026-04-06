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
        row_h = 18
        stroke_light()
        canvas_obj.rect(x_left, y - row_h, x_right - x_left, row_h)
        for v in (v1, v2, v3, v4):
            canvas_obj.line(v, y - row_h, v, y)

        canvas_obj.setFont(font_regular, 9)
        text_dark()
        canvas_obj.drawString(col_code + 2, y - 13, str(code))
        canvas_obj.drawString(col_qty + 2, y - 13, str(qty))

        if len(desc) > 60:
            desc = desc[:57] + "..."
        canvas_obj.drawString(col_desc + 2, y - 13, desc)

        canvas_obj.drawRightString(v4 - 6, y - 13, _money(unit))
        canvas_obj.drawRightString(x_right - 6, y - 13, _money(total))
        return y - row_h

    y = height - 40
    y = header(y)
    y = customer(y)
    y = table_header(y)

    for item in order.items.all():
        if y < footer_reserved_space + 18:
            canvas_obj.showPage()
            y = height - 40
            y = header(y)
            y = customer(y)
            y = table_header(y)

        desc = f"{order_item_name(item)}{_attrs_label(item.atributos)}"
        y = table_row(y, item.product_id or "-", item.cantidad, desc, item.precio_unitario, item.subtotal)

    y -= 14
    canvas_obj.setFont(font_bold, 11)
    if getattr(order, "envio", None):
        canvas_obj.drawRightString(x_right, y, f"ENVIO: {_money(order.envio)}")
        y -= 14
    canvas_obj.drawRightString(x_right, y, f"TOTAL: {_money(order.total)}")

    if y < footer_reserved_space:
        canvas_obj.showPage()
        y = height - 40
        y = header(y)
    draw_footer()

    canvas_obj.save()
    return buffer.getvalue()
