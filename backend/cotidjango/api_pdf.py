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
        base_dir.parent / "DjangoFrontCoti" / "src" / "assets" / "logo-coti-optimized.webp",
        base_dir.parent / "DjangoFrontCoti" / "public" / "logo-coti.png",
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
        try: val = Decimal(str(value or 0))
        except: val = Decimal("0")
        return "$" + f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _attrs_label(attrs):
        return order_item_attrs_label(attrs, prefix=" - ", separator=" | ", suffix="")

    def _safe(txt, fallback="-"):
        s = str(txt or "").strip()
        return s if s else fallback

    def _wrap_text(text, max_width, font_name, font_size):
        content = str(text or "").strip()
        if not content: return [""]
        paragraphs = content.splitlines()
        all_lines = []
        for paragraph in paragraphs:
            words = paragraph.split()
            if not words:
                all_lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                    current = candidate
                else:
                    all_lines.append(current)
                    current = word
            all_lines.append(current)
        return all_lines

    buffer = BytesIO()
    width, height = A4
    canvas_obj = canvas.Canvas(buffer, pagesize=A4)

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    try:
        arial = r"C:\Windows\Fonts\arial.ttf"
        arial_bold = r"C:\Windows\Fonts\arialbd.ttf"
        if Path(arial).exists():
            pdfmetrics.registerFont(TTFont("Arial", arial))
            font_regular = "Arial"
            pdfmetrics.registerFont(TTFont("Arial-Bold", arial_bold))
            font_bold = "Arial-Bold"
    except: pass

    margin_l = 36
    margin_r = 36
    x_left = margin_l
    x_right = width - margin_r
    footer_reserved_space = 96

    date_label = order.creado_en.strftime("%d/%m/%y %H:%M") if order.creado_en else ""
    address = ", ".join(filter(None, [order.direccion, order.ciudad, order.cp]))
    logo_path = _invoice_logo_path()

    def header(y):
        if logo_path:
            try:
                img = ImageReader(str(logo_path))
                canvas_obj.drawImage(img, x_right - 180, height - 66, width=180, height=58, mask="auto", preserveAspectRatio=True)
            except: pass
        canvas_obj.setFont(font_bold, 14)
        canvas_obj.drawString(x_left, y, f"Orden: #{order.id}")
        y -= 16
        canvas_obj.setFont(font_bold, 12)
        canvas_obj.drawString(x_left, y, "PRESUPUESTO")
        y -= 16
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left, y, f"Fecha: {date_label}")
        y -= 12
        canvas_obj.drawString(x_left, y, f"Pago: Acordar")
        y -= 24
        canvas_obj.setLineWidth(0.6)
        canvas_obj.setStrokeColorRGB(0.7, 0.7, 0.7)
        canvas_obj.line(x_left, y, x_right, y)
        return y - 16

    def customer(y):
        canvas_obj.setFont(font_bold, 9.5)
        canvas_obj.drawString(x_left, y, "Recibe:")
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left + 45, y, _safe(order.nombre))
        y -= 12
        canvas_obj.setFont(font_bold, 9.5)
        canvas_obj.drawString(x_left, y, "Dirección:")
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left + 55, y, _safe(address))
        y -= 12
        phone = str(order.telefono or "").strip()
        if phone:
            canvas_obj.setFont(font_bold, 9.5)
            canvas_obj.drawString(x_left, y, "Teléfono:")
            canvas_obj.setFont(font_regular, 9.5)
            canvas_obj.drawString(x_left + 50, y, phone)
            y -= 12
        return y - 8

    y = height - 40
    y = header(y)
    y = customer(y)

    # Nota / comentario del pedido
    nota = str(order.nota or "").strip()
    if nota:
        nota_lines = _wrap_text(nota, x_right - x_left - 60, font_regular, 9)
        canvas_obj.setFont(font_bold, 9)
        canvas_obj.drawString(x_left, y, "Nota:")
        canvas_obj.setFont(font_regular, 9)
        for i, line in enumerate(nota_lines):
            canvas_obj.drawString(x_left + 38, y - (i * 11), line)
        y -= max(12, len(nota_lines) * 11)
        y -= 6

    # Table Header
    row_h = 22
    canvas_obj.rect(x_left, y - row_h, x_right - x_left, row_h)
    canvas_obj.setFont(font_bold, 9.2)
    canvas_obj.drawString(x_left + 2, y - 15, "Cant")
    canvas_obj.drawString(x_left + 48, y - 15, "SKU")
    canvas_obj.drawString(x_left + 115, y - 15, "Descripción")
    canvas_obj.drawRightString(x_right - 76, y - 15, "P. unit")
    canvas_obj.drawRightString(x_right - 6, y - 15, "Total")
    y -= row_h

    import re
    items = list(order.items.all())
    
    def sort_key(item):
        has_sku = 1
        sku_sort = []
        cat_name = "zzzzz"
        prod_name = ""
        
        if item.product:
            sku = (item.product.sku or "").strip()
            if sku:
                has_sku = 0
                # Split strings and numbers for natural sorting (e.g., 2 comes before 10)
                sku_sort = [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', sku)]
                
            if item.product.categoria and item.product.categoria.nombre:
                cat_name = item.product.categoria.nombre.lower()
                
            prod_name = (item.product.nombre or "").lower()
            
        return (has_sku, cat_name, sku_sort, prod_name)
    
    items.sort(key=sort_key)

    for item in items:
        sku_val = getattr(item.product, "sku", "").strip() if item.product else ""
        desc = f"{order_item_name(item)}{_attrs_label(item.atributos)}"
        
        desc_lines = _wrap_text(desc, x_right - 140 - (x_left + 115), font_regular, 9)
        row_h = max(18, 8 + len(desc_lines) * 10)
        if y < footer_reserved_space + row_h:
            canvas_obj.showPage()
            y = height - 40
        
        canvas_obj.rect(x_left, y - row_h, x_right - x_left, row_h)
        canvas_obj.setFont(font_regular, 9)
        canvas_obj.drawString(x_left + 2, y - 13, str(item.cantidad))
        canvas_obj.drawString(x_left + 48, y - 13, sku_val)
        for i, line in enumerate(desc_lines):
            canvas_obj.drawString(x_left + 115, y - 13 - (i * 10), line)
        canvas_obj.drawRightString(x_right - 76, y - 13, _money(item.precio_unitario))
        canvas_obj.drawRightString(x_right - 6, y - 13, _money(item.subtotal))
        y -= row_h

    from decimal import Decimal as _Dec

    y -= 10
    # Separador antes de totales
    canvas_obj.setLineWidth(0.6)
    canvas_obj.setStrokeColorRGB(0.7, 0.7, 0.7)
    canvas_obj.line(x_right - 180, y, x_right, y)
    y -= 14

    subtotal_items = sum(
        (item.precio_unitario or _Dec("0")) * (item.cantidad or 0)
        for item in order.items.all()
    )
    envio_val = _Dec(str(getattr(order, "envio", 0) or 0))
    total_final = subtotal_items + envio_val

    canvas_obj.setFont(font_regular, 10)
    canvas_obj.drawRightString(x_right - 90, y, "Subtotal:")
    canvas_obj.setFont(font_bold, 10)
    canvas_obj.drawRightString(x_right, y, _money(subtotal_items))
    y -= 14

    if envio_val > 0:
        canvas_obj.setFont(font_regular, 10)
        canvas_obj.drawRightString(x_right - 90, y, "Envío:")
        canvas_obj.setFont(font_bold, 10)
        canvas_obj.drawRightString(x_right, y, _money(envio_val))
        y -= 14

    # Línea gruesa antes del total final
    canvas_obj.setLineWidth(1.0)
    canvas_obj.setStrokeColorRGB(0.2, 0.2, 0.2)
    canvas_obj.line(x_right - 180, y + 4, x_right, y + 4)
    y -= 8

    canvas_obj.setFont(font_bold, 12)
    canvas_obj.drawRightString(x_right - 90, y, "TOTAL:")
    canvas_obj.drawRightString(x_right, y, _money(total_final))


    # Leyenda al pie de la última página
    legend_y = 36
    canvas_obj.setLineWidth(0.4)
    canvas_obj.setStrokeColorRGB(0.75, 0.75, 0.75)
    canvas_obj.line(x_left, legend_y + 14, x_right, legend_y + 14)
    canvas_obj.setFont(font_regular, 8)
    canvas_obj.setFillColorRGB(0.45, 0.45, 0.45)
    canvas_obj.drawCentredString(
        (x_left + x_right) / 2,
        legend_y,
        "Los reclamos deben hacerse dentro de las 48 hs posteriores al recibir el pedido."
    )
    canvas_obj.setFillColorRGB(0, 0, 0)

    canvas_obj.save()
    return buffer.getvalue()

def build_stock_request_pdf(order) -> bytes:
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    import re

    def _attrs_label(attrs):
        return order_item_attrs_label(attrs, prefix=" - ", separator=" | ", suffix="")

    def _wrap_text(text, max_width, font_name, font_size):
        content = str(text or "").strip()
        if not content: return [""]
        paragraphs = content.splitlines()
        all_lines = []
        for paragraph in paragraphs:
            words = paragraph.split()
            if not words:
                all_lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                    current = candidate
                else:
                    all_lines.append(current)
                    current = word
            all_lines.append(current)
        return all_lines

    buffer = BytesIO()
    width, height = A4
    canvas_obj = canvas.Canvas(buffer, pagesize=A4)

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    try:
        arial = r"C:\Windows\Fonts\arial.ttf"
        arial_bold = r"C:\Windows\Fonts\arialbd.ttf"
        if Path(arial).exists():
            pdfmetrics.registerFont(TTFont("Arial", arial))
            font_regular = "Arial"
            pdfmetrics.registerFont(TTFont("Arial-Bold", arial_bold))
            font_bold = "Arial-Bold"
    except: pass

    margin_l = 36
    margin_r = 36
    x_left = margin_l
    x_right = width - margin_r
    footer_reserved_space = 40

    date_label = order.creado_en.strftime("%d/%m/%y %H:%M") if order.creado_en else ""
    logo_path = _invoice_logo_path()

    def header(y):
        if logo_path:
            try:
                img = ImageReader(str(logo_path))
                canvas_obj.drawImage(img, x_right - 180, height - 66, width=180, height=58, mask="auto", preserveAspectRatio=True)
            except: pass
        canvas_obj.setFont(font_bold, 14)
        canvas_obj.drawString(x_left, y, f"Orden: #{order.id}")
        y -= 16
        canvas_obj.setFont(font_bold, 12)
        canvas_obj.drawString(x_left, y, "PEDIDO DE STOCK")
        y -= 16
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left, y, f"Fecha: {date_label}")
        y -= 24
        canvas_obj.setLineWidth(0.6)
        canvas_obj.setStrokeColorRGB(0.7, 0.7, 0.7)
        canvas_obj.line(x_left, y, x_right, y)
        return y - 16

    def customer(y):
        canvas_obj.setFont(font_bold, 9.5)
        canvas_obj.drawString(x_left, y, "Solicita:")
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left + 45, y, "CotiStore")
        y -= 12
        canvas_obj.setFont(font_bold, 9.5)
        canvas_obj.drawString(x_left, y, "Dirección:")
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left + 55, y, "Gregorio de Laferrere - CP 1757")
        y -= 12
        canvas_obj.setFont(font_bold, 9.5)
        canvas_obj.drawString(x_left, y, "Teléfono:")
        canvas_obj.setFont(font_regular, 9.5)
        canvas_obj.drawString(x_left + 50, y, "11 3958-1816")
        y -= 12
        return y - 8

    y = height - 40
    y = header(y)
    y = customer(y)

    # Table Header
    row_h = 22
    canvas_obj.rect(x_left, y - row_h, x_right - x_left, row_h)
    canvas_obj.setFont(font_bold, 9.2)
    canvas_obj.drawString(x_left + 2, y - 15, "Cant")
    canvas_obj.drawString(x_left + 48, y - 15, "SKU")
    canvas_obj.drawString(x_left + 115, y - 15, "Descripción")
    y -= row_h

    items = list(order.items.all())
    
    def sort_key(item):
        has_sku = 1
        sku_sort = []
        cat_name = "zzzzz"
        prod_name = ""
        
        if item.product:
            sku = (item.product.sku or "").strip()
            if sku:
                has_sku = 0
                sku_sort = [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', sku)]
                
            if item.product.categoria and item.product.categoria.nombre:
                cat_name = item.product.categoria.nombre.lower()
                
            prod_name = (item.product.nombre or "").lower()
            
        return (has_sku, cat_name, sku_sort, prod_name)
    
    items.sort(key=sort_key)

    for item in items:
        sku_val = getattr(item.product, "sku", "").strip() if item.product else ""
        desc = f"{order_item_name(item)}{_attrs_label(item.atributos)}"
        
        desc_lines = _wrap_text(desc, x_right - (x_left + 115) - 5, font_regular, 9)
        row_h = max(18, 8 + len(desc_lines) * 10)
        if y < footer_reserved_space + row_h:
            canvas_obj.showPage()
            y = height - 40
        
        canvas_obj.rect(x_left, y - row_h, x_right - x_left, row_h)
        canvas_obj.setFont(font_regular, 9)
        canvas_obj.drawString(x_left + 2, y - 13, str(item.cantidad))
        canvas_obj.drawString(x_left + 48, y - 13, sku_val)
        for i, line in enumerate(desc_lines):
            canvas_obj.drawString(x_left + 115, y - 13 - (i * 10), line)
        y -= row_h

    canvas_obj.save()
    return buffer.getvalue()

LABEL_SIZES = {"thermal": (100, 150), "courier": (100, 190), "a4": (105, 148.5)}

def build_shipping_label_pdf(order, label_size="thermal", num_bultos=1) -> bytes:
    from io import BytesIO
    from datetime import datetime
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    size_key = label_size if label_size in LABEL_SIZES else "thermal"
    lw_mm, lh_mm = LABEL_SIZES[size_key]
    is_a4 = size_key == "a4"
    page_w, page_h = A4 if is_a4 else (lw_mm * mm, lh_mm * mm)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    
    def draw_label(ox, oy, lw, lh, bulto_num, total_bultos):
        # Outer Border
        c.setLineWidth(0.5)
        c.rect(ox + 2 * mm, oy + 2 * mm, lw - 4 * mm, lh - 4 * mm)
        
        y_cursor = oy + lh - 10 * mm
        x_left = ox + 8 * mm
        x_right = ox + lw - 8 * mm

        # Header: Order and Date
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x_left, y_cursor, f"PEDIDO #{order.id}")
        c.drawRightString(x_right, y_cursor, datetime.now().strftime("%d/%m/%Y"))
        
        y_cursor -= 10 * mm
        
        # --- DESTINATARIO ---
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x_left, y_cursor, "DESTINATARIO:")
        y_cursor -= 7 * mm
        
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x_left, y_cursor, "APELLIDO Y NOMBRE:")
        c.setFont("Helvetica", 10.5)
        c.drawString(x_left + 45 * mm, y_cursor, str(order.nombre))
        y_cursor -= 6 * mm
        
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x_left, y_cursor, "DNI/CUIL:")
        c.setFont("Helvetica", 10.5)
        c.drawString(x_left + 22 * mm, y_cursor, str(getattr(order, 'destinatario_documento', '-') or '-'))
        y_cursor -= 6 * mm

        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x_left, y_cursor, "DIRECCIÓN:")
        c.setFont("Helvetica", 10.5)
        c.drawString(x_left + 25 * mm, y_cursor, str(order.direccion))
        y_cursor -= 6 * mm

        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x_left, y_cursor, "LOCALIDAD:")
        c.setFont("Helvetica", 10.5)
        c.drawString(x_left + 25 * mm, y_cursor, f"{order.ciudad} - CP {order.cp}")
        y_cursor -= 6 * mm

        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x_left, y_cursor, "TELÉFONO:")
        c.setFont("Helvetica", 10.5)
        c.drawString(x_left + 25 * mm, y_cursor, str(order.telefono))
        y_cursor -= 6 * mm

        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x_left, y_cursor, "E-MAIL:")
        c.setFont("Helvetica", 10.5)
        c.drawString(x_left + 18 * mm, y_cursor, str(order.email))
        
        y_cursor -= 10 * mm
        c.setLineWidth(0.3)
        c.line(x_left, y_cursor + 4 * mm, x_right, y_cursor + 4 * mm)

        # --- REMITENTE ---
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x_left, y_cursor, "REMITENTE:")
        y_cursor -= 7 * mm

        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x_left, y_cursor, "APELLIDO Y NOMBRE:")
        c.setFont("Helvetica", 10.5)
        c.drawString(x_left + 45 * mm, y_cursor, "CotiStore")
        y_cursor -= 6 * mm

        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x_left, y_cursor, "LOCALIDAD:")
        c.setFont("Helvetica", 10.5)
        c.drawString(x_left + 25 * mm, y_cursor, "Gregorio de Laferrere - CP 1757")
        y_cursor -= 6 * mm

        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x_left, y_cursor, "TELÉFONO:")
        c.setFont("Helvetica", 10.5)
        c.drawString(x_left + 25 * mm, y_cursor, "11 3958-1816")

        # --- FOOTER ---
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(ox + lw/2, oy + 12 * mm, f"PEDIDO: #{order.id} BULTO {bulto_num} DE {total_bultos}")

    if is_a4:
        label_w, label_h = lw_mm * mm, lh_mm * mm
        for b in range(1, num_bultos + 1):
            if (b-1) % 4 == 0 and b > 1: c.showPage()
            slot = (b-1) % 4
            ox = (slot % 2) * label_w
            oy = page_h - ((slot // 2) + 1) * label_h
            draw_label(ox, oy, label_w, label_h, b, num_bultos)
    else:
        for b in range(1, num_bultos + 1):
            draw_label(0, 0, page_w, page_h, b, num_bultos)
            if b < num_bultos: c.showPage()
    
    c.save()
    return buffer.getvalue()
